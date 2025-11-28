import time
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import statistics
from bilibili_api import search, user, video, sync, Credential
from core.tool_registry import ToolResult

# ==========================================
# 👇 Bilibili 凭证配置
# ==========================================
MY_SESSDATA = "131f13c1%2C1774179487%2C71799%2A92CjCW6GJ9HMc5hsa6xLNDpAkgFfU2sVsdN5QHM80H5FLxZjJK92balhkRVVZ46j6g0SVnZrT3pLREwzbUc3RFV0cFg1M0RLQjBKbGFlUnRFcVROOUUtLV9MY0lwWHlyMk9GN1F6RmRXWGhpRWdoWGZkZHFBeV9Mek04cVNxa0JENzh4c2dkOG9nIIEC"
MY_BUVID3 = "0AD3C626-7C49-A0E2-976E-C27C6E11DEA772471infoc"

class BilibiliSearchInput(BaseModel):
    keyword: str = Field(..., description="搜索关键词")
    limit: int = Field(15, description="返回结果数量限制（返回给调用者）")
    sort_by: str = Field("comprehensive", description="排序策略: comprehensive/click/dm/pubdate/stow/scores")
    days: int = Field(30, description="仅保留最近N天内的投稿，0表示不过滤")
    fetch_size: int = Field(50, description="实际从API获取的数量（过滤前）")

class BilibiliMonitorInput(BaseModel):
    user_id: str = Field(..., description="B站用户ID (mid)")
    limit: int = Field(10, description="返回结果数量限制")

class BilibiliAdapter:
    def __init__(self):
        # 初始化凭证
        if MY_SESSDATA:
            self.credential = Credential(sessdata=MY_SESSDATA, buvid3=MY_BUVID3)
            print("[Bilibili] ✅ 已加载用户凭证")
        else:
            self.credential = None
            print("[Bilibili] ⚠️ 警告：运行在游客模式")

    def search_videos(self, params: BilibiliSearchInput) -> ToolResult:
        """
        🎯 智能分页 + 爆款评分搜索

        策略:
        1. 智能分页（播放量下降就停止）
        2. 计算爆款分并排序
        3. 对top N补充详细信息

        Returns:
            ToolResult: 爆款优先的搜索结果
        """
        print(f"[Bilibili] 🔍 智能搜索: {params.keyword}")

        try:
            order_type = self._resolve_order(params.sort_by)

            # === 阶段1: 智能分页获取 ===
            print(f"📄 [阶段1] 智能分页扫描（最多 {params.fetch_size} 条）...")
            raw_videos = self._smart_pagination(
                params.keyword,
                order_type,
                target_count=params.fetch_size
            )

            if not raw_videos:
                print("[Bilibili] ❌ 未获取到数据")
                return ToolResult(
                    status="success",
                    data=[],
                    summary=f"No videos found for '{params.keyword}'"
                )

            print(f"✅ [阶段1] 扫描到 {len(raw_videos)} 条基础数据")

            # === 阶段2: 爆款评分与排序 ===
            print(f"🎯 [阶段2] 计算爆款分（详细处理 {params.limit} 条）...")
            scored_videos = self._score_and_rank_viral(raw_videos, params.days, params.keyword)  # 🔑 传递keyword

            if not scored_videos:
                print("[Bilibili] ⚠️ 所有视频被过滤")
                return ToolResult(
                    status="success",
                    data=[],
                    summary=f"All videos filtered out for '{params.keyword}'"
                )

            print(f"✅ [阶段2] 爆款排序完成，top {params.limit} 识别")

            # === 阶段3: 详细信息补充 ===
            print(f"📊 [阶段3] 补充 top {params.limit} 详细信息...")
            top_videos = scored_videos[:params.limit]
            enriched_videos = self._enrich_details(top_videos)

            print(f"✅ [Bilibili] 完成！扫描 {len(raw_videos)} 条 → 返回 {len(enriched_videos)} 条爆款")

            return ToolResult(
                status="success",
                data=enriched_videos,
                summary=f"Found {len(enriched_videos)} viral videos on Bilibili for '{params.keyword}' (scanned {len(raw_videos)} total)"
            )

        except Exception as e:
            print(f"[Bilibili] ❌ 搜索错误: {e}")
            import traceback
            traceback.print_exc()
            return ToolResult(status="error", error=str(e), summary=f"Bilibili search failed: {e}")

    def _smart_pagination(self, keyword: str, order_type, target_count: int = 50) -> List[Dict]:
        """
        智能分页: 播放量下降就停止

        策略:
        - 如果当前页平均播放量 < 上一页 * 50%，提前停止
        - 节省无效请求
        """
        collected = []
        current_page = 1
        max_pages = 8  # 最多8页
        last_avg_views = None  # 🔑 修复: 改为None，避免第一页被误判为"下降"

        while len(collected) < target_count and current_page <= max_pages:
            print(f"   抓取第 {current_page} 页...")

            try:
                # 🔑 修复: search_by_type 不接受 credential 参数
                # 搜索功能在游客模式下也能正常工作
                results = sync(search.search_by_type(
                    keyword=keyword,
                    search_type=search.SearchObjectType.VIDEO,
                    order_type=order_type,
                    page=current_page,
                    page_size=20
                ))
            except Exception as e:
                print(f"   ❌ 第 {current_page} 页请求失败: {e}")
                break

            if 'result' not in results or not results['result']:
                print(f"   🛑 第 {current_page} 页无数据，停止")
                break

            raw_list = results['result']
            page_videos = []

            for v in raw_list:
                if v.get('type') != 'video':
                    continue

                item = self._parse_basic_video(v)
                page_videos.append(item)
                collected.append(item)

            # 计算本页平均播放量
            if page_videos:
                current_avg = statistics.mean([v['view_count'] for v in page_videos])

                # 🔑 只在有历史数据时检查质量下降
                if last_avg_views is not None:
                    # 播放量大幅下降，说明质量变差
                    if current_avg < last_avg_views * 0.4:  # 下降超过60%
                        print(f"   ⚠️ 第 {current_page} 页质量下降（{current_avg:.0f} vs {last_avg_views:.0f}），提前停止")
                        break

                last_avg_views = current_avg
                print(f"   ✅ 第 {current_page} 页获取 {len(page_videos)} 条（平均播放: {current_avg:.0f}）")

            current_page += 1

            # 防止速率限制
            if current_page <= max_pages:
                time.sleep(1.0)  # 1秒延迟

        print(f"   📊 智能分页完成：{current_page-1} 页，共 {len(collected)} 条")
        return collected

    def _parse_basic_video(self, v: Dict) -> Dict:
        """解析单条视频的基础数据"""
        pub_ts = v.get('pubdate', 0)
        pub_date = datetime.fromtimestamp(pub_ts).strftime('%Y-%m-%d')

        # 清洗标题HTML
        raw_title = v.get('title', '')
        clean_title = raw_title.replace('<em class="keyword">', '').replace('</em>', '')

        # 🔑 修复: 处理duration字符串格式 (如 "5:30" -> 330秒)
        duration_raw = v.get('duration', 0)
        duration_seconds = self._parse_duration(duration_raw)

        return {
            "platform": "bilibili",
            "source_type": "search",
            "title": clean_title,
            "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
            "bvid": v.get('bvid'),
            "author_name": v.get('author', ''),
            "author_id": str(v.get('mid', '')),
            "publish_time": pub_date,
            "pub_ts": pub_ts,  # 保留时间戳用于计算
            "view_count": v.get('play', 0),
            "interaction": v.get('favorites', 0) + v.get('review', 0),
            "duration": duration_seconds,  # 转换为秒数
            "raw_data": v
        }

    def _score_and_rank_viral(self, videos: List[Dict], days: int = 30, keyword: str = "") -> List[Dict]:
        """
        计算爆款分并排序

        爆款分算法:
        viral_score = (播放量相对表现) * (时间新鲜度) * (互动率) * (时长权重) * (相关性权重)
        """
        if not videos:
            return []

        # 计算平均播放量
        valid_views = [v['view_count'] for v in videos if v['view_count'] > 0]
        avg_views = statistics.mean(valid_views) if valid_views else 1

        now = datetime.now()
        scored_videos = []

        for video in videos:
            # 播放量相对表现
            view_ratio = video['view_count'] / max(avg_views, 1)

            # 时间新鲜度
            freshness = 1.0
            days_old = 0

            if video.get('pub_ts'):
                try:
                    pub_dt = datetime.fromtimestamp(video['pub_ts'])
                    days_old = (now - pub_dt).days

                    # 超过时间范围，跳过
                    if days_old > days:
                        continue

                    # 时间衰减
                    if days_old <= 3:
                        freshness = 1.5
                    elif days_old <= 7:
                        freshness = 1.3
                    elif days_old <= 14:
                        freshness = 1.0
                    else:
                        freshness = 0.8

                except:
                    freshness = 1.0

            # 互动率
            engagement_rate = 1.0
            if video['view_count'] > 0:
                engagement_rate = 1.0 + (video['interaction'] / video['view_count']) * 10

            # 时长权重（5-15分钟是黄金时长）
            duration_weight = 1.0
            duration_min = video.get('duration', 0) / 60
            if 5 <= duration_min <= 15:
                duration_weight = 1.2
            elif duration_min < 2:
                duration_weight = 0.6
            elif duration_min > 30:
                duration_weight = 0.8

            # 🔑 新增：相关性权重
            relevance_weight = self._calculate_relevance(video.get('title', ''), keyword)

            # 综合爆款分（加入相关性权重）
            viral_score = view_ratio * freshness * engagement_rate * duration_weight * relevance_weight

            video['viral_score'] = viral_score
            video['days_old'] = days_old
            scored_videos.append(video)

        # 按爆款分排序
        scored_videos.sort(key=lambda x: x['viral_score'], reverse=True)

        # 输出top 3的爆款分
        if len(scored_videos) >= 3:
            print(f"   Top 3 爆款分: {scored_videos[0]['viral_score']:.2f}, {scored_videos[1]['viral_score']:.2f}, {scored_videos[2]['viral_score']:.2f}")

        return scored_videos

    def _enrich_details(self, videos: List[Dict]) -> List[Dict]:
        """
        为top N视频补充详细信息

        补充:
        - 详细统计（硬币、分享、收藏）
        - 标签
        - 描述
        """
        if not videos:
            return []

        enriched = []

        for i, vid in enumerate(videos):
            try:
                bvid = vid.get('bvid')
                if not bvid:
                    enriched.append(vid)
                    continue

                print(f"   补充详情 {i+1}/{len(videos)}: {vid['title'][:30]}...")

                # 获取详细信息（info 中已包含 stat 数据）
                v = video.Video(bvid=bvid, credential=self.credential)
                info = sync(v.get_info())

                # 从 info 中提取 stat（不再单独调用 get_stat，因为该 API 已被 B站禁用）
                stats = info.get('stat', {})

                # 合并数据
                enriched_video = {
                    **vid,  # 保留基础数据
                    "view_count": stats.get('view', vid['view_count']),
                    "likes": stats.get('like', 0),
                    "coins": stats.get('coin', 0),
                    "favorites": stats.get('favorite', 0),
                    "shares": stats.get('share', 0),
                    "comments": stats.get('reply', 0),
                    "danmaku": stats.get('danmaku', 0),
                    "interaction": stats.get('like', 0) + stats.get('coin', 0) + stats.get('favorite', 0),
                    "raw_data": {
                        "description": info.get('desc', '')[:200],
                        "tid": info.get('tid'),
                        "tname": info.get('tname'),
                        "pic": info.get('pic'),
                    }
                }

                # 尝试获取标签
                try:
                    tags = sync(v.get_tags())
                    enriched_video['raw_data']['tags'] = [t.get('tag_name', '') for t in tags[:10]]
                except:
                    enriched_video['raw_data']['tags'] = []

                enriched.append(enriched_video)

                # 速率控制
                time.sleep(0.5)

            except Exception as e:
                print(f"   ⚠️ 补充失败: {e}")
                # 失败时保留基础数据
                enriched.append(vid)

        return enriched

    def monitor_user(self, params: BilibiliMonitorInput) -> ToolResult:
        """
        🎯 博主质量评分监控

        策略:
        1. 获取最近5个视频
        2. 计算博主质量分
        3. 高分博主保留top 2，低分放弃
        """
        print(f"[Bilibili] 📡 监控UP主: {params.user_id}")

        try:
            u = user.User(uid=int(params.user_id), credential=self.credential)

            # 获取最近5个视频用于评分
            resp = sync(u.get_videos(ps=5))

            items = []
            if 'list' in resp and 'vlist' in resp['list']:
                vlist = resp['list']['vlist']
                for v in vlist:
                    pub_ts = v.get('created', 0)
                    pub_date = datetime.fromtimestamp(pub_ts).strftime('%Y-%m-%d')

                    item = {
                        "platform": "bilibili",
                        "source_type": "monitor",
                        "title": v.get('title', ''),
                        "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
                        "bvid": v.get('bvid'),
                        "author_name": v.get('author', ''),
                        "author_id": str(v.get('mid', '')),
                        "publish_time": pub_date,
                        "pub_ts": pub_ts,
                        "view_count": v.get('play', 0),
                        "interaction": v.get('comment', 0),
                        "raw_data": v
                    }
                    items.append(item)

            if len(items) < 2:
                print(f"   ⚠️ 视频数量不足")
                return ToolResult(status="success", data=[], summary="Not enough videos")

            # 计算博主质量分
            channel_score = self._score_channel_quality(items)
            print(f"   📊 博主质量分: {channel_score:.2f}")

            # 低分博主放弃
            if channel_score < 3.0:
                print(f"   ❌ 质量分过低，放弃该博主")
                return ToolResult(status="success", data=[], summary="Low quality channel")

            # 高分博主：保留最新2个视频
            items.sort(key=lambda x: x.get('pub_ts', 0), reverse=True)
            top_videos = items[:2]

            print(f"   ✅ 保留 {len(top_videos)} 条精品内容")

            return ToolResult(
                status="success",
                data=top_videos,
                summary=f"Retrieved {len(top_videos)} videos from high-quality Bilibili user {params.user_id}"
            )

        except Exception as e:
            print(f"[Bilibili] ❌ 监控错误: {e}")
            return ToolResult(status="error", error=str(e), summary=f"Bilibili monitor failed: {e}")

    def _score_channel_quality(self, videos: List[Dict]) -> float:
        """
        计算博主质量分

        指标:
        1. 平均播放量（相对基准）
        2. 平均互动率
        3. 发布频率
        """
        if len(videos) < 2:
            return 0.0

        # 1. 平均播放量评分
        avg_views = statistics.mean([v.get('view_count', 0) for v in videos])
        view_score = min(avg_views / 10000, 30)  # 最高30分

        # 2. 平均互动率评分
        engagement_rates = []
        for v in videos:
            views = v.get('view_count', 0)
            if views > 0:
                engagement = v.get('interaction', 0) / views
                engagement_rates.append(engagement)

        avg_engagement = statistics.mean(engagement_rates) if engagement_rates else 0
        engagement_score = min(avg_engagement * 1000, 30)  # 最高30分

        # 3. 发布频率加分
        frequency_bonus = 0
        now = datetime.now()
        for v in videos:
            pub_ts = v.get('pub_ts', 0)
            if pub_ts:
                try:
                    days_old = (now - datetime.fromtimestamp(pub_ts)).days
                    if days_old <= 7:
                        frequency_bonus = 20
                        break
                except:
                    pass

        total_score = view_score + engagement_score + frequency_bonus
        return total_score

    def _calculate_relevance(self, title: str, keyword: str) -> float:
        """
        计算标题与搜索词的相关性权重

        策略：
        1. 提取关键词中的核心术语
        2. 计算标题中匹配的比例
        3. 低相关性大幅降权，高相关性加权

        Returns:
            0.2 - 2.0 之间的权重值
        """
        if not keyword or not title:
            return 1.0

        # 标准化处理
        title_lower = title.lower()
        keyword_lower = keyword.lower()

        # 移除常见的无意义词（中英文）
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
            'latest', '2025', '2024', '11', '10', '12',
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'
        }

        # 提取关键词中的核心词
        keyword_terms = [term for term in keyword_lower.split() if term not in stop_words and len(term) > 1]

        if not keyword_terms:
            return 1.0

        # 计算匹配度
        matched_count = sum(1 for term in keyword_terms if term in title_lower)
        match_ratio = matched_count / len(keyword_terms)

        # 相关性权重映射
        if match_ratio >= 0.8:
            return 2.0  # 高度相关，翻倍
        elif match_ratio >= 0.5:
            return 1.5  # 中度相关，加权50%
        elif match_ratio >= 0.3:
            return 1.0  # 基本相关，保持
        elif match_ratio >= 0.1:
            return 0.5  # 低相关性，减半
        else:
            return 0.2  # 几乎不相关，大幅降权

    def _parse_duration(self, duration_raw) -> int:
        """
        解析Bilibili duration字段

        支持格式:
        - 字符串 "5:30" -> 330秒
        - 字符串 "1:05:30" -> 3930秒
        - 整数 330 -> 330秒

        Returns:
            int: 时长（秒）
        """
        if isinstance(duration_raw, int):
            return duration_raw

        if isinstance(duration_raw, str):
            try:
                parts = duration_raw.split(':')
                if len(parts) == 2:  # MM:SS
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:  # HH:MM:SS
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                else:
                    return 0
            except:
                return 0

        return 0

    def _resolve_order(self, sort_by: str):
        """排序参数映射"""
        mapping = {
            "comprehensive": search.OrderVideo.TOTALRANK,
            "click": search.OrderVideo.CLICK,
            "dm": search.OrderVideo.DM,
            "pubdate": search.OrderVideo.PUBDATE,
            "stow": search.OrderVideo.STOW,
            "scores": search.OrderVideo.SCORES
        }
        key = (sort_by or "comprehensive").lower()
        return mapping.get(key, search.OrderVideo.TOTALRANK)

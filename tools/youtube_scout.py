import json
import subprocess
import shutil
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import statistics
import scrapetube

class YoutubeScout:
    """
    YouTube 数据采集器 (v3.0 - 爆款优先版)
    核心策略: 三阶段筛选 + 博主质量评分
    1. 快速扫描大量候选
    2. 计算爆款分，智能排序
    3. 只对高分内容提取详细信息
    """
    def __init__(self):
        self.yt_dlp_cmd = self._get_yt_dlp_cmd()

    def _get_yt_dlp_cmd(self):
        """检查 yt-dlp 是否可用"""
        if shutil.which('yt-dlp'):
            return 'yt-dlp'
        return 'yt-dlp'

    def search_videos(self, keyword: str, limit: int = 15, days: int = 30, sort_by: str = "relevance", scan_limit: int = 0) -> List[Dict[str, Any]]:
        """
        🎯 三阶段爆款筛选搜索

        阶段1: 快速扫描 (scan_limit 条基础数据)
        阶段2: 计算爆款分，排序
        阶段3: 只对 top N 提取详细信息

        Args:
            keyword: 搜索关键词
            limit: 最终返回数量 (默认15)
            days: 时间范围 (默认30天)
            sort_by: 排序方式 (relevance/date)
            scan_limit: 快速扫描数量 (0=自动计算为limit*3)

        Returns:
            List[Dict]: 按爆款分排序的高质量视频列表
        """
        print(f"🔍 [YouTube] 三阶段搜索: {keyword}")

        # === 阶段1: 快速扫描 ===
        scan_count = scan_limit if scan_limit > 0 else limit * 3  # 🔑 支持自定义扫描数量
        print(f"📄 [阶段1] 快速扫描 {scan_count} 条（详细处理 {limit} 条）...")

        basic_videos = self._fast_scan(keyword, scan_count, sort_by)
        if not basic_videos:
            print("❌ 快速扫描未获取到数据")
            return []

        print(f"✅ [阶段1] 扫描到 {len(basic_videos)} 条基础数据")

        # === 阶段2: 爆款评分与排序 ===
        print(f"🎯 [阶段2] 计算爆款分...")

        scored_videos = self._score_and_rank_viral(basic_videos, days, keyword)
        print(f"✅ [阶段2] 排序完成，top {limit} 爆款识别")

        # === 阶段3: 详细信息提取 ===
        print(f"📊 [阶段3] 提取 top {limit} 详细信息...")

        top_videos = scored_videos[:limit]
        detailed_videos = self._enrich_details(top_videos)

        print(f"✅ [YouTube] 完成！返回 {len(detailed_videos)} 条爆款内容")
        return detailed_videos

    def _fast_scan(self, keyword: str, count: int, sort_by: str = "relevance") -> List[Dict[str, Any]]:
        """
        阶段1: 快速扫描
        使用 --flat-playlist 只获取基础元数据
        """
        search_prefix = "ytsearch"
        if (sort_by or "").lower() == "date":
            search_prefix = "ytsearchdate"

        cmd = [
            self.yt_dlp_cmd,
            f"{search_prefix}{count}:{keyword}",
            "--flat-playlist",  # 🔑 快速模式
            "--dump-json",
            "--no-warnings",
            "--ignore-errors",
            "--skip-download"
        ]

        videos = []
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode != 0:
                print(f"⚠️ yt-dlp 搜索失败: {result.stderr}")
                return []

            # 解析每行JSON
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    data = json.loads(line)

                    # 提取基础数据
                    video_id = data.get('id') or data.get('url')
                    if not video_id:
                        continue

                    # 构造URL
                    if len(video_id) == 11 and '.' not in video_id:
                        url = f"https://www.youtube.com/watch?v={video_id}"
                    else:
                        url = data.get('url') or data.get('webpage_url') or f"https://www.youtube.com/watch?v={video_id}"

                    # 基础数据字典
                    video = {
                        'url': url,
                        'id': video_id,
                        'title': data.get('title', ''),
                        'view_count': data.get('view_count', 0),
                        'upload_date': data.get('upload_date'),  # YYYYMMDD格式
                        'duration': data.get('duration', 0),
                        'channel': data.get('channel', ''),
                        'channel_id': data.get('channel_id', ''),
                    }
                    videos.append(video)

                except Exception as e:
                    continue

        except Exception as e:
            print(f"⚠️ 快速扫描异常: {e}")
            return []

        return videos

    def _score_and_rank_viral(self, videos: List[Dict], days: int = 30, keyword: str = "") -> List[Dict]:
        """
        阶段2: 计算爆款分并排序

        爆款分算法:
        viral_score = (播放量相对表现) * (时间新鲜度) * (时长权重) * (相关性权重)

        返回按爆款分排序的视频列表
        """
        if not videos:
            return []

        # 计算平均播放量（用于相对比较）
        valid_views = [v['view_count'] for v in videos if v['view_count'] > 0]
        avg_views = statistics.mean(valid_views) if valid_views else 1

        now = datetime.now()
        scored_videos = []

        for video in videos:
            # 播放量相对表现
            view_ratio = video['view_count'] / max(avg_views, 1)

            # 时间新鲜度计算
            freshness = 1.0
            if video.get('upload_date'):
                try:
                    upload_dt = datetime.strptime(video['upload_date'], "%Y%m%d")
                    days_old = (now - upload_dt).days

                    # 超过时间范围的直接跳过
                    if days_old > days:
                        continue

                    # 时间衰减: 越新越好
                    if days_old <= 3:
                        freshness = 1.5  # 3天内加分
                    elif days_old <= 7:
                        freshness = 1.2  # 7天内加分
                    elif days_old <= 14:
                        freshness = 1.0  # 14天内正常
                    else:
                        freshness = 0.8  # 超过14天降分

                except:
                    freshness = 1.0

            # 时长权重（3-20分钟是黄金时长）
            duration_weight = 1.0
            duration_min = video.get('duration', 0) / 60
            if 3 <= duration_min <= 20:
                duration_weight = 1.2
            elif duration_min < 1:
                duration_weight = 0.5  # 太短的视频降分
            elif duration_min > 60:
                duration_weight = 0.8  # 太长的视频降分

            # 🔑 新增：相关性权重
            relevance_weight = self._calculate_relevance(video.get('title', ''), keyword)

            # 综合爆款分（加入相关性权重）
            viral_score = view_ratio * freshness * duration_weight * relevance_weight

            video['viral_score'] = viral_score
            video['days_old'] = days_old if video.get('upload_date') else 999
            scored_videos.append(video)

        # 按爆款分排序（降序）
        scored_videos.sort(key=lambda x: x['viral_score'], reverse=True)

        # 输出top 3的爆款分（调试用）
        if len(scored_videos) >= 3:
            print(f"   Top 3 爆款分: {scored_videos[0]['viral_score']:.2f}, {scored_videos[1]['viral_score']:.2f}, {scored_videos[2]['viral_score']:.2f}")

        return scored_videos

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

        # 移除常见的无意义词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'latest', '2025', '2024', '11', '10', '12'}

        # 提取关键词中的核心词
        keyword_terms = [term for term in keyword_lower.split() if term not in stop_words and len(term) > 2]

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

    def _enrich_details(self, videos: List[Dict]) -> List[Dict]:
        """
        阶段3: 为top N视频补充详细信息

        补充字段:
        - 点赞数、评论数
        - 作者信息
        - 标签（前10个）
        - 描述（前200字）
        - 分类
        """
        if not videos:
            return []

        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'socket_timeout': 15,
        }

        enriched = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for i, video in enumerate(videos):
                try:
                    print(f"   提取详情 {i+1}/{len(videos)}: {video['title'][:40]}...")

                    # 获取完整信息
                    info = ydl.extract_info(video['url'], download=False)
                    if not info:
                        continue

                    # 合并数据
                    enriched_video = {
                        # 基础数据（保留）
                        "title": info.get('title', video['title']),
                        "url": video['url'],
                        "platform": "youtube",

                        # 数据指标
                        "view_count": info.get('view_count', video['view_count']),
                        "likes": info.get('like_count', 0),
                        "comments": info.get('comment_count', 0),
                        "interaction": (info.get('like_count') or 0) + (info.get('comment_count') or 0),

                        # 作者信息
                        "author_name": info.get('uploader', video.get('channel', 'Unknown')),
                        "author_id": info.get('channel_id', video.get('channel_id', '')),
                        "author_fans": info.get('channel_follower_count', 0),

                        # 时间信息
                        "publish_time": info.get('upload_date', video.get('upload_date')),
                        "duration": info.get('duration', video.get('duration', 0)),

                        # 爆款分（用于后续分析）
                        "viral_score": video.get('viral_score', 0),
                        "days_old": video.get('days_old', 0),

                        # 详细信息
                        "raw_data": {
                            "description": (info.get('description') or "")[:200],  # 前200字
                            "tags": info.get('tags', [])[:10],  # 前10个标签
                            "category": info.get('categories', []),
                            "language": info.get('language'),
                        }
                    }

                    enriched.append(enriched_video)

                except Exception as e:
                    # 单个失败不影响整体
                    print(f"   ⚠️ 提取失败: {e}")
                    continue

        return enriched

    def get_channel_videos(self, channel_url: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        🎯 博主质量评分监控

        策略:
        1. 获取最近5个视频
        2. 计算博主"近期表现分"
        3. 高分博主保留top 2视频，低分博主放弃

        Returns:
            List[Dict]: 高质量博主的精选内容（最多2条）
        """
        print(f"📡 [YouTube] 监控博主: {channel_url}")

        # 获取最近5个视频用于评分
        recent_urls = self._get_channel_recent_urls(channel_url, limit=5)
        if not recent_urls:
            print(f"   ❌ 未获取到视频")
            return []

        # 获取详细信息
        videos = self._hydrate_urls(recent_urls, check_date_days=None)  # 不过滤时间
        if len(videos) < 2:
            print(f"   ⚠️ 视频数量不足，跳过评分")
            return []

        # 计算博主质量分
        channel_score = self._score_channel_quality(videos)
        print(f"   📊 博主质量分: {channel_score:.2f}")

        # 低分博主直接放弃
        if channel_score < 5.0:  # 阈值可调
            print(f"   ❌ 质量分过低，放弃该博主")
            return []

        # 高分博主：保留最新2个视频
        # 按时间排序
        videos.sort(key=lambda x: x.get('publish_time', ''), reverse=True)
        top_videos = videos[:2]

        print(f"   ✅ 保留 {len(top_videos)} 条精品内容")
        return top_videos

    def _get_channel_recent_urls(self, channel_url: str, limit: int = 5) -> List[str]:
        """获取频道最近视频URLs"""
        urls = []

        # 优先使用 scrapetube (快速)
        try:
            videos = scrapetube.get_channel(channel_url=channel_url, limit=limit)
            for v in videos:
                v_id = v.get('videoId')
                if v_id:
                    urls.append(f"https://www.youtube.com/watch?v={v_id}")
        except Exception as e:
            print(f"   ⚠️ Scrapetube 失败，回退到 yt-dlp: {e}")

            # 回退到 yt-dlp
            cmd = [
                self.yt_dlp_cmd,
                channel_url,
                f"--playlist-end", str(limit),
                "--flat-playlist",
                "--dump-json",
                "--no-warnings",
                "--ignore-errors",
                "--skip-download"
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        url = data.get('url') or data.get('webpage_url')
                        if url:
                            urls.append(url)
                    except:
                        pass
            except Exception as inner_e:
                print(f"   ❌ yt-dlp 也失败: {inner_e}")

        return urls

    def _score_channel_quality(self, videos: List[Dict]) -> float:
        """
        计算博主质量分

        核心指标:
        1. 平均播放量 (相对粉丝数)
        2. 平均互动率
        3. 发布频率

        Returns:
            float: 质量分 (0-100)
        """
        if len(videos) < 2:
            return 0.0

        # 提取粉丝数（使用第一个视频的）
        author_fans = videos[0].get('author_fans', 0)
        if author_fans == 0:
            author_fans = 100000  # 默认假设10万粉丝

        # 1. 平均播放量相对粉丝数
        avg_views = statistics.mean([v.get('view_count', 0) for v in videos])
        view_ratio = avg_views / author_fans  # 播放量/粉丝数比例
        view_score = min(view_ratio * 100, 50)  # 最高50分

        # 2. 平均互动率
        engagement_rates = []
        for v in videos:
            views = v.get('view_count', 0)
            if views > 0:
                engagement = (v.get('likes', 0) + v.get('comments', 0)) / views
                engagement_rates.append(engagement)

        avg_engagement = statistics.mean(engagement_rates) if engagement_rates else 0
        engagement_score = min(avg_engagement * 1000, 30)  # 最高30分

        # 3. 发布频率加分
        frequency_bonus = 0
        now = datetime.now()
        for v in videos:
            upload_date = v.get('publish_time')
            if upload_date:
                try:
                    dt = datetime.strptime(upload_date, "%Y%m%d")
                    days_old = (now - dt).days
                    if days_old <= 7:
                        frequency_bonus = 20  # 7天内有视频，加20分
                        break
                except:
                    pass

        # 综合评分
        total_score = view_score + engagement_score + frequency_bonus
        return total_score

    def _hydrate_urls(self, urls: List[str], check_date_days: int = None) -> List[Dict[str, Any]]:
        """
        批量提取视频详细信息
        """
        if not urls:
            return []

        final_data = []
        now = datetime.now()
        skipped_count = 0

        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'socket_timeout': 10,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                try:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        continue

                    # 日期过滤
                    upload_date_str = info.get('upload_date')
                    is_valid_date = True

                    if check_date_days and upload_date_str:
                        try:
                            d = datetime.strptime(upload_date_str, "%Y%m%d")
                            delta_days = (now - d).days
                            if delta_days > check_date_days:
                                skipped_count += 1
                                continue
                        except:
                            pass

                    # 数据组装
                    item = {
                        "title": info.get('title'),
                        "url": info.get('webpage_url', url),
                        "view_count": info.get('view_count', 0),
                        "interaction": (info.get('like_count') or 0) + (info.get('comment_count') or 0),
                        "likes": info.get('like_count', 0),
                        "comments": info.get('comment_count', 0),
                        "author_name": info.get('uploader', 'Unknown'),
                        "author_id": info.get('channel_id', ''),
                        "author_fans": info.get('channel_follower_count', 0),
                        "publish_time": upload_date_str,
                        "platform": "youtube",
                        "raw_data": {
                            "description": (info.get('description') or "")[:200],
                            "tags": info.get('tags', [])[:10]
                        }
                    }
                    final_data.append(item)

                except Exception as e:
                    pass

        if skipped_count > 0:
            print(f"  🧹 [YouTube] 过滤掉 {skipped_count} 条过期视频 (>{check_date_days}天)")

        return final_data

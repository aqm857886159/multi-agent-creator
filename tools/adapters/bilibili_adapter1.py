import time
from datetime import datetime, timedelta
from bilibili_api import search, user, sync, Credential
from core.tool_registry import ToolResult

# ==========================================
# 👇 这里是你刚刚提供的凭证 (已填好)
# ==========================================
MY_SESSDATA = "131f13c1%2C1774179487%2C71799%2A92CjCW6GJ9HMc5hsa6xLNDpAkgFfU2sVsdN5QHM80H5FLxZjJK92balhkRVVZ46j-j6g0SVnZrT3pLREwzbUc3RFV0cFg1M0RLQjBKbGFlUnRFcVROOUUtLV9MY0lwWHlyMk9GN1F6RmRXWGhpRWdoWGZkZHFBeV9Mek04cVNxa0JENzh4c2dkOG9nIIEC"
MY_BUVID3 = "0AD3C626-7C49-A0E2-976E-C27C6E11DEA772471infoc"

class BilibiliAdapter:
    def __init__(self):
        # 初始化凭证
        if MY_SESSDATA:
            self.credential = Credential(sessdata=MY_SESSDATA, buvid3=MY_BUVID3)
            print("[Bilibili] ✅ 已加载用户凭证，解除游客限制，火力全开！")
        else:
            self.credential = None
            print("[Bilibili] ⚠️ 警告：运行在游客模式，数据量将受限")

    def search_videos(self, params: BilibiliSearchInput) -> ToolResult:
        print(f"[Bilibili] 🔍 正在搜索: {params.keyword}")
        
        try:
            order_type = self._resolve_order(params.sort_by)
            # 设定目标获取数量
            fetch_goal = params.fetch_size if hasattr(params, 'fetch_size') else params.limit * 3
            
            collected_items = []
            current_page = 1
            max_pages = 10  # 最大翻10页
            
            while len(collected_items) < fetch_goal and current_page <= max_pages:
                print(f"[Bilibili] 正在抓取第 {current_page} 页... (当前已获: {len(collected_items)} 条)")
                
                try:
                    # 调用搜索接口
                    results = sync(search.search_by_type(
                        keyword=params.keyword,
                        search_type=search.SearchObjectType.VIDEO,
                        order_type=order_type,
                        page=current_page,
                        page_size=20,          
                        credential=self.credential # 🔑 关键：使用你的凭证
                    ))
                except Exception as e:
                    print(f"[Bilibili] ❌ 第 {current_page} 页请求失败: {e}")
                    break

                if 'result' not in results or not results['result']:
                    print("[Bilibili] 🛑 已到达搜索结果末尾。")
                    break

                raw_list = results['result']
                
                for v in raw_list:
                    if v.get('type') != 'video':
                        continue
                    item = self._parse_video_item(v)
                    collected_items.append(item)
                
                # 翻页
                current_page += 1
                time.sleep(1.5) # 休息一下防止封IP

            # 过滤和排序
            final_items = self._filter_and_sort(collected_items, params)
            
            return ToolResult(
                status="success",
                data=final_items,
                summary=f"成功抓取 {len(final_items)} 条视频 (共扫描 {len(collected_items)} 条)"
            )

        except Exception as e:
            print(f"[Bilibili] Error: {e}")
            return ToolResult(status="error", error=str(e), summary=f"API Error: {e}")

    # --- 辅助方法 1: 解析单条数据 ---
    def _parse_video_item(self, v):
        pub_ts = v.get('pubdate', 0)
        pub_date = datetime.fromtimestamp(pub_ts).strftime('%Y-%m-%d')
        
        # 清洗标题 HTML
        raw_title = v.get('title', '')
        clean_title = raw_title.replace('<em class="keyword">', '').replace('</em>', '')
        
        return {
            "platform": "bilibili",
            "source_type": "search",
            "title": clean_title,
            "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
            "author_name": v.get('author', ''),
            "author_id": str(v.get('mid', '')),
            "publish_time": pub_date,
            "pub_ts": pub_ts,
            "view_count": v.get('play', 0),
            "interaction": v.get('favorites', 0) + v.get('review', 0),
            "raw_data": v
        }

    # --- 辅助方法 2: 过滤与排序 ---
    def _filter_and_sort(self, items, params):
        filtered_items = []
        cutoff = None
        
        if params.days and params.days > 0:
            cutoff = datetime.now() - timedelta(days=params.days)
        
        for item in items:
            if cutoff:
                item_dt = datetime.fromtimestamp(item['pub_ts'])
                if item_dt < cutoff:
                    continue
            filtered_items.append(item)
            
        return filtered_items[:params.limit]

    # --- 辅助方法 3: 排序参数映射 ---
    def _resolve_order(self, sort_by: str):
        mapping = {
            "comprehensive": search.OrderVideo.TOTALRANK,
            "click": search.OrderVideo.CLICK,
            "pubdate": search.OrderVideo.PUBDATE,
        }
        return mapping.get((sort_by or "comprehensive").lower(), search.OrderVideo.TOTALRANK)
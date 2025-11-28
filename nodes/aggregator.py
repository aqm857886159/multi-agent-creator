import asyncio
from typing import Dict, Any, List
import os
from core.state import RadarState, ContentItem
from core.config import load_settings
from tools.youtube_scout import YoutubeScout
from tools.douyin_scout import DouyinScout
from tools.reddit_scout import RedditScout
from tools.x_scout import XScout

def run_dual_collection(state: RadarState) -> Dict[str, Any]:
    """
    节点 2: 数据聚合 (Aggregator)
    集成 YouTube, Douyin, Reddit, X (Twitter) 四大平台
    """
    print("\n--- 节点: 数据聚合 (Node 2: Aggregator) ---")
    settings = load_settings()
    
    # 初始化 Scouts
    yt_scout = YoutubeScout()
    dy_scout = DouyinScout(headless=True) 
    rd_scout = RedditScout()
    x_scout = XScout()
    
    collected_items: List[ContentItem] = []
    logs = []

    # ==========================================
    # 1. 监控模式 (Monitor Mode)
    # ==========================================
    
    # [YouTube]
    yt_kols = state.monitoring_list.get("youtube", []) + settings.get("whitelist_kols", {}).get("youtube", [])
    if yt_kols:
        print(f"\n📡 [YouTube] 监控任务: {len(set(yt_kols))} 个频道")
        for kol in set(yt_kols):
            try:
                collected_items.extend([ContentItem(**i) for i in yt_scout.get_channel_videos(kol)])
            except Exception as e: logs.append(f"YT监控失败 {kol}: {e}")

    # [Douyin]
    dy_kols = state.monitoring_list.get("douyin", []) + settings.get("whitelist_kols", {}).get("douyin", [])
    if dy_kols:
        print(f"\n📡 [抖音] 监控任务: {len(set(dy_kols))} 个账号")
        for kol in set(dy_kols):
            try:
                collected_items.extend([ContentItem(**i) for i in dy_scout.get_user_posts(kol)])
            except Exception as e: logs.append(f"DY监控失败 {kol}: {e}")

    # [Reddit]
    rd_kols = state.monitoring_list.get("reddit", []) + settings.get("whitelist_kols", {}).get("reddit", [])
    if rd_kols:
        print(f"\n📡 [Reddit] 监控任务: {len(set(rd_kols))} 个目标")
        for target in set(rd_kols):
            try:
                if "/r/" in target: items = rd_scout.monitor_subreddit(target)
                else: items = rd_scout.monitor_user(target)
                collected_items.extend([ContentItem(**i) for i in items])
            except Exception as e: logs.append(f"RD监控失败 {target}: {e}")

    # [X / Twitter]
    x_kols = state.monitoring_list.get("twitter", []) + settings.get("whitelist_kols", {}).get("twitter", [])
    if x_kols:
        # 检查是否有配置账号，否则 X 很容易失败
        if os.getenv("X_USERNAME") or os.path.exists("user_data/x_cookies.json"):
            print(f"\n📡 [X/Twitter] 监控任务: {len(set(x_kols))} 个博主")
            for kol in set(x_kols):
                try:
                    collected_items.extend([ContentItem(**i) for i in x_scout.get_user_tweets(kol)])
                except Exception as e: logs.append(f"X监控失败 {kol}: {e}")
        else:
            logs.append("⚠️ 跳过 X 监控: 未配置 X_USERNAME/X_PASSWORD 且无 Cookies")

    # ==========================================
    # 2. 搜索模式 (Search Mode)
    # ==========================================
    keywords = state.keywords
    if keywords:
        print(f"\n🏹 [全网猎捕] 关键词: {keywords}")
        for kw in keywords:
            # YouTube
            try:
                collected_items.extend([ContentItem(**i) for i in yt_scout.search_videos(kw)])
            except Exception as e: logs.append(f"YT搜索失败 {kw}: {e}")

            # Reddit
            try:
                collected_items.extend([ContentItem(**i) for i in rd_scout.search(kw)])
            except Exception as e: logs.append(f"RD搜索失败 {kw}: {e}")

            # X / Twitter
            if os.getenv("X_USERNAME") or os.path.exists("user_data/x_cookies.json"):
                try:
                    collected_items.extend([ContentItem(**i) for i in x_scout.search(kw)])
                except Exception as e: logs.append(f"X搜索失败 {kw}: {e}")

    # 清理
    dy_scout.close()
    
    # 去重
    seen = set()
    unique_items = []
    for item in collected_items:
        if item.url not in seen:
            seen.add(item.url)
            unique_items.append(item)
    
    logs.append(f"采集完成: 原始 {len(collected_items)} -> 去重后 {len(unique_items)}")
    print(f"\n📊 [汇总] 最终有效数据: {len(unique_items)} 条")
    
    return {"candidates": unique_items, "logs": logs}

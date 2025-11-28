from typing import List, Dict, Any
from datetime import datetime, timedelta
import dateutil.parser
import statistics
from collections import defaultdict
from core.state import RadarState, ContentItem
import sys
import os

# 添加 utils 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.logger import print_filter_result

def run_hybrid_filter(state: RadarState) -> Dict[str, Any]:
    """
    节点 3: 智能筛选 (Filter V3)
    核心逻辑: 统计学异常检测 (Z-Score & 同行对比)
    """
    print("\n--- 节点: 智能筛选 (Node 3: Filter V3) ---")
    
    valid_items = []
    logs = []
    now = datetime.now()

    before_count = len(state.candidates)
    state.candidates = _deduplicate_candidates(state.candidates)
    after_count = len(state.candidates)
    if after_count < before_count:
        logs.append(f"去重 {before_count}->{after_count}")

    _enrich_cross_platform_metrics(state.candidates)
    
    # 🔑 修复: 按引擎分组，不是按source_type
    monitor_items = [i for i in state.candidates if
                     i.raw_data.get("engine") == "engine1" or
                     i.raw_data.get("from_influencer_search") or
                     i.source_type in ["youtube_monitor", "bilibili_monitor"]]

    hunter_items = [i for i in state.candidates if
                    i.raw_data.get("engine") == "engine2" and
                    not i.raw_data.get("from_influencer_search")]

    print(f"\n{'='*60}")
    print(f"🧹 智能筛选")
    print(f"   输入: {len(state.candidates)} 条 (🔴{len(monitor_items)} 🔵{len(hunter_items)})")
    
    # --- 策略 A: 监控模式 (纵向对比) ---
    # 🔵 引擎 1: 头部博主监控 - 纵向异常检测
    # 目标: 发现博主自己"发挥超常"的视频

    passed_time_check = 0
    for item in monitor_items:
        # 1. 时效检查（放宽到30天）
        if not _check_time(item.publish_time, days=30):
            continue
        passed_time_check += 1

        # 2. 异常值检测
        if item.author_avg_views > 0:
            ratio = item.view_count / item.author_avg_views

            # 阈值: 1.2倍 (比平时好20%)
            if ratio > 1.2:
                item.score = 80.0 + (ratio * 10)
                item.raw_data["analysis_note"] = f"比平时数据好 {ratio:.1f} 倍"
                item.raw_data["engine"] = "引擎1-头部博主监控"
                item.raw_data["detection_type"] = "纵向异常"
                valid_items.append(item)
            else:
                # 特例: 绝对爆款 (超过50万播放)，即使该博主平时就很强，也保留
                if item.view_count > 500000:
                    item.score = 75.0
                    item.raw_data["engine"] = "引擎1-头部博主监控"
                    item.raw_data["detection_type"] = "绝对爆款"
                    item.raw_data["analysis_note"] = "绝对流量爆款"
                    valid_items.append(item)
        else:
            # 🔑 修复关键问题 2: 降低兜底策略阈值（从 5000 降到 1000）
            # 兜底: 无历史基准数据时，只看绝对指标
            if item.view_count > 1000 or item.interaction > 50:
                 item.score = 70.0
                 item.raw_data["analysis_note"] = "监控数据（无历史基准）"
                 item.raw_data["engine"] = "引擎1-头部博主监控"
                 item.raw_data["detection_type"] = "绝对指标"
                 valid_items.append(item)

    print(f"   引擎1通过时效检查: {passed_time_check}/{len(monitor_items)}")

    # --- 策略 B: 猎杀模式 (横向对比) ---
    # 🔴 引擎 2: 关键词搜索 - 横向对比找爆款
    # 目标: 发现比同行强得多的视频

    if hunter_items:
        # 1. 计算当前池子的中位数 (基准线)
        views = [i.view_count for i in hunter_items if i.view_count > 0]
        median_views = statistics.median(views) if views else 1000

        print(f"📊 猎杀池播放中位数: {median_views}")

        passed_time_check2 = 0
        passed_criteria = 0
        for item in hunter_items:
             # 时效检查（放宽到60天）
            if not _check_time(item.publish_time, days=60):
                continue
            passed_time_check2 += 1

            # 2. 同行对比
            # 🔑 修复关键问题 4: 降低筛选标准（从 2倍降到 1.5倍）

            fans = item.author_fans if item.author_fans > 0 else 5000
            interaction = item.interaction
            if interaction == 0:
                interaction = item.view_count * 0.02 # 估算互动

            rate = interaction / fans

            is_view_outlier = (item.view_count > median_views * 1.5)  # 从 2 降到 1.5
            is_eng_outlier = (rate > 0.01)  # 从 0.02 降到 0.01 
            
            normalized_view = item.raw_data.get("normalized_view", 0)
            if normalized_view > 0:
                score_boost = normalized_view * 5
            else:
                score_boost = (item.view_count / median_views * 5)

            if is_view_outlier or is_eng_outlier or normalized_view > 2:
                passed_criteria += 1
                item.score = 60.0 + score_boost
                note = "赛道黑马 (Peer Outlier)"
                if normalized_view:
                    note += f" | 归一播放 {normalized_view:.1f}x"
                item.raw_data["analysis_note"] = note
                item.raw_data["engine"] = "引擎2-关键词搜索"
                item.raw_data["detection_type"] = "横向异常"
                valid_items.append(item)
            
            # Reddit 特赦 (高价值文本)
            elif item.platform == "reddit" and item.interaction > 50:
                item.score = 65.0
                item.raw_data["engine"] = "引擎2-关键词搜索"
                item.raw_data["detection_type"] = "高价值文本"
                valid_items.append(item)

        print(f"   引擎2通过时效检查: {passed_time_check2}/{len(hunter_items)}")
        print(f"   引擎2符合筛选标准: {passed_criteria}/{passed_time_check2}")

    # 排序并截取 Top 10
    valid_items.sort(key=lambda x: x.score, reverse=True)
    top_items = valid_items[:10]

    summary_msg = f"筛选后剩余 {len(top_items)} 条优质素材。"
    logs.append(summary_msg)
    state.logs.append(f"【筛选】输入 {len(state.candidates)} 条，输出 {len(top_items)} 条。")

    print(f"   输出: {len(top_items)} 条\n")
    
    return {
        "filtered_candidates": top_items,
        "logs": logs
    }

def _check_time(publish_time, days=7):
    try:
        now = datetime.now()
        p_time = None
        if isinstance(publish_time, (int, float)):
            p_time = datetime.fromtimestamp(publish_time)
        elif isinstance(publish_time, str):
            clean_time = publish_time.replace("/", "").replace("-", "").replace(".", "")
            if len(clean_time) == 8 and clean_time.isdigit():
                p_time = datetime.strptime(clean_time, "%Y%m%d")
            else:
                p_time = dateutil.parser.parse(publish_time)
        
        if p_time:
            if p_time.tzinfo: p_time = p_time.replace(tzinfo=None)
            if (now - p_time).days > days:
                return False
        return True
    except:
        return True 


def _deduplicate_candidates(items: List[ContentItem]) -> List[ContentItem]:
    deduped = {}
    for item in items:
        key_source = item.url or item.title or f"{item.platform}-{id(item)}"
        key = key_source.strip().lower()
        if key in deduped:
            existing = deduped[key]
            _merge_sources(existing, item)
            if item.view_count > existing.view_count:
                _merge_sources(item, existing)
                deduped[key] = item
        else:
            deduped[key] = item
    return list(deduped.values())


def _merge_sources(primary: ContentItem, secondary: ContentItem):
    chain = set()
    for entry in (primary, secondary):
        if entry.source_type:
            chain.add(entry.source_type)
        extra = entry.raw_data.get("source_chain")
        if isinstance(extra, list):
            chain.update(extra)
        elif isinstance(extra, str):
            chain.add(extra)
    primary.raw_data["source_chain"] = sorted(chain)


def _enrich_cross_platform_metrics(items: List[ContentItem]):
    if not items:
        return
    per_platform_views = defaultdict(list)
    all_views = []
    for item in items:
        if item.view_count > 0:
            per_platform_views[item.platform].append(item.view_count)
            all_views.append(item.view_count)

    platform_median = {
        platform: (statistics.median(values) if values else 1)
        for platform, values in per_platform_views.items()
    }
    global_median = statistics.median(all_views) if all_views else 1

    for item in items:
        base = platform_median.get(item.platform) or global_median or 1
        normalized_view = item.view_count / base if base else 0

        fans = item.author_fans if item.author_fans > 0 else 5000
        interaction = item.interaction if item.interaction > 0 else item.view_count * 0.02
        engagement_rate = interaction / fans if fans else 0

        item.raw_data["normalized_view"] = round(normalized_view, 2)
        item.raw_data["engagement_rate"] = round(engagement_rate, 4)

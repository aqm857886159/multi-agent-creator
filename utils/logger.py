"""
结构化日志工具
提供清晰的双引擎进度展示
"""

from typing import Any, Dict, List
from core.state import RadarState, TaskItem


def print_phase_header(phase: str):
    """打印阶段标题"""
    phase_map = {
        "init": "系统初始化",
        "discovery": "🔴 引擎1 - 阶段1: 发现博主",
        "collection": "🔴🔵 双引擎并行收集",
        "filtering": "📊 智能筛选与策划"
    }

    title = phase_map.get(phase, phase)
    print(f"\n{'╔'+'═'*58+'╗'}")
    print(f"║  {title:<54}  ║")
    print(f"{'╚'+'═'*58+'╝'}\n")


def print_progress_dashboard(state: RadarState):
    """打印进度仪表盘"""
    youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
    bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])

    engine1_count = state.engine_progress.get("engine1", 0)
    engine2_count = state.engine_progress.get("engine2", 0)

    youtube_influencers = len([i for i in state.discovered_influencers if i.get("platform") == "youtube"])
    bilibili_influencers = len([i for i in state.discovered_influencers if i.get("platform") == "bilibili"])

    total = len(state.candidates)
    target = 50
    percentage = int(total / target * 100) if target > 0 else 0

    print(f"\n{'─'*60}")
    print(f"📊 双引擎进度仪表盘")
    print(f"{'─'*60}")
    print(f"├─ 🔴 引擎1 (头部博主监控):")
    print(f"│  ├─ 发现博主: {len(state.discovered_influencers)} 个")
    print(f"│  │  ├─ YouTube: {youtube_influencers} 个")
    print(f"│  │  └─ Bilibili: {bilibili_influencers} 个")
    print(f"│  └─ 收集内容: {engine1_count} 条")
    print(f"│")
    print(f"├─ 🔵 引擎2 (关键词搜索):")
    print(f"│  └─ 收集内容: {engine2_count} 条")
    print(f"│")
    print(f"├─ 📦 平台分布:")
    print(f"│  ├─ YouTube: {youtube_count} 条")
    print(f"│  └─ Bilibili: {bilibili_count} 条")
    print(f"│")
    print(f"└─ 🎯 总进度: {total}/{target} 条 ({percentage}%)")
    print(f"{'─'*60}\n")


def print_task_selected(task: TaskItem):
    """打印选中的任务"""
    engine_emoji = "🔴" if task.engine == "engine1" else "🔵"

    print(f"{engine_emoji} 选中任务: [{task.engine}] {task.task_type}")
    print(f"   任务ID: {task.task_id}")
    print(f"   平台: {task.platform}")
    print(f"   工具: {task.tool_name}")
    print(f"   优先级: {task.priority}")
    print(f"   理由: {task.reasoning}")


def print_task_result(task: TaskItem, success: bool, summary: str):
    """打印任务执行结果"""
    engine_emoji = "🔴" if task.engine == "engine1" else "🔵"
    status_emoji = "✅" if success else "❌"

    print(f"{engine_emoji} {status_emoji} 任务完成: {task.task_id}")
    print(f"   结果: {summary}")


def print_task_queue_status(state: RadarState):
    """打印任务队列状态"""
    pending = [t for t in state.task_queue if t.status == "pending"]
    in_progress = [t for t in state.task_queue if t.status == "in_progress"]
    completed = len(state.completed_tasks)

    if not pending and not in_progress:
        return

    print(f"\n📋 任务队列状态:")
    print(f"   待执行: {len(pending)} 个")
    print(f"   进行中: {len(in_progress)} 个")
    print(f"   已完成: {completed} 个")

    if pending:
        print(f"\n   下一批待执行任务 (Top 5):")
        for task in sorted(pending, key=lambda t: t.priority, reverse=True)[:5]:
            engine_emoji = "🔴" if task.engine == "engine1" else "🔵"
            print(f"   {engine_emoji} [{task.priority}] {task.task_type} - {task.platform}")


def print_influencer_extraction_result(influencers: List[Dict], total_articles: int):
    """打印博主提取结果"""
    youtube_count = len([i for i in influencers if i.get("platform") == "youtube"])
    bilibili_count = len([i for i in influencers if i.get("platform") == "bilibili"])

    print(f"\n✅ 博主提取完成:")
    print(f"   分析文章数: {total_articles}")
    print(f"   发现博主数: {len(influencers)} 个 (去重后)")
    print(f"   ├─ YouTube: {youtube_count} 个")
    print(f"   └─ Bilibili: {bilibili_count} 个")

    if youtube_count > 0:
        print(f"\n   YouTube 博主 (Top 5):")
        youtube_influencers = [i for i in influencers if i.get("platform") == "youtube"]
        for i, inf in enumerate(youtube_influencers[:5], 1):
            conf = inf.get("confidence", "medium")
            mentions = inf.get("mention_count", 1)
            print(f"   {i}. {inf.get('name')} (提及{mentions}次, 置信度:{conf})")

    if bilibili_count > 0:
        print(f"\n   Bilibili UP主 (Top 5):")
        bilibili_influencers = [i for i in influencers if i.get("platform") == "bilibili"]
        for i, inf in enumerate(bilibili_influencers[:5], 1):
            conf = inf.get("confidence", "medium")
            mentions = inf.get("mention_count", 1)
            print(f"   {i}. {inf.get('name')} (提及{mentions}次, 置信度:{conf})")


def print_filter_result(input_count: int, engine1_count: int, engine2_count: int, output_count: int):
    """打印筛选结果"""
    print(f"\n🧹 智能筛选完成:")
    print(f"   输入: {input_count} 条")
    print(f"   ├─ 🔴 引擎1数据: {engine1_count} 条")
    print(f"   └─ 🔵 引擎2数据: {engine2_count} 条")
    print(f"   输出: {output_count} 条优质内容")


def print_separator():
    """打印分隔线"""
    print(f"\n{'─'*60}\n")

"""
Topic Selector Node - 选题人工交互节点
=====================================

功能: 在 Architect 和 Analyst 之间插入人工审核环节
- 展示 AI 生成的选题
- 允许用户选择感兴趣的选题
- 允许用户添加自定义选题

作者: AI Assistant
日期: 2025-11-27
"""

from typing import Dict, Any, List
from core.state import RadarState, TopicBrief
from core.config import load_settings
from colorama import Fore, Style
import uuid


def run_topic_selector(state: RadarState) -> Dict[str, Any]:
    """
    节点: 选题人工选择器 (Topic Selector with Human-in-the-Loop)

    流程:
    1. 读取配置，决定是否启用交互模式
    2. 交互模式: 展示选题 → 用户选择 → 可选添加自定义
    3. 自动模式: 自动选择 Top N 个选题
    4. 返回最终选定的选题列表
    """

    # 读取配置
    settings = load_settings()
    interaction_config = settings.get("interaction", {})
    enable_interaction = interaction_config.get("enable_topic_selection", True)
    allow_custom = interaction_config.get("allow_custom_topics", True)
    auto_top_n = interaction_config.get("auto_select_top_n", 3)

    # 🔑 根据配置决定模式
    if not enable_interaction:
        print(Fore.YELLOW + f"\n⚡ 配置为自动模式，将自动选择 Top {auto_top_n} 个选题")
        return run_quick_selector(state, auto_select_top_n=auto_top_n)

    # 交互模式
    print("\n" + "="*70)
    print(Fore.CYAN + "🎯 选题审核与选择 (Topic Selection & Review)")
    print(Fore.WHITE + "💡 提示: 可在 config/settings.yaml 中关闭交互模式")
    print("="*70)

    ai_proposals = state.proposals

    if not ai_proposals:
        print(Fore.YELLOW + "\n⚠️ AI 未生成任何选题，您可以手动添加选题。")
        return _handle_manual_topics_only(state)

    # 显示 AI 生成的选题
    print(Fore.GREEN + f"\n📋 AI 已生成 {len(ai_proposals)} 个选题建议:\n")

    for idx, proposal in enumerate(ai_proposals, 1):
        print(Fore.WHITE + f"【选题 {idx}】")
        print(Fore.YELLOW + f"  标题: {proposal.title}")
        print(Fore.CYAN + f"  切入点: {proposal.core_angle}")
        print(Fore.WHITE + f"  推荐理由: {proposal.rationale}")
        print(Fore.MAGENTA + f"  来源策略: {proposal.source_type}")
        print(Fore.WHITE + f"  支撑数据: {len(proposal.reference_data)} 条内容")
        print("-" * 70)

    # 用户选择
    selected_proposals = _interactive_selection(ai_proposals)

    # 询问是否添加自定义选题 (根据配置)
    if allow_custom:
        final_proposals = _ask_for_custom_topics(selected_proposals, state)
    else:
        print(Fore.YELLOW + "\n💡 自定义选题功能已禁用 (配置: allow_custom_topics=false)")
        final_proposals = selected_proposals

    # 显示最终选择
    print(Fore.GREEN + f"\n✅ 最终选定 {len(final_proposals)} 个选题:")
    for idx, proposal in enumerate(final_proposals, 1):
        print(Fore.WHITE + f"  [{idx}] {proposal.title}")

    return {
        "proposals": [p.model_dump() if hasattr(p, 'model_dump') else p for p in final_proposals],
        "logs": state.logs + [f"【人工选择】用户选定 {len(final_proposals)} 个选题"]
    }


def _interactive_selection(ai_proposals: List[TopicBrief]) -> List[TopicBrief]:
    """
    交互式选择 AI 生成的选题

    Returns:
        用户选定的选题列表
    """

    print(Fore.CYAN + "\n💡 请选择您感兴趣的选题 (支持多选):")
    print(Fore.WHITE + "  输入格式:")
    print(Fore.GREEN + "    - 单个: 1")
    print(Fore.GREEN + "    - 多个: 1,3,5")
    print(Fore.GREEN + "    - 全选: all 或 *")
    print(Fore.GREEN + "    - 跳过: 直接回车 (不选任何AI建议)")

    try:
        user_input = input(Fore.YELLOW + "\n请输入选择 (默认全选): " + Fore.WHITE).strip()
    except (EOFError, KeyboardInterrupt):
        print(Fore.YELLOW + "\n⚠️ 未检测到输入，默认全选所有选题")
        user_input = "all"

    # 处理输入
    if not user_input or user_input.lower() in ["all", "*"]:
        print(Fore.GREEN + "✅ 已选择全部选题")
        return ai_proposals

    if user_input.lower() in ["none", "skip", "0"]:
        print(Fore.YELLOW + "⚠️ 未选择任何AI建议")
        return []

    # 解析选择
    selected = []
    try:
        indices = [int(x.strip()) for x in user_input.split(",") if x.strip()]

        for idx in indices:
            if 1 <= idx <= len(ai_proposals):
                selected.append(ai_proposals[idx - 1])
                print(Fore.GREEN + f"  ✓ 已选择: {ai_proposals[idx - 1].title}")
            else:
                print(Fore.RED + f"  ✗ 无效选项: {idx} (范围: 1-{len(ai_proposals)})")

        if not selected:
            print(Fore.YELLOW + "⚠️ 未选择任何有效选项，默认全选")
            return ai_proposals

        return selected

    except ValueError:
        print(Fore.RED + "❌ 输入格式错误，默认全选所有选题")
        return ai_proposals


def _ask_for_custom_topics(
    existing_proposals: List[TopicBrief],
    state: RadarState
) -> List[TopicBrief]:
    """
    询问用户是否添加自定义选题

    Returns:
        合并后的选题列表 (AI选择 + 用户自定义)
    """

    print(Fore.CYAN + "\n📝 是否添加自定义选题?")
    print(Fore.WHITE + "  (输入 'y' 添加，直接回车跳过)")

    try:
        add_custom = input(Fore.YELLOW + "添加自定义选题? (y/N): " + Fore.WHITE).strip().lower()
    except (EOFError, KeyboardInterrupt):
        add_custom = "n"

    if add_custom not in ["y", "yes", "是", "y"]:
        return existing_proposals

    # 收集自定义选题
    custom_topics = []

    print(Fore.GREEN + "\n✏️ 开始添加自定义选题 (输入空白标题结束):\n")

    topic_count = 1
    while True:
        print(Fore.CYAN + f"--- 自定义选题 #{topic_count} ---")

        try:
            title = input(Fore.WHITE + "标题 (必填, 回车结束): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not title:
            break

        try:
            angle = input(Fore.WHITE + "切入点 (可选): ").strip()
        except (EOFError, KeyboardInterrupt):
            angle = ""

        try:
            rationale = input(Fore.WHITE + "选题理由 (可选): ").strip()
        except (EOFError, KeyboardInterrupt):
            rationale = ""

        # 创建自定义选题
        custom_topic = TopicBrief(
            id=f"custom_{uuid.uuid4().hex[:8]}",
            title=title,
            core_angle=angle if angle else f"用户自定义选题: {title}",
            rationale=rationale if rationale else "用户手动添加的选题",
            source_type="user_custom",
            reference_data=[{
                "type": "user_input",
                "target_domains": state.target_domains,
                "session_focus": state.session_focus
            }]
        )

        custom_topics.append(custom_topic)
        print(Fore.GREEN + f"✅ 已添加自定义选题: {title}\n")

        topic_count += 1

    if custom_topics:
        print(Fore.GREEN + f"\n✅ 共添加 {len(custom_topics)} 个自定义选题")
        return existing_proposals + custom_topics
    else:
        print(Fore.YELLOW + "⚠️ 未添加自定义选题")
        return existing_proposals


def _handle_manual_topics_only(state: RadarState) -> Dict[str, Any]:
    """
    处理只有手动添加选题的情况 (AI 未生成任何选题)

    Returns:
        包含用户自定义选题的 state 更新
    """

    print(Fore.CYAN + "\n📝 请手动添加选题:")

    custom_topics = []

    print(Fore.GREEN + "\n✏️ 开始添加选题 (至少添加一个):\n")

    topic_count = 1
    while True:
        print(Fore.CYAN + f"--- 选题 #{topic_count} ---")

        try:
            title = input(Fore.WHITE + "标题 (必填, 回车结束): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not title:
            if topic_count == 1:
                print(Fore.YELLOW + "⚠️ 至少需要添加一个选题，请继续...")
                continue
            else:
                break

        try:
            angle = input(Fore.WHITE + "切入点 (可选): ").strip()
        except (EOFError, KeyboardInterrupt):
            angle = ""

        try:
            rationale = input(Fore.WHITE + "选题理由 (可选): ").strip()
        except (EOFError, KeyboardInterrupt):
            rationale = ""

        # 创建选题
        custom_topic = TopicBrief(
            id=f"manual_{uuid.uuid4().hex[:8]}",
            title=title,
            core_angle=angle if angle else f"手动选题: {title}",
            rationale=rationale if rationale else "用户手动添加",
            source_type="manual_input",
            reference_data=[{
                "type": "manual_input",
                "target_domains": state.target_domains
            }]
        )

        custom_topics.append(custom_topic)
        print(Fore.GREEN + f"✅ 已添加选题: {title}\n")

        topic_count += 1

    if not custom_topics:
        print(Fore.RED + "❌ 未添加任何选题，系统将退出")
        return {
            "proposals": [],
            "logs": state.logs + ["【人工选择】用户未添加任何选题，流程终止"]
        }

    print(Fore.GREEN + f"\n✅ 共添加 {len(custom_topics)} 个选题")

    return {
        "proposals": [t.model_dump() for t in custom_topics],
        "logs": state.logs + [f"【人工选择】用户手动添加 {len(custom_topics)} 个选题"]
    }


# ============================================
# 快速选择模式 (可选功能)
# ============================================

def run_quick_selector(state: RadarState, auto_select_top_n: int = 3) -> Dict[str, Any]:
    """
    快速选择模式: 自动选择 Top N 个选题，跳过交互

    适用场景: 批处理、自动化流程

    Args:
        state: RadarState
        auto_select_top_n: 自动选择前 N 个选题 (默认3个)

    Returns:
        包含选定选题的 state 更新
    """

    print(Fore.YELLOW + f"\n⚡ 快速模式: 自动选择 Top {auto_select_top_n} 个选题")

    ai_proposals = state.proposals

    if not ai_proposals:
        print(Fore.RED + "❌ 无可用选题")
        return {"proposals": [], "logs": state.logs + ["【快速选择】无可用选题"]}

    selected = ai_proposals[:auto_select_top_n]

    print(Fore.GREEN + f"✅ 已自动选择 {len(selected)} 个选题:")
    for idx, proposal in enumerate(selected, 1):
        print(Fore.WHITE + f"  [{idx}] {proposal.title}")

    return {
        "proposals": [p.model_dump() if hasattr(p, 'model_dump') else p for p in selected],
        "logs": state.logs + [f"【快速选择】自动选择 Top {len(selected)} 个选题"]
    }


if __name__ == "__main__":
    # 测试代码
    print("=== Testing Topic Selector ===\n")

    from core.state import RadarState

    # 创建测试选题
    test_proposals = [
        TopicBrief(
            id="test_001",
            title="AI绘图技术革命",
            core_angle="Stable Diffusion vs MidJourney 对比",
            rationale="高热度话题，技术深度足够",
            source_type="viral_hit",
            reference_data=[{"platform": "youtube", "title": "AI Art Tutorial"}]
        ),
        TopicBrief(
            id="test_002",
            title="大模型降本增效实战",
            core_angle="从 GPT-4 迁移到 DeepSeek 的省钱攻略",
            rationale="企业痛点，实用性强",
            source_type="tech_news",
            reference_data=[{"platform": "bilibili", "title": "降本增效"}]
        ),
        TopicBrief(
            id="test_003",
            title="AI Agent 开发指南",
            core_angle="从零构建智能体系统",
            rationale="开发者关注，教育价值高",
            source_type="competitor",
            reference_data=[{"platform": "youtube", "title": "Agent Tutorial"}]
        )
    ]

    # 创建测试 state
    test_state = RadarState(
        target_domains=["AI技术", "内容创作"],
        proposals=[p.model_dump() for p in test_proposals]
    )

    # 运行选择器
    result = run_topic_selector(test_state)

    print("\n=== Result ===")
    print(f"Selected Topics: {len(result['proposals'])}")
    for p in result['proposals']:
        print(f"  - {p['title']}")

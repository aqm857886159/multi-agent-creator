"""
测试新改进模块 - P0/P1/P2/P4

测试内容:
1. P0: PromptManager 提示词管理
2. P2: ToolMasker 动态工具屏蔽
3. P1: ContextCompressor 上下文压缩
4. P4: FeedbackAnalyzer 反馈分析
"""

import sys
import os

# 确保 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_prompt_manager():
    """测试 P0: PromptManager"""
    print("\n" + "="*60)
    print("测试 P0: PromptManager")
    print("="*60)
    
    from core.prompt_manager import (
        get_prompt,
        get_role,
        get_goal,
        get_available_tools,
        get_compression_template,
        get_prompt_manager
    )
    
    # 测试 1: 获取提示词
    print("\n1. 测试获取提示词...")
    planner_prompt = get_prompt("planner", "system")
    assert planner_prompt, "Planner prompt 不应为空"
    assert "规划师" in planner_prompt or "调度" in planner_prompt, "Planner prompt 应包含角色描述"
    print(f"   ✓ Planner prompt 长度: {len(planner_prompt)} 字符")
    
    # 测试 2: 获取角色和目标
    print("\n2. 测试获取角色和目标...")
    role = get_role("keyword_designer")
    goal = get_goal("keyword_designer")
    assert role, "Role 不应为空"
    assert goal, "Goal 不应为空"
    print(f"   ✓ Keyword Designer Role: {role}")
    print(f"   ✓ Keyword Designer Goal: {goal[:50]}...")
    
    # 测试 3: 获取阶段工具
    print("\n3. 测试获取阶段工具...")
    discovery_tools = get_available_tools("discovery")
    collection_tools = get_available_tools("collection")
    print(f"   ✓ Discovery 阶段工具: {discovery_tools}")
    print(f"   ✓ Collection 阶段工具: {collection_tools}")
    assert "web_search" in discovery_tools, "Discovery 阶段应包含 web_search"
    assert "youtube_search" in collection_tools, "Collection 阶段应包含 youtube_search"
    
    # 测试 4: 获取压缩模板
    print("\n4. 测试获取压缩模板...")
    template = get_compression_template("candidates_summary_template")
    print(f"   ✓ 压缩模板存在: {bool(template)}")
    
    # 测试 5: 动态变量替换
    print("\n5. 测试动态变量替换...")
    prompt_with_vars = get_prompt("keyword_designer", "system", topic="AI视频")
    assert "2025" in prompt_with_vars, "应包含当前年份"
    print(f"   ✓ 变量替换成功，包含年份: 2025")
    
    print("\n✅ P0: PromptManager 测试通过!")
    return True


def test_tool_masker():
    """测试 P2: ToolMasker"""
    print("\n" + "="*60)
    print("测试 P2: ToolMasker")
    print("="*60)
    
    from core.tool_masker import (
        get_masked_tools,
        get_tool_descriptions,
        get_tool_hints,
        should_allow_tool,
        get_tool_masker
    )
    from core.state import RadarState
    
    # 创建测试状态
    state = RadarState(
        target_domains=["AI"],
        current_phase="collection"
    )
    
    # 测试 1: 获取阶段工具
    print("\n1. 测试获取阶段工具...")
    tools = get_masked_tools(state)
    print(f"   ✓ Collection 阶段可用工具: {tools}")
    assert "youtube_search" in tools, "Collection 阶段应包含 youtube_search"
    assert "bilibili_search" in tools, "Collection 阶段应包含 bilibili_search"
    
    # 测试 2: Monitor 工具需要博主
    print("\n2. 测试 Monitor 工具前置条件...")
    # 无博主时
    tools_no_influencers = get_masked_tools(state)
    has_monitor = "youtube_monitor" in tools_no_influencers
    print(f"   ✓ 无博主时 youtube_monitor 可用: {has_monitor}")
    
    # 有博主时
    state.discovered_influencers = [{"name": "Test", "platform": "youtube"}]
    tools_with_influencers = get_masked_tools(state)
    has_monitor_now = "youtube_monitor" in tools_with_influencers
    print(f"   ✓ 有博主时 youtube_monitor 可用: {has_monitor_now}")
    
    # 测试 3: 获取工具描述
    print("\n3. 测试获取工具描述...")
    descriptions = get_tool_descriptions(state, format="brief")
    print(f"   ✓ 工具描述 (brief): {descriptions}")
    
    descriptions_md = get_tool_descriptions(state, format="markdown")
    assert "youtube_search" in descriptions_md, "Markdown 描述应包含工具名"
    print(f"   ✓ Markdown 描述长度: {len(descriptions_md)} 字符")
    
    # 测试 4: 获取工具提示
    print("\n4. 测试获取工具提示...")
    hints = get_tool_hints(state)
    print(f"   ✓ 工具提示: {hints if hints else '(无)'}")
    
    # 测试 5: 检查工具是否允许
    print("\n5. 测试检查工具是否允许...")
    allowed, reason = should_allow_tool("youtube_search", state)
    print(f"   ✓ youtube_search 允许: {allowed}, 原因: {reason}")
    
    # 切换到 init 阶段
    state.current_phase = "init"
    allowed_init, reason_init = should_allow_tool("youtube_search", state)
    print(f"   ✓ init 阶段 youtube_search 允许: {allowed_init}, 原因: {reason_init}")
    
    print("\n✅ P2: ToolMasker 测试通过!")
    return True


def test_context_compressor():
    """测试 P1: ContextCompressor"""
    print("\n" + "="*60)
    print("测试 P1: ContextCompressor")
    print("="*60)
    
    from core.context_compressor import (
        compress_candidates,
        compress_influencers,
        compress_tasks,
        compress_errors,
        compress_state,
        should_compress,
        estimate_tokens
    )
    from core.state import RadarState, ContentItem, TaskItem
    
    # 创建测试数据
    candidates = []
    for i in range(30):
        platform = "youtube" if i % 2 == 0 else "bilibili"
        candidates.append(ContentItem(
            platform=platform,
            source_type="keyword_search",
            title=f"测试视频 {i} - {'YouTube' if platform == 'youtube' else 'B站'}",
            url=f"https://example.com/video/{i}",
            author_name=f"作者{i}",
            author_id=str(i),
            publish_time="2025-11-28",  # 添加必需字段
            view_count=10000 * (i + 1),
            interaction=1000 * (i + 1)
        ))
    
    # 测试 1: 压缩候选内容
    print("\n1. 测试压缩候选内容...")
    summary = compress_candidates(candidates)
    print(f"   ✓ 压缩结果:\n{summary}")
    assert "30" in summary, "应显示总数 30"
    assert "YouTube" in summary, "应包含 YouTube"
    assert "Bilibili" in summary, "应包含 Bilibili"
    
    # 测试 2: 压缩博主列表
    print("\n2. 测试压缩博主列表...")
    influencers = [
        {"name": "影视飓风", "platform": "bilibili"},
        {"name": "Two Minute Papers", "platform": "youtube"},
        {"name": "老番茄", "platform": "bilibili"},
    ]
    inf_summary = compress_influencers(influencers)
    print(f"   ✓ 博主摘要:\n{inf_summary}")
    
    # 测试 3: 压缩任务队列
    print("\n3. 测试压缩任务队列...")
    tasks = [
        TaskItem(task_id="1", task_type="search", priority=10, engine="engine1", 
                 platform="youtube", tool_name="youtube_search", status="pending"),
        TaskItem(task_id="2", task_type="search", priority=9, engine="engine2", 
                 platform="bilibili", tool_name="bilibili_search", status="completed"),
    ]
    task_summary = compress_tasks(tasks)
    print(f"   ✓ 任务摘要:\n{task_summary}")
    
    # 测试 4: 压缩错误历史
    print("\n4. 测试压缩错误历史...")
    errors = [
        {"tool_name": "youtube_search", "error_type": "timeout", "error": "请求超时"},
        {"tool_name": "youtube_search", "error_type": "timeout", "error": "请求超时"},
        {"tool_name": "bilibili_search", "error_type": "no_results", "error": "无结果"},
    ]
    error_summary = compress_errors(errors)
    print(f"   ✓ 错误摘要:\n{error_summary}")
    assert "× 2" in error_summary, "应聚合相同错误"
    
    # 测试 5: 压缩整个状态
    print("\n5. 测试压缩整个状态...")
    state = RadarState(
        target_domains=["AI"],
        current_phase="collection",
        candidates=candidates,
        discovered_influencers=influencers,
        task_queue=tasks,
        error_history=errors
    )
    full_summary = compress_state(state)
    print(f"   ✓ 完整状态摘要:\n{full_summary}")
    
    # 测试 6: 判断是否需要压缩
    print("\n6. 测试判断是否需要压缩...")
    needs_compress = should_compress(state)
    print(f"   ✓ 需要压缩: {needs_compress}")
    
    # 测试 7: Token 估算
    print("\n7. 测试 Token 估算...")
    tokens = estimate_tokens(full_summary)
    print(f"   ✓ 估算 Token 数: {tokens}")
    
    print("\n✅ P1: ContextCompressor 测试通过!")
    return True


def test_feedback_analyzer():
    """测试 P4: FeedbackAnalyzer"""
    print("\n" + "="*60)
    print("测试 P4: FeedbackAnalyzer")
    print("="*60)
    
    from core.feedback_analyzer import (
        analyze_result,
        get_retry_suggestion,
        get_success_params,
        get_failure_summary,
        get_analyzer
    )
    
    # 模拟结果对象
    class MockResult:
        def __init__(self, status, data=None, error=None):
            self.status = status
            self.data = data or []
            self.error = error
    
    # 测试 1: 分析成功结果
    print("\n1. 测试分析成功结果...")
    success_result = MockResult("success", data=[{"title": "视频1"}, {"title": "视频2"}])
    analysis = analyze_result(
        tool_name="youtube_search",
        params={"keyword": "AI tutorial", "limit": 10},
        result=success_result
    )
    print(f"   ✓ 成功分析: success={analysis['success']}, count={analysis['result_count']}")
    assert analysis['success'] == True
    assert analysis['result_count'] == 2
    
    # 测试 2: 分析失败结果
    print("\n2. 测试分析失败结果...")
    error_result = MockResult("error", error="Connection timeout")
    error_analysis = analyze_result(
        tool_name="bilibili_search",
        params={"keyword": "AI教程", "limit": 15},
        result=error_result
    )
    print(f"   ✓ 失败分析: success={error_analysis['success']}, error_type={error_analysis.get('error_type', 'N/A')}")
    assert error_analysis['success'] == False
    
    # 测试 3: 获取重试建议
    print("\n3. 测试获取重试建议...")
    suggestion = get_retry_suggestion(
        tool_name="youtube_search",
        error="timeout error occurred",
        original_params={"keyword": "AI", "limit": 20}
    )
    print(f"   ✓ 重试建议: should_retry={suggestion['should_retry']}, reason={suggestion['reason']}")
    if suggestion.get('adjusted_params'):
        print(f"   ✓ 调整后参数: {suggestion['adjusted_params']}")
    
    # 测试 4: 测试无结果场景
    print("\n4. 测试无结果场景...")
    no_result = MockResult("success", data=[])
    no_result_analysis = analyze_result(
        tool_name="bilibili_search",
        params={"keyword": "非常冷门的关键词", "limit": 10},
        result=no_result
    )
    print(f"   ✓ 无结果分析: issues={no_result_analysis['issues']}")
    print(f"   ✓ 建议: {no_result_analysis['suggestions']}")
    
    # 测试 5: 获取失败摘要
    print("\n5. 测试获取失败摘要...")
    summary = get_failure_summary()
    print(f"   ✓ 失败摘要:\n{summary}")
    
    # 测试 6: 获取成功参数
    print("\n6. 测试获取成功参数...")
    success_params = get_success_params("youtube_search")
    print(f"   ✓ 成功参数: {success_params}")
    
    print("\n✅ P4: FeedbackAnalyzer 测试通过!")
    return True


def test_integration():
    """集成测试 - 验证所有模块协同工作"""
    print("\n" + "="*60)
    print("集成测试 - 验证模块协同")
    print("="*60)
    
    from core.state import RadarState, ContentItem
    from core.prompt_manager import build_state_summary, build_error_summary, build_goal_recap
    from core.tool_masker import get_masked_tools, get_tool_hints
    from core.context_compressor import compress_state, should_compress
    
    # 创建一个模拟的运行状态
    state = RadarState(
        target_domains=["AI视频"],
        current_phase="collection",
        session_focus={"priority_topics": ["AI视频生成"]},  # 修复为字典格式
        candidates=[
            ContentItem(
                platform="youtube",
                source_type="keyword_search",
                title="AI Video Generation Tutorial",
                url="https://youtube.com/watch?v=123",
                author_name="TechChannel",
                author_id="UC123",
                publish_time="2025-11-28",  # 添加必需字段
                view_count=50000,
                interaction=5000
            ),
            ContentItem(
                platform="bilibili",
                source_type="keyword_search",
                title="AI视频生成教程",
                url="https://bilibili.com/video/BV123",
                author_name="技术UP主",
                author_id="12345",
                publish_time="2025-11-28",  # 添加必需字段
                view_count=30000,
                interaction=3000
            )
        ],
        discovered_influencers=[
            {"name": "Two Minute Papers", "platform": "youtube", "identifier": "@TwoMinutePapers"}
        ],
        error_history=[
            {"tool_name": "youtube_search", "error": "timeout", "error_type": "timeout"}
        ]
    )
    
    print("\n1. 测试状态摘要构建...")
    state_summary = build_state_summary(state)
    print(f"   ✓ 状态摘要:\n{state_summary}")
    
    print("\n2. 测试错误摘要构建...")
    error_summary = build_error_summary(state)
    print(f"   ✓ 错误摘要:\n{error_summary if error_summary else '(无)'}")
    
    print("\n3. 测试目标提醒构建...")
    goal_recap = build_goal_recap(state, target_items=50)
    print(f"   ✓ 目标提醒:\n{goal_recap}")
    
    print("\n4. 测试工具屏蔽...")
    available_tools = get_masked_tools(state)
    print(f"   ✓ 可用工具: {available_tools}")
    
    print("\n5. 测试工具提示...")
    hints = get_tool_hints(state)
    print(f"   ✓ 工具提示: {hints if hints else '(无)'}")
    
    print("\n6. 测试压缩判断...")
    needs_compress = should_compress(state)
    print(f"   ✓ 需要压缩: {needs_compress}")
    
    if needs_compress:
        compressed = compress_state(state)
        print(f"   ✓ 压缩后摘要:\n{compressed}")
    
    print("\n✅ 集成测试通过!")
    return True


def main():
    """运行所有测试"""
    print("="*60)
    print("开始测试新改进模块")
    print("="*60)
    
    all_passed = True
    
    try:
        all_passed &= test_prompt_manager()
    except Exception as e:
        print(f"\n❌ P0 测试失败: {e}")
        all_passed = False
    
    try:
        all_passed &= test_tool_masker()
    except Exception as e:
        print(f"\n❌ P2 测试失败: {e}")
        all_passed = False
    
    try:
        all_passed &= test_context_compressor()
    except Exception as e:
        print(f"\n❌ P1 测试失败: {e}")
        all_passed = False
    
    try:
        all_passed &= test_feedback_analyzer()
    except Exception as e:
        print(f"\n❌ P4 测试失败: {e}")
        all_passed = False
    
    try:
        all_passed &= test_integration()
    except Exception as e:
        print(f"\n❌ 集成测试失败: {e}")
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️ 部分测试失败，请检查上方错误信息")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


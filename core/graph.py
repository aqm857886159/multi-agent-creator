from langgraph.graph import StateGraph, END
from core.state import RadarState
from nodes import filter, architect, planner, executor, keyword_designer, influencer_extractor, analyst, topic_selector

# Graph Definition
workflow = StateGraph(RadarState)

# Add Nodes
# 🆕 双引擎新增节点
workflow.add_node("keyword_designer", keyword_designer.run_keyword_designer)
workflow.add_node("influencer_extractor", influencer_extractor.run_influencer_extractor)

# 原有节点
workflow.add_node("planner", planner.run_planner)
workflow.add_node("executor", executor.run_executor)
workflow.add_node("filter", filter.run_hybrid_filter)
workflow.add_node("architect", architect.run_architect)

# 🎯 Topic Selector - 人工选题交互节点
workflow.add_node("topic_selector", topic_selector.run_topic_selector)

# 🚀 Analyst Agent - 深度分析智能体
workflow.add_node("analyst", analyst.analyst_node)

# Define Edges
# 🔑 新流程: 从搜索词设计开始
workflow.set_entry_point("keyword_designer")

def keyword_designer_router(state: RadarState):
    """关键词设计节点之后的路由"""
    # 如果有搜索词，进入 Planner 开始执行 Web 搜索
    if state.discovery_queries or state.content_queries:
        return "planner"
    else:
        # 没有生成搜索词，直接进入常规流程
        return "planner"

def planner_router(state: RadarState):
    """Planner 节点之后的路由"""
    # 🔑 优先检查：如果有 Web 搜索结果且还没有提取过博主，立即提取
    # （不管 plan_status 是什么状态）
    if state.leads and not state.discovered_influencers:
        print("🔄 检测到 Web 搜索结果，准备提取博主...")
        return "influencer_extractor"

    # 如果正在执行工具，去 Executor
    if state.plan_status == "executing":
        return "executor"
    # 如果规划完成（收集到足够数据），进入筛选
    elif state.plan_status == "finished":
        return "filter"
    else:
        # 继续规划
        return "planner"

def influencer_extractor_router(state: RadarState):
    """博主提取节点之后的路由"""
    # 提取完博主后，重新进入 Planner 让它规划后续搜索
    return "planner"

# 🔑 新的路由逻辑
workflow.add_conditional_edges(
    "keyword_designer",
    keyword_designer_router,
    {
        "planner": "planner"
    }
)

workflow.add_conditional_edges(
    "planner",
    planner_router,
    {
        "executor": "executor",
        "filter": "filter",
        "planner": "planner",
        "influencer_extractor": "influencer_extractor"
    }
)

workflow.add_conditional_edges(
    "influencer_extractor",
    influencer_extractor_router,
    {
        "planner": "planner"
    }
)

workflow.add_edge("executor", "planner")
workflow.add_edge("filter", "architect")

# 🎯 新流程: Architect → TopicSelector → Analyst → END
# 1. Architect 生成选题
# 2. TopicSelector 人工审核和选择
# 3. Analyst 对选定的选题进行深度分析
workflow.add_edge("architect", "topic_selector")
workflow.add_edge("topic_selector", "analyst")
workflow.add_edge("analyst", END)

app = workflow.compile()

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from core.state import RadarState
from core.llm import get_llm_with_schema
from core.tool_registry import registry
import json
from datetime import datetime

TARGET_TOTAL_ITEMS = 50  # 收集50条高质量内容
MAX_PLAN_STEPS = 50  # 增加规划步数限制以支持更多收集
DISCOVERY_QUERIES = []
DEFAULT_TOPICS = []
TOPIC_TEMPLATES = {}

class ToolCall(BaseModel):
    tool_name: str = Field(..., description="调用的工具名称")
    arguments: Dict[str, Any] = Field(..., description="工具调用参数")
    reasoning: str = Field(..., description="为什么现在需要调用这个工具")

class PlannerOutput(BaseModel):
    thought: str = Field(..., description="对当前情况的分析以及下一步计划")
    action: Optional[ToolCall] = Field(None, description="要执行的工具调用。如果任务完成则为 Null。")
    is_finished: bool = Field(False, description="是否已收集到足够的数据")

def run_planner(state: RadarState) -> Dict[str, Any]:
    print("\n--- 节点: 规划大脑 (Node: Planner) ---")

    # 1. Prepare Context
    tool_schemas = registry.list_tool_schemas()
    scratchpad = state.plan_scratchpad

    # 获取当前日期
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().strftime("%Y")
    current_month = datetime.now().strftime("%Y-%m")
    collected = len(state.candidates)

    # 🔑 增加调试信息：显示当前状态
    print(f"📊 当前进度: 已收集 {collected}/{TARGET_TOTAL_ITEMS} 条")
    print(f"📊 待监控队列: YouTube={len(state.pending_monitors.get('youtube', []))}, "
          f"Bilibili={len(state.pending_monitors.get('bilibili', []))}")
    print(f"📊 已监控数量: YouTube={len(state.monitored_sources.get('youtube', []))}, "
          f"Bilibili={len(state.monitored_sources.get('bilibili', []))}")
    
    if len(state.plan_scratchpad) >= MAX_PLAN_STEPS:
        print("⚠️ 规划达到安全上限，提前进入筛选。")
        return {
            "plan_status": "finished",
            "plan_scratchpad": state.plan_scratchpad,
            "pending_monitors": state.pending_monitors,
            "discovery_history": state.discovery_history
        }

    # 🔑 修复关键问题 1: 优先检查数量，停止条件优先级最高
    if collected >= TARGET_TOTAL_ITEMS:
        print(f"🧠 规划完成: 已收集 {collected} 条素材，准备进入筛选。")
        return {
            "plan_status": "finished",
            "plan_scratchpad": state.plan_scratchpad,
            "pending_monitors": state.pending_monitors,
            "discovery_history": state.discovery_history
        }

    # 检查是否有确定性任务（待监控频道或线索），但要受数量限制
    deterministic_action = _deterministic_plan(state, today_str, current_year, current_month)
    if deterministic_action:
        tool_name, arguments, reasoning = deterministic_action
        print(f"🧠 规划器: {reasoning}")
        print(f"👉 决策: 调用 {tool_name}")
        action = ToolCall(tool_name=tool_name, arguments=arguments, reasoning=reasoning)
        state.plan_scratchpad.append({"tool_call": action.model_dump(), "timestamp": "now"})
        return {
            "plan_status": "executing",
            "plan_scratchpad": state.plan_scratchpad,
            "pending_monitors": state.pending_monitors,
            "discovery_history": state.discovery_history
        }

    # Summarize history
    history_text = ""
    if not scratchpad:
        history_text = "暂无行动记录。"
    else:
        for entry in scratchpad:
            if "tool_call" in entry:
                tc = entry["tool_call"]
                history_text += f"\n[思考]: {tc.get('reasoning', '')}\n"
                history_text += f"[行动]: 调用 {tc['tool_name']} 参数 {tc['arguments']}\n"
            if "tool_result" in entry:
                res = entry["tool_result"]
                history_text += f"[结果]: {res.get('summary', '')} (状态: {res.get('status')})\n"
                if res.get('error'):
                    history_text += f"[错误]: {res.get('error')}\n"

    target = ", ".join(state.target_domains) or ", ".join(state.keywords)

    # 🔑 检查双引擎阶段
    has_discovery_queries = len(state.discovery_queries) > 0
    has_web_results = len(state.leads) > 0
    has_influencers = len(state.discovered_influencers) > 0

    user_prompt = f"""
    目标: 为主题 '{target}' 收集高质量内容。
    当前日期: {today_str} (YYYY-MM-DD)
    当前已收集: {collected} 条，目标至少 {TARGET_TOTAL_ITEMS} 条。

    可用工具:
    {json.dumps(tool_schemas, indent=2, ensure_ascii=False)}

    执行历史:
    {history_text}

    🔑 **双引擎策略状态**:
    - 发现博主搜索词已设计: {"是" if has_discovery_queries else "否"}
    - Web 搜索已执行: {"是" if has_web_results else "否"}
    - 博主已提取: {"是" if has_influencers else "否"}

    {"📋 发现博主搜索词: " + str(state.discovery_queries[:3]) + ("..." if len(state.discovery_queries) > 3 else "") if has_discovery_queries else ""}
    {"📋 已发现博主数量: " + str(len(state.discovered_influencers)) if has_influencers else ""}

    **关键策略**:
    1. **双引擎执行顺序** ⭐⭐⭐ 最重要：
       如果刚开始，必须按以下顺序执行：

       【阶段 1: 发现博主】
       a) 如果 discovery_queries 已设计但 Web 搜索未执行：
          → **立即使用 web_search 搜索 discovery_queries 中的第一个关键词**
          → 目的：找到"博主推荐文章"（如"2025年顶级AI博主"）
          → 示例调用：
             {{"tool_name": "web_search", "arguments": {{"query": "{state.discovery_queries[0] if state.discovery_queries else 'AI博主推荐'}", "limit": 10}}}}

       b) 如果 Web 搜索已完成但博主未提取：
          → 等待 influencer_extractor 节点自动执行（不要自己调用）

       c) 如果博主已提取：
          → 进入阶段 2

       【阶段 2: 内容收集】
       d) 博主发现完成后，才执行 youtube_search / bilibili_search
       e) 或者如果没有发现博主（Web搜索失败），也可以直接执行内容搜索

    2. **搜索策略 (Time-Aware)**:
       - **必须**在关键词中加入日期限定，以确保内容的时效性。
       - 格式示例: "AI News {current_month}", "Python tutorial {current_year}", "Latest tech reviews {today_str}"
       - 如果大词搜索无效，尝试更具体的时间范围或话题，例如 "DeepSeek V3 analysis {current_month}"。
       - **切勿**反复搜索同一个无效的大词。

    2. **语言策略**:
       - 你的目标受众是中文用户，需要同时覆盖中英文平台。
       - **YouTube/Reddit**: 使用英文关键词搜索（如 "AI News", "Python tutorial"）
       - **Bilibili**: 使用中文关键词搜索（如 "AI新闻", "Python教程"）

    3. **平台平衡策略** ⭐ 非常重要：
       - **必须同时尝试 YouTube 和 Bilibili 两个平台**，不要只依赖一个
       - 优先顺序：先执行广泛搜索（youtube_search, bilibili_search），再考虑监控
       - 如果已经执行了 youtube_search，下一步应该执行 bilibili_search 以保持平衡
       - 不要让 pending_monitors 队列"绑架"你的决策，先完成平台覆盖

    4. **工具选择**:
       - 如果某个工具失败了，尝试切换到其他平台
       - 不要死磕一个平台
    
    指令:
    1. 分析历史记录。如果你已经收集到足够的内容（至少 5-10 条高质量条目），设置 is_finished=True。
    2. 如果某个工具失败了，尝试使用不同的参数，或者切换到备用工具（例如：如果 youtube_search 失败，尝试 web_search）。
    3. 刚开始时，优先使用广泛搜索（如 youtube_search, reddit_search, web_search），然后再深入挖掘。
    4. 不要重复执行已经成功的相同工具调用。
    5. 如果发现需要登录但未登录的工具报错，请尝试其他无需登录的工具。
    
    请以 JSON 格式输出你的计划。
    """
    
    try:
        # Use reasoning capability for planning
        plan: PlannerOutput = get_llm_with_schema(
            user_prompt=user_prompt,
            response_model=PlannerOutput,
            capability="reasoning",
            system_prompt=f"你是一个自主调研智能体。当前时间是 {today_str}。请规划下一步行动以收集情报。"
        )
        
        if plan.is_finished:
            print(f"🧠 规划完成: {plan.thought}")
            return {
                "plan_status": "finished",
                "plan_scratchpad": state.plan_scratchpad,
                "pending_monitors": state.pending_monitors,
                "discovery_history": state.discovery_history
            }
        
        if plan.action:
            print(f"🧠 思考: {plan.thought}")
            print(f"👉 决策: 调用 {plan.action.tool_name}")
            
            # Add to scratchpad
            new_entry = {
                "tool_call": plan.action.model_dump(),
                "timestamp": "now" # proper timestamp in real app
            }
            state.plan_scratchpad.append(new_entry)
            
            return {
                "plan_status": "executing", 
                "plan_scratchpad": state.plan_scratchpad,
                "pending_monitors": state.pending_monitors,
                "discovery_history": state.discovery_history
            }
            
        # Fallback
        return {
            "plan_status": "finished",
            "plan_scratchpad": state.plan_scratchpad,
            "pending_monitors": state.pending_monitors,
            "discovery_history": state.discovery_history
        }
        
    except Exception as e:
        print(f"❌ Planner Error: {e}")
        # Fail safe: finish to avoid loops
        return {
            "plan_status": "finished",
            "plan_scratchpad": state.plan_scratchpad,
            "pending_monitors": state.pending_monitors,
            "discovery_history": state.discovery_history
        }

def _deterministic_plan(state: RadarState, today: str, year: str, month: str) -> Optional[Tuple[str, Dict[str, Any], str]]:
    """
    🔑 确定性规划逻辑 - 双引擎策略

    执行顺序：
    1. 顺藤摸瓜：搜索已发现的博主内容（引擎 1 的核心）
    2. 线索跟进：跟进 Web 搜索发现的线索
    3. 监控执行：监控待监控队列中的频道（引擎 1 的持续监控）

    注意：只有两个平台都搜索过后，才执行监控（避免被"绑架"）
    """

    # 🆕 优先级 1: 顺藤摸瓜 - 搜索已发现的博主内容
    influencer_action = _schedule_influencer_search(state, today, year, month)
    if influencer_action:
        return influencer_action

    # 🔑 修复关键问题：只在搜索阶段完成后才执行监控
    # 检查是否两个平台都搜索过了
    youtube_searched = state.platform_search_progress.get("youtube", False)
    bilibili_searched = state.platform_search_progress.get("bilibili", False)

    # 如果还没有完成平台搜索，不执行监控（避免被"绑架"）
    if not (youtube_searched and bilibili_searched):
        return None

    # 优先级 2: 线索跟进
    lead_action = _schedule_lead_follow_up(state)
    if lead_action:
        return lead_action

    # 优先级 3: 监控执行
    action = _schedule_pending_monitor(state)
    if action:
        return action
    return None

AUTO_MONITOR_LIMIT = 2


def _schedule_influencer_search(state: RadarState, today: str, year: str, month: str) -> Optional[Tuple[str, Dict[str, Any], str]]:
    """
    🆕 顺藤摸瓜：针对发现的博主进行搜索（引擎 1 的核心逻辑）

    流程：
    1. 从 discovered_influencers 中找到未搜索的博主
    2. 按优先级排序（高置信度 + 多次提及）
    3. 生成针对性搜索任务
    4. 标记为已搜索
    """
    if not state.discovered_influencers:
        return None

    # 按优先级排序
    confidence_score = {"high": 3, "medium": 2, "low": 1}
    sorted_influencers = sorted(
        state.discovered_influencers,
        key=lambda x: (confidence_score.get(x.confidence, 1), x.mention_count),
        reverse=True
    )

    # 找到第一个未搜索的博主
    for influencer in sorted_influencers:
        if influencer.identifier in state.searched_influencers:
            continue

        # 找到了未搜索的博主
        target_domain = state.target_domains[0] if state.target_domains else ""

        if influencer.platform == "youtube":
            tool_name = "youtube_search"
            keyword = f"{influencer.name} {target_domain}".strip()
            reasoning = f"顺藤摸瓜：搜索顶级博主 {influencer.name} 的 {target_domain} 相关内容"

            # 标记为已搜索
            state.searched_influencers.append(influencer.identifier)

            return (
                tool_name,
                {
                    "keyword": keyword,
                    "limit": 8
                },
                reasoning
            )

        elif influencer.platform == "bilibili":
            tool_name = "bilibili_search"
            keyword = f"{influencer.name} {target_domain}".strip()
            reasoning = f"顺藤摸瓜：搜索顶级UP主 {influencer.name} 的 {target_domain} 相关内容"

            # 标记为已搜索
            state.searched_influencers.append(influencer.identifier)

            return (
                tool_name,
                {
                    "keyword": keyword,
                    "limit": 8
                },
                reasoning
            )

    # 所有博主都搜索完了
    if not state.influencer_search_done:
        state.influencer_search_done = True
        print("✅ 博主搜索阶段完成，所有发现的博主内容已搜索")

    return None


def _schedule_pending_monitor(state: RadarState) -> Optional[Tuple[str, Dict[str, Any], str]]:
    priorities = [
        ("youtube", "youtube_monitor", "channel_url", "执行频道监控：{target}"),
        ("bilibili", "bilibili_monitor", "user_id", "监控 B站 UP主：{target}")
    ]
    for platform, tool_name, arg_key, template in priorities:
        pending = state.pending_monitors.get(platform, [])
        autoruns = state.monitor_autoruns.get(platform, 0)
        if pending and autoruns < AUTO_MONITOR_LIMIT:
            target = pending.pop(0)
            args = {arg_key: target}
            reasoning = template.format(target=target)
            state.monitor_autoruns[platform] = autoruns + 1
            return tool_name, args, reasoning
    return None


def _schedule_lead_follow_up(state: RadarState) -> Optional[Tuple[str, Dict[str, Any], str]]:
    if not state.leads:
        return None

    priority_platforms = state.session_focus.get("priority_platforms") or [
        "youtube", "bilibili"
    ]

    for idx, lead in enumerate(state.leads):
        keyword = _select_lead_keyword(lead)
        if not keyword:
            continue

        platform = _detect_lead_platform(lead, priority_platforms)
        tool_name = _platform_search_tool(platform)
        if not tool_name:
            continue

        state.leads.pop(idx)
        state.logs.append(f"【线索】跟进 {platform} 搜索 {keyword}")
        reasoning = f"线索《{lead.title}》提示 {platform} 有相关内容，尝试关键词: {keyword}"
        arguments = {
            "keyword": keyword,
            "limit": 8,
            "topic_hint": lead.topic_hint
        }
        return tool_name, arguments, reasoning

    return None


def _detect_lead_platform(lead, priority_platforms: List[str]) -> str:
    url = (lead.url or "").lower()
    platform_markers = {
        "bilibili": ["bilibili.com", "b站"],
        "youtube": ["youtube.com", "youtu.be"]
    }

    for platform, markers in platform_markers.items():
        if any(marker in url for marker in markers):
            return platform

    for tag in lead.tags:
        low = tag.lower()
        for platform, markers in platform_markers.items():
            if any(marker in low for marker in markers):
                return platform

    return (priority_platforms or ["bilibili"])[0]


def _platform_search_tool(platform: str) -> Optional[str]:
    mapping = {
        "bilibili": "bilibili_search",
        "youtube": "youtube_search"
    }
    return mapping.get(platform)


def _select_lead_keyword(lead) -> str:
    for tag in lead.tags:
        clean = tag.strip()
        if clean:
            return clean[:60]
    title = (lead.title or "").strip()
    if title:
        return title[:60]
    return ""


def _schedule_initial_platform_search(state: RadarState) -> Optional[Tuple[str, Dict[str, Any], str]]:
    return None

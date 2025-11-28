"""
规划大脑 v2.2 - 任务调度器
核心改进:
1. 任务队列化管理
2. 智能任务选择（平台平衡 + 引擎平衡）
3. 结构化日志输出
4. 🔑 P1: 集成 PlatformBalancer 强制平衡
5. 🔑 P1: 复述机制（目标提醒）
6. 🔑 P2: 动态工具屏蔽 (ToolMasker)
7. 🔑 P1: 上下文压缩 (ContextCompressor)
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from core.state import RadarState, TaskItem, TopicSearchQueries
from core.llm import get_llm_with_schema
from core.platform_balancer import (
    get_platform_balancer, 
    get_balance_summary,
    BalanceMode
)
# 🔑 P2: 动态工具屏蔽
from core.tool_masker import (
    get_masked_tools,
    get_tool_descriptions,
    get_tool_hints
)
# 🔑 P1: 上下文压缩
from core.context_compressor import (
    compress_state,
    should_compress
)
# 🔑 P0: Prompt 管理
from core.prompt_manager import (
    get_prompt,
    build_goal_recap,
    build_state_summary,
    build_error_summary
)
from datetime import datetime
import sys
import os

# 添加 utils 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.logger import (
    print_phase_header,
    print_progress_dashboard,
    print_task_selected,
    print_task_queue_status,
    print_separator
)

TARGET_TOTAL_ITEMS = 50
MAX_PLAN_STEPS = 50

# 🔑 P1: 全局平台平衡器
_balancer = get_platform_balancer()


class ToolCall(BaseModel):
    tool_name: str = Field(..., description="调用的工具名称")
    arguments: Dict[str, Any] = Field(..., description="工具调用参数")
    reasoning: str = Field(..., description="为什么现在需要调用这个工具")


class PlannerOutput(BaseModel):
    thought: str = Field(..., description="对当前情况的分析")
    action: Optional[ToolCall] = Field(None, description="要执行的工具调用")
    is_finished: bool = Field(False, description="是否已收集到足够的数据")


def run_planner(state: RadarState) -> Dict[str, Any]:
    """
    规划器 v2.1 - 任务调度器

    核心逻辑:
    1. 阶段管理 (init → discovery → collection → filtering)
    2. 任务队列初始化
    3. 智能任务选择
    4. 结构化日志输出
    5. 🔑 P1: 复述机制（目标提醒）
    6. 🔑 P1: 错误历史参考
    """
    collected = len(state.candidates)

    # 🔑 P1: 复述机制 - 每次迭代打印目标提醒（Manus最佳实践）
    _print_goal_recap(state, collected)

    # 只在初始化或达到目标时打印详细仪表盘
    if state.current_phase == "init" or collected >= TARGET_TOTAL_ITEMS:
        print(f"\n{'='*60}")
        print(f"📍 {state.current_phase.upper()}")
        print_progress_dashboard(state)

    # ============ 阶段1: 初始化任务队列 ============
    if state.current_phase == "init":
        if state.topic_queries:
            _initialize_task_queue(state)
            state.current_phase = "discovery"
            print("✅ 初始化完成\n")
            return {
                "plan_status": "planning",
                "current_phase": "discovery",
                "task_queue": state.task_queue
            }
        else:
            return {"plan_status": "planning"}

    # ============ 阶段2: 检查完成条件 ============
    if collected >= TARGET_TOTAL_ITEMS:
        print(f"🎯 目标达成: 已收集 {collected}/{TARGET_TOTAL_ITEMS} 条")
        state.current_phase = "filtering"
        return {
            "plan_status": "finished",
            "current_phase": "filtering"
        }

    if len(state.plan_scratchpad) >= MAX_PLAN_STEPS:
        print(f"⚠️ 达到最大步数限制 ({MAX_PLAN_STEPS}), 进入筛选")
        state.current_phase = "filtering"
        return {
            "plan_status": "finished",
            "current_phase": "filtering"
        }

    # ============ 阶段2.5: 自适应反馈检查 ============
    # 🔑 检查上一个任务的质量反馈，决定是否需要重试
    if state.feedback_enabled and state.quality_checks:
        retry_task = _check_quality_feedback_and_retry(state)
        if retry_task:
            # 有重试任务，优先执行
            next_task = retry_task
        else:
            # 没有重试任务，正常选择
            next_task = _select_next_task(state)
    else:
        # 反馈系统关闭或无检查历史，正常选择
        next_task = _select_next_task(state)

    # ============ 阶段3: 任务执行 ============
    # next_task = _select_next_task(state)  # 移除重复

    if next_task:
        # 简化任务日志
        engine_icon = "🔴" if next_task.engine == "engine1" else "🔵"
        print(f"{engine_icon} {next_task.tool_name} | {next_task.arguments.get('query') or next_task.arguments.get('keyword', '')[:40]}")

        # 标记为进行中
        next_task.status = "in_progress"

        # 创建tool_call
        action = ToolCall(
            tool_name=next_task.tool_name,
            arguments=next_task.arguments,
            reasoning=next_task.reasoning
        )

        # 添加任务ID到reasoning中（用于后续标记完成）
        action.reasoning = f"[{next_task.task_id}] {action.reasoning}"

        state.plan_scratchpad.append({"tool_call": action.model_dump()})

        return {
            "plan_status": "executing",
            "task_queue": state.task_queue,
            "plan_scratchpad": state.plan_scratchpad  # 🔑 必须返回以保存修改！
        }

    # ============ 阶段4: 动态任务生成 ============
    # 如果队列为空但还没达到目标，让LLM补充任务
    if collected < TARGET_TOTAL_ITEMS:
        print("📋 任务队列为空，尝试生成新任务...")
        new_tasks = _llm_generate_tasks(state)

        if new_tasks:
            added_count = _add_tasks_with_deduplication(state, new_tasks)
            print(f"✅ 生成 {added_count} 个新任务")
            return {
                "plan_status": "planning",
                "task_queue": state.task_queue
            }

    # ============ 阶段5: 无任务可执行，结束 ============
    print("✅ 所有任务已完成，进入筛选阶段")
    state.current_phase = "filtering"
    return {
        "plan_status": "finished",
        "current_phase": "filtering"
    }


def _is_duplicate_task(task: TaskItem, state: RadarState) -> bool:
    """
    检查任务是否重复

    策略:
    1. 检查 task_id 是否已在队列或完成列表中
    2. 检查相同 tool_name + arguments 组合是否已存在

    Returns:
        True if duplicate, False if unique
    """
    # 检查1: task_id已完成
    if task.task_id in state.completed_tasks:
        return True

    # 检查2: task_id已在队列中
    existing_ids = {t.task_id for t in state.task_queue}
    if task.task_id in existing_ids:
        return True

    # 检查3: 相同工具+参数组合（防止参数完全相同的重复任务）
    for existing_task in state.task_queue:
        if (existing_task.tool_name == task.tool_name and
            existing_task.arguments == task.arguments and
            existing_task.status in ["pending", "in_progress"]):
            return True

    return False


def _add_tasks_with_deduplication(state: RadarState, new_tasks: List[TaskItem]) -> int:
    """
    添加任务到队列，自动去重

    Returns:
        实际添加的任务数量
    """
    added_count = 0
    duplicate_count = 0

    for task in new_tasks:
        if _is_duplicate_task(task, state):
            duplicate_count += 1
            print(f"   ⚠️ 跳过重复任务: {task.task_id}")
        else:
            state.task_queue.append(task)
            added_count += 1

    if duplicate_count > 0:
        print(f"   🔁 去重: 跳过 {duplicate_count} 个重复任务，新增 {added_count} 个")

    return added_count


def _initialize_task_queue(state: RadarState):
    """
    初始化任务队列

    策略:
    1. 优先级: discovery (发现博主) > content_search (关键词搜索)
    2. 中英文配对: 每个主题生成4个任务
    3. 平台轮换: YouTube和Bilibili交替
    """
    tasks = []
    priority = 100  # 从高到低

    print("\n🔧 初始化任务队列...")

    for topic_query in state.topic_queries:
        topic = topic_query.get("topic", "unknown")

        # ========== 引擎1: 发现博主任务 ==========
        # 优先级最高

        # 任务1: Web搜索 - 英文（YouTube博主）
        tasks.append(TaskItem(
            task_id=f"web_search_{topic}_en",
            task_type="discovery",
            priority=priority,
            engine="engine1",
            platform="youtube",
            tool_name="web_search",
            arguments={
                "query": topic_query.get("discovery_query_en"),
                "limit": 10
            },
            status="pending",
            reasoning=f"🔴 [引擎1-发现博主] Web搜索: {topic} (英文) → 发现YouTube博主"
        ))
        priority -= 1

        # 任务2: Web搜索 - 中文（Bilibili博主）
        tasks.append(TaskItem(
            task_id=f"web_search_{topic}_zh",
            task_type="discovery",
            priority=priority,
            engine="engine1",
            platform="bilibili",
            tool_name="web_search",
            arguments={
                "query": topic_query.get("discovery_query_zh"),
                "limit": 10
            },
            status="pending",
            reasoning=f"🔴 [引擎1-发现博主] Web搜索: {topic} (中文) → 发现Bilibili UP主"
        ))
        priority -= 1

        # ========== 引擎2: 关键词搜索任务 ==========
        # 优先级略低

        # 任务3: YouTube内容搜索
        tasks.append(TaskItem(
            task_id=f"youtube_search_{topic}",
            task_type="content_search",
            priority=priority - 20,  # 低于发现博主
            engine="engine2",
            platform="youtube",
            tool_name="youtube_search",
            arguments={
                "keyword": topic_query.get("content_query_en"),
                "limit": 10
            },
            status="pending",
            reasoning=f"🔵 [引擎2-关键词搜索] YouTube搜索: {topic}"
        ))

        # 任务4: Bilibili内容搜索
        tasks.append(TaskItem(
            task_id=f"bilibili_search_{topic}",
            task_type="content_search",
            priority=priority - 20,
            engine="engine2",
            platform="bilibili",
            tool_name="bilibili_search",
            arguments={
                "keyword": topic_query.get("content_query_zh"),
                "limit": 10
            },
            status="pending",
            reasoning=f"🔵 [引擎2-关键词搜索] Bilibili搜索: {topic}"
        ))

        priority -= 30  # 下一个主题的优先级更低

    state.task_queue = tasks

    # 统计
    engine1_tasks = len([t for t in tasks if t.engine == "engine1"])
    engine2_tasks = len([t for t in tasks if t.engine == "engine2"])
    youtube_tasks = len([t for t in tasks if t.platform == "youtube"])
    bilibili_tasks = len([t for t in tasks if t.platform == "bilibili"])

    print(f"   📋 任务: {len(tasks)} 个 (🔴{engine1_tasks} 🔵{engine2_tasks} | YT:{youtube_tasks} BL:{bilibili_tasks})")


def _select_next_task(state: RadarState) -> Optional[TaskItem]:
    """
    智能任务选择 v2.1
    
    🔑 P1 改进: 使用 PlatformBalancer 进行更智能的平衡

    策略:
    1. 平台平衡: 使用 PlatformBalancer（自适应模式）
    2. 引擎平衡: 如果引擎1比引擎2多10条，优先选引擎2任务
    3. 优先级排序: 在满足平衡的前提下，选择最高优先级任务
    4. 动态生成顺藤摸瓜任务
    """
    # 获取待执行任务
    pending_tasks = [t for t in state.task_queue if t.status == "pending"]

    if not pending_tasks:
        # 🔑 检查是否有博主需要"顺藤摸瓜"
        influencer_tasks = _generate_influencer_search_tasks(state)
        if influencer_tasks:
            added_count = _add_tasks_with_deduplication(state, influencer_tasks)
            if added_count > 0:
                # 返回第一个新添加的任务
                return next((t for t in state.task_queue if t.status == "pending"), None)
        return None

    # ========== 策略1: 平台平衡（使用 PlatformBalancer）==========
    # 获取平台统计
    stats = _balancer.get_stats(state.candidates, state.task_queue)
    
    # 获取可用平台
    available_platforms = list(set(t.platform for t in pending_tasks if t.platform in ["youtube", "bilibili"]))
    
    # 让平衡器决定优先平台
    preferred_platform = _balancer.select_platform(stats, available_platforms)
    
    if preferred_platform:
        platform_tasks = [t for t in pending_tasks if t.platform == preferred_platform]
        if platform_tasks:
            selected = max(platform_tasks, key=lambda t: t.priority)
            print(f"   ⚖️ 平台平衡 → {preferred_platform.upper()} (YT:{stats.youtube_count} BL:{stats.bilibili_count})")
            _balancer.record_execution(preferred_platform)
            return selected

    # ========== 策略2: 引擎平衡 ==========
    engine1_count = state.engine_progress.get("engine1", 0)
    engine2_count = state.engine_progress.get("engine2", 0)

    if engine1_count > engine2_count + 10:
        engine2_tasks = [t for t in pending_tasks if t.engine == "engine2"]
        if engine2_tasks:
            selected = max(engine2_tasks, key=lambda t: t.priority)
            print(f"   ⚖️ 引擎平衡 → 引擎2 (E1:{engine1_count} > E2:{engine2_count})")
            _balancer.record_execution(selected.platform)
            return selected

    if engine2_count > engine1_count + 10:
        engine1_tasks = [t for t in pending_tasks if t.engine == "engine1"]
        if engine1_tasks:
            selected = max(engine1_tasks, key=lambda t: t.priority)
            print(f"   ⚖️ 引擎平衡 → 引擎1 (E2:{engine2_count} > E1:{engine1_count})")
            _balancer.record_execution(selected.platform)
            return selected

    # ========== 策略3: 默认优先级 ==========
    selected = max(pending_tasks, key=lambda t: t.priority)
    _balancer.record_execution(selected.platform)
    return selected


def _check_quality_feedback_and_retry(state: RadarState) -> Optional[TaskItem]:
    """
    🔑 自适应反馈循环：检查质量反馈并生成重试任务

    逻辑：
    1. 读取最后一个质量检查结果
    2. 如果不通过且建议调整 → 创建重试任务
    3. 应用adjustment_plan中的参数调整
    4. 护栏：最多重试3次，每个失败任务只重试1次

    Returns:
        TaskItem if需要重试, None otherwise
    """
    if not state.quality_checks:
        return None

    # 获取最后一个质量检查
    last_check = state.quality_checks[-1]

    # 只处理失败的检查
    if last_check["passed"]:
        return None

    # 只处理建议调整的情况
    if last_check["suggested_action"] not in ["adjust_params", "retry"]:
        return None

    # 🔑 检查这个质量检查是否已经被处理过
    check_id = last_check.get("timestamp", "")
    if not check_id:
        return None

    # 使用一个新的状态字段记录已处理的检查
    if not hasattr(state, 'processed_quality_checks'):
        state.processed_quality_checks = []

    if check_id in state.processed_quality_checks:
        return None  # 这个检查已经处理过了

    # 标记这个检查为已处理
    state.processed_quality_checks.append(check_id)

    # 生成重试任务ID
    tool_name = last_check["tool_name"]
    tool_args = last_check["tool_args"]
    retry_key = f"retry_{tool_name}_{hash(str(tool_args))}"

    # 🔑 护栏2: 全局重试次数限制
    if state.retry_count >= 3:
        print(f"   ⚠️ 已达全局重试上限({state.retry_count}次)，停止自适应反馈")
        state.feedback_enabled = False
        return None

    # 显示反馈信息
    print(f"\n🔄 自适应反馈: 检测到 {tool_name} 质量问题")
    print(f"   分数: {last_check['quality_score']:.2f}")
    print(f"   问题: {last_check['issues'][0] if last_check['issues'] else '未知'}")
    print(f"   建议: {last_check['suggested_action']}")

    # 🔑 应用调整方案
    adjusted_params = tool_args.copy()
    if last_check.get("adjustment_plan"):
        adjusted_params.update(last_check["adjustment_plan"])
        print(f"   🔧 参数调整: {last_check['adjustment_plan']}")

    # 推断平台和引擎
    platform = _infer_platform(tool_name)
    engine = _infer_engine_from_check(last_check)

    # 创建重试任务
    retry_task = TaskItem(
        task_id=retry_key,
        task_type="quality_retry",
        priority=999,  # 最高优先级
        engine=engine,
        platform=platform,
        tool_name=tool_name,
        arguments=adjusted_params,
        status="pending",
        reasoning=f"🔄 [质量反馈重试] {last_check['reasoning'][:80]}..."
    )

    # 🔑 只增加重试计数，不立即标记为completed
    # completed标记由executor在任务真正执行完成后处理
    state.retry_count += 1

    print(f"   ✅ 创建重试任务 (第{state.retry_count}次全局重试)")

    return retry_task


def _infer_platform(tool_name: str) -> str:
    """从工具名推断平台"""
    if "youtube" in tool_name:
        return "youtube"
    elif "bilibili" in tool_name:
        return "bilibili"
    else:
        return "both"


def _infer_engine_from_check(check: Dict[str, Any]) -> str:
    """从质量检查中推断引擎"""
    reasoning = check.get("reasoning", "")
    if "engine1" in reasoning.lower() or "博主" in reasoning or "influencer" in reasoning.lower():
        return "engine1"
    else:
        return "engine2"


def _is_english(text: str) -> bool:
    """检测文本是否主要是英文"""
    if not text:
        return False
    # 简单检测：如果超过 70% 是 ASCII 字符，认为是英文
    ascii_count = sum(1 for c in text if ord(c) < 128)
    return ascii_count / len(text) > 0.7

def _is_chinese(text: str) -> bool:
    """检测文本是否主要是中文"""
    if not text:
        return False
    # 检测中文字符
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return chinese_count / len(text) > 0.3


def _generate_influencer_search_tasks(state: RadarState) -> List[TaskItem]:
    """
    生成"顺藤摸瓜"任务
    为已发现但未搜索的博主创建搜索任务
    """
    if not state.discovered_influencers:
        return []

    print(f"\n🔍 动态生成博主任务: 发现{len(state.discovered_influencers)}个博主")

    tasks = []
    searched_ids = set(state.searched_influencers)

    # 按置信度和提及次数排序
    confidence_score = {"high": 3, "medium": 2, "low": 1}
    sorted_influencers = sorted(
        state.discovered_influencers,
        key=lambda x: (confidence_score.get(x.get("confidence", "medium"), 1), x.get("mention_count", 1)),
        reverse=True
    )

    # 只为前5个未搜索的博主生成任务
    count = 0
    for idx, influencer in enumerate(sorted_influencers, 1):
        if count >= 5:
            break

        identifier = influencer.get("identifier", "")
        name = influencer.get("name", "")
        platform = influencer.get("platform", "")
        confidence = influencer.get("confidence", "medium")

        print(f"   [{idx}] {name} ({platform}, {confidence}) - identifier: {identifier[:30] if identifier else 'N/A'}")

        if identifier in searched_ids:
            print(f"       ⏭️ 已搜索过，跳过")
            continue

        if not name or not platform:
            print(f"       ⚠️ 缺少name或platform，跳过")
            continue

        # 🔑 生成搜索关键词 - 根据平台使用对应语言
        # 避免混合语言导致搜索结果不佳
        target_domain = state.target_domains[0] if state.target_domains else ""
        
        if platform == "youtube":
            # YouTube: 纯英文搜索词
            # 如果博主名是英文，直接用；如果是中文，需要翻译或使用英文关键词
            keyword = f"{name} {target_domain}".strip() if _is_english(name) else f"{name}"
        else:
            # Bilibili: 纯中文搜索词
            # 使用中文关键词
            keyword = f"{name} {target_domain}".strip() if _is_chinese(target_domain) else f"{name} 最新视频"

        tool_name = "youtube_search" if platform == "youtube" else "bilibili_search"

        # 🔑 根据置信度调整优先级
        confidence = influencer.get("confidence", "medium")
        base_priority = 60
        if confidence == "high":
            priority_offset = 10  # 优先级70
        elif confidence == "medium":
            priority_offset = 0   # 优先级60
        else:  # low
            priority_offset = -15  # 优先级45（低于Engine2）

        task = TaskItem(
            task_id=f"influencer_search_{platform}_{name}",
            task_type="influencer_search",
            priority=base_priority + priority_offset,
            engine="engine1",
            platform=platform,
            tool_name=tool_name,
            arguments={
                "keyword": keyword,
                "limit": 8,
                "from_influencer": identifier,
                "influencer_name": name
            },
            status="pending",
            reasoning=f"🔴 [引擎1-顺藤摸瓜-{confidence}] 搜索博主: {name} ({platform})"
        )

        tasks.append(task)
        count += 1

        # 标记为已搜索
        state.searched_influencers.append(identifier)

    if tasks:
        print(f"   🌿 顺藤摸瓜: +{len(tasks)} 博主任务")

    return tasks


def _llm_generate_tasks(state: RadarState) -> List[TaskItem]:
    """
    LLM动态生成任务（兜底方案）
    当任务队列为空但目标未达成时调用
    
    🔑 P3: 集成 Skills 框架 + PromptManager，注入专业知识到 prompt
    """
    from skills import get_skill_context
    from core.prompt_manager import get_prompt, build_state_summary, build_error_summary
    
    # 获取当前搜索主题
    topic = state.session_focus or "AI"
    
    # 🔑 根据当前状态匹配相关 Skills
    context_hint = f"{topic} youtube bilibili 搜索 筛选"
    skill_context = get_skill_context(context_hint, max_skills=2)
    
    # 🔑 使用 PromptManager 构建状态摘要和错误摘要
    state_summary = build_state_summary(state)
    error_summary = build_error_summary(state, max_errors=3)
    
    # 构建 prompt
    collected = len(state.candidates)
    youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
    bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
    
    # 🔑 使用 PromptManager 获取基础提示词
    base_prompt = get_prompt("task_generator", "system", topic=topic)
    
    system_prompt = f"""{base_prompt}

## 专业知识参考
{skill_context}

## 当前状态
{state_summary}

## 历史错误（避免重复）
{error_summary if error_summary else "无"}

## 任务要求
1. 平台平衡：优先补充数量较少的平台 (YouTube: {youtube_count}, Bilibili: {bilibili_count})
2. 关键词多样：避免重复已搜索的词
3. 语言纯净：YouTube纯英文，Bilibili纯中文，禁止混合
"""

    user_prompt = f"""基于主题「{topic}」，生成 2-4 个搜索任务。

已搜索的关键词（避免重复）：
{[t.arguments.get('query', t.arguments.get('keyword', '')) for t in state.task_queue[:10]]}

请返回 JSON 格式的任务列表：
[
  {{"platform": "youtube", "query": "纯英文搜索词", "reason": "原因"}},
  {{"platform": "bilibili", "query": "纯中文搜索词", "reason": "原因"}}
]
"""

    try:
        # 调用 LLM 生成任务
        from core.llm import get_llm_with_schema
        from pydantic import BaseModel, Field
        from typing import List as ListType
        
        class TaskSuggestion(BaseModel):
            platform: str = Field(..., description="平台: youtube 或 bilibili")
            query: str = Field(..., description="搜索关键词")
            reason: str = Field(..., description="选择原因")
        
        class TaskSuggestions(BaseModel):
            tasks: ListType[TaskSuggestion] = Field(..., description="建议的任务列表")
        
        # 🔑 修复: get_llm_with_schema 直接返回结果，不是返回 LLM 对象
        result = get_llm_with_schema(
            user_prompt=user_prompt,
            response_model=TaskSuggestions,
            system_prompt=system_prompt,
            capability="fast"
        )
        
        # 转换为 TaskItem
        new_tasks = []
        for i, suggestion in enumerate(result.tasks):
            tool_name = f"{suggestion.platform}_search"
            task = TaskItem(
                task_id=f"llm_gen_{len(state.task_queue)}_{i}",
                tool_name=tool_name,
                engine="engine2",  # LLM 生成的任务归入引擎2
                platform=suggestion.platform,
                priority=60,  # 中等优先级
                arguments={
                    "query" if suggestion.platform == "youtube" else "keyword": suggestion.query,
                    "limit": 10,
                    "days": 30
                },
                status="pending",
                reasoning=f"🤖 [LLM生成] {suggestion.reason}"
            )
            new_tasks.append(task)
        
        print(f"   🤖 LLM 生成 {len(new_tasks)} 个任务")
        return new_tasks
        
    except Exception as e:
        print(f"   ⚠️ LLM 任务生成失败: {e}")
        return []


# ============ P1: 复述机制 ============

def _print_goal_recap(state: RadarState, collected: int):
    """
    🔑 P1: 复述机制 - 每次迭代打印目标提醒
    
    Manus 最佳实践：通过不断复述目标，将注意力引导到任务焦点
    避免 LLM 在长任务链中"迷失方向"
    
    🔑 P0: 使用 PromptManager 的 build_goal_recap
    """
    # 只在非初始化阶段且有一定进度时打印
    if state.current_phase == "init":
        return
    
    # 每 5 次迭代打印一次完整提醒
    step_count = len(state.plan_scratchpad)
    
    if step_count > 0 and step_count % 5 == 0:
        # 🔑 使用 PromptManager 构建目标提醒
        recap = build_goal_recap(state, TARGET_TOTAL_ITEMS)
        print(f"\n{recap}")
        
        # 🔑 P2: 显示当前可用工具提示
        tool_hints = get_tool_hints(state)
        if tool_hints:
            print(f"\n💡 工具提示:")
            print(f"   {tool_hints}")
        
        print()


def _build_error_context(state: RadarState, limit: int = 3) -> str:
    """
    🔑 P1: 构建错误上下文供 LLM 参考
    
    返回最近的错误记录摘要，帮助 LLM 避免重复犯错
    """
    if not state.error_history:
        return ""
    
    recent_errors = state.error_history[-limit:]
    lines = ["【最近错误记录 - 请避免重复】"]
    
    for err in recent_errors:
        tool = err.get("tool_name", "unknown")
        error_type = err.get("error_type", "Error")
        error_msg = err.get("error", "")[:80]
        lines.append(f"- {tool}: [{error_type}] {error_msg}")
    
    return "\n".join(lines)


def get_planner_context_summary(state: RadarState) -> str:
    """
    🔑 P1: 生成规划器上下文摘要
    
    用于在 LLM 调用时附加到 prompt 末尾，实现复述机制
    
    🔑 P1: 使用 ContextCompressor 进行智能压缩
    """
    # 🔑 P1: 判断是否需要压缩
    if should_compress(state):
        # 使用压缩器生成摘要
        summary = compress_state(state)
    else:
        # 简单摘要
        collected = len(state.candidates)
        youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
        bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
        
        # 平衡状态
        balance_summary = get_balance_summary(state.candidates, state.task_queue)
        
        # 任务队列状态
        pending_count = len([t for t in state.task_queue if t.status == "pending"])
        
        summary = f"""
【当前状态摘要】
- 目标: 收集 {TARGET_TOTAL_ITEMS} 条内容
- 进度: {collected}/{TARGET_TOTAL_ITEMS} ({collected*100//TARGET_TOTAL_ITEMS if TARGET_TOTAL_ITEMS > 0 else 0}%)
- {balance_summary}
- 待执行任务: {pending_count} 个
- 当前阶段: {state.current_phase}
"""
    
    # 添加错误上下文
    error_context = _build_error_context(state)
    if error_context:
        summary += f"\n{error_context}"
    
    # 🔑 P2: 添加可用工具信息
    available_tools = get_masked_tools(state)
    if available_tools:
        summary += f"\n【可用工具】{', '.join(available_tools)}"
    
    return summary

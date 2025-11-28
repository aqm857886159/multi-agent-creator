from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from urllib.parse import urlparse
from core.state import RadarState, ContentItem, LeadItem
from core.tool_registry import registry
from core.tool_loader import load_tools_from_config
from core.quality_gate import AdaptiveQualityGate, FeedbackLoopManager, FeedbackLoopGuard
from core.memory import compress_candidates_if_needed
from core.state_reducers import (
    append_reducer,
    merge_dict_reducer,
    dedupe_append_reducer,
    capped_append_reducer
)
# 🔑 P4: 反馈分析器
from core.feedback_analyzer import (
    analyze_result,
    get_retry_suggestion
)
# 🔑 P1: 上下文压缩
from core.context_compressor import compress_candidates

# 🔑 P0: 候选内容压缩阈值
CANDIDATES_COMPRESS_THRESHOLD = 100

DEFAULT_PARAMS = {
    "web_search": {"limit": 20, "depth": "advanced"},  # 🔑 15→20 (低成本扩容)
    "youtube_search": {"limit": 15, "days": 60, "scan_limit": 50},  # 🔑 快速扫描50条，详细处理15条，时间放宽到60天
    "bilibili_search": {"limit": 15, "days": 60, "sort_by": "comprehensive", "fetch_size": 100},  # 🔑 时间放宽到60天
    "youtube_monitor": {"limit": 15, "days": 60},  # 🔑 10→15，时间放宽到60天
    "bilibili_monitor": {"limit": 15},  # 🔑 10→15
}

# 🔑 自适应质量门（全局单例，使用fast model降低成本）
_quality_gate = AdaptiveQualityGate(use_fast_model=True)
_feedback_manager = FeedbackLoopManager(max_retries=2, max_cost=0.5)

def run_executor(state: RadarState) -> Dict[str, Any]:
    # 静默加载工具（不打印日志）
    load_tools_from_config()

    # Get last planned action
    if not state.plan_scratchpad:
        return {"plan_status": "planning"} # Should not happen

    last_entry = state.plan_scratchpad[-1]
    if "tool_result" in last_entry:
        # Already executed
        return {"plan_status": "planning"}

    tool_call = last_entry.get("tool_call")
    if not tool_call:
        return {"plan_status": "planning"}
        
    tool_name = tool_call["tool_name"]
    tool_args = tool_call["arguments"]
    _apply_default_params(tool_name, tool_args)
    
    tool_def = registry.get_tool(tool_name)
    if not tool_def or not tool_def.func:
        error_msg = f"Tool {tool_name} not found or not executable."
        print(f"❌ {error_msg}")
        last_entry["tool_result"] = {"status": "error", "error": error_msg}
        return {"plan_status": "planning", "plan_scratchpad": state.plan_scratchpad}
        
    try:
        print(f"🔨 执行: {tool_name}...")

        # 🔑 新增: 从reasoning中提取任务ID和引擎信息
        reasoning = tool_call.get("reasoning", "")
        task_id = _extract_task_id(reasoning)
        engine = _extract_engine(reasoning)

        # Execute the tool wrapper
        result = tool_def.func(tool_args)

        # result is a ToolResult object
        print(f"✅ 结果: {result.summary}")

        # 🔑 自适应质量检查（智能判断结果质量）
        if state.feedback_enabled and result.status == "success":
            quality_result = _run_quality_check(
                state=state,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=result,
                reasoning=reasoning
            )

            # 如果质量不通过且建议调整，记录反馈但继续（由planner决定是否重试）
            if not quality_result.passed:
                print(f"   ⚠️ 质量检查: {quality_result.suggested_action} - {quality_result.reasoning[:100]}")
                if quality_result.issues:
                    for issue in quality_result.issues[:2]:  # 只显示前2个问题
                        print(f"     • {issue}")

                # 记录质量检查结果到状态（供planner参考）
                state.quality_checks.append({
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "result_summary": result.summary,
                    "quality_score": quality_result.score,
                    "passed": quality_result.passed,
                    "issues": quality_result.issues,
                    "suggested_action": quality_result.suggested_action,
                    "adjustment_plan": quality_result.adjustment_plan,
                    "reasoning": quality_result.reasoning,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                print(f"   ✅ 质量检查: 通过 (分数: {quality_result.score:.2f})")

        # Save result to scratchpad
        last_entry["tool_result"] = result.model_dump()

        # Ingest data into state.candidates if applicable
        topic_hint = tool_args.get("topic_hint")
        new_count = 0
        if tool_name == "web_search" and isinstance(result.data, list):
            lead_count = _ingest_leads(state, result.data, topic_hint, tool_name)
            if lead_count:
                state.logs.append(f"【线索】{tool_name} 追加 {lead_count} 条 leads")

        if result.status == "success":
            new_items = []
            if result.data and isinstance(result.data, list):
                for item in result.data:
                    try:
                        if isinstance(item, dict):
                            if topic_hint:
                                item.setdefault("raw_data", {})
                                item["raw_data"]["topic_hint"] = topic_hint
                            if "source_type" not in item:
                                item["source_type"] = tool_name
                            if "platform" not in item:
                                item["platform"] = "web"
                            if "publish_time" not in item:
                                item["publish_time"] = datetime.now().strftime("%Y%m%d")

                            # 🔑 新增: 标记引擎来源
                            item.setdefault("raw_data", {})
                            item["raw_data"]["engine"] = engine

                            # 🔑 新增: 标记是否来自顺藤摸瓜
                            if tool_args.get("from_influencer"):
                                item["raw_data"]["from_influencer_search"] = True
                                item["raw_data"]["source_influencer"] = tool_args.get("influencer_name", "")

                            ci = ContentItem(**item)
                            new_items.append(ci)
                    except Exception:
                        pass

            if new_items:
                state.candidates.extend(new_items)
                new_count = len(new_items)

                # 🔑 新增: 更新引擎进度
                if engine in ["engine1", "engine2"]:
                    state.engine_progress[engine] = state.engine_progress.get(engine, 0) + new_count

                engine_icon = "🔴" if engine == "engine1" else "🔵"
                print(f"   {engine_icon} +{new_count} 条")
                _harvest_sources(state, new_items, tool_name)
                _update_topic_progress(state, topic_hint, new_count)
                _log_collection_summary(state, tool_name, topic_hint, new_count, result.summary)
                
                # 🔑 P0: 检查是否需要压缩候选内容到外部存储
                _maybe_compress_candidates(state)
            else:
                _log_collection_summary(state, tool_name, topic_hint, 0, "未获取到可用的数据")
            _mark_platform_search_done(state, tool_name)

            # 🔑 修复关键问题 4: 监控完成后，标记为已监控
            _mark_source_monitored(state, tool_name, tool_args)
        else:
            _log_collection_summary(state, tool_name, topic_hint, 0, f"执行失败: {result.summary}")

        # 🔑 新增: 标记任务完成
        if task_id:
            _mark_task_completed(state, task_id)

        return {
            "plan_status": "planning", # Go back to planner
            "plan_scratchpad": state.plan_scratchpad,
            "candidates": state.candidates,
            "leads": state.leads,
            "pending_monitors": state.pending_monitors,
            "discovered_sources": state.discovered_sources,
            "task_queue": state.task_queue,  # 🔑 新增: 返回更新后的任务队列
            "completed_tasks": state.completed_tasks,  # 🔑 新增
            "engine_progress": state.engine_progress,  # 🔑 新增
            "candidates_externalized": state.candidates_externalized  # 🔑 P0: 返回外部化标记
        }
        
    except Exception as e:
        print(f"❌ Execution Error: {e}")
        last_entry["tool_result"] = {"status": "error", "error": str(e)}
        
        # 🔑 P4: 使用 FeedbackAnalyzer 分析错误
        retry_suggestion = get_retry_suggestion(
            tool_name=tool_name,
            error=str(e),
            original_params=tool_args,
            state=state
        )
        
        # 🔑 P0: 记录错误到 error_history（Manus最佳实践：保留失败尝试）
        error_record = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now().isoformat(),
            "reasoning": tool_call.get("reasoning", "")[:200],  # 保留部分reasoning便于分析
            # 🔑 P4: 添加重试建议
            "retry_suggestion": retry_suggestion
        }
        state.error_history.append(error_record)
        
        # 🔑 P4: 打印重试建议
        if retry_suggestion.get("should_retry"):
            print(f"   💡 建议: {retry_suggestion.get('reason', '')}")
            if retry_suggestion.get("adjusted_params"):
                print(f"   🔧 调整参数: {retry_suggestion.get('adjusted_params')}")
            if retry_suggestion.get("wait_seconds", 0) > 0:
                print(f"   ⏱️ 建议等待: {retry_suggestion.get('wait_seconds')}秒")
        else:
            print(f"   ⚠️ 不建议重试: {retry_suggestion.get('reason', '')}")
            if retry_suggestion.get("alternative_tool"):
                print(f"   🔄 可尝试: {retry_suggestion.get('alternative_tool')}")
        
        print(f"   📝 错误已记录到 error_history (共 {len(state.error_history)} 条)")
        
        return {
            "plan_status": "planning",
            "leads": state.leads,
            "pending_monitors": state.pending_monitors,
            "discovered_sources": state.discovered_sources,
            "error_history": state.error_history  # 🔑 返回更新后的错误历史
        }

def _apply_default_params(tool_name: str, tool_args: Dict[str, Any]):
    defaults = DEFAULT_PARAMS.get(tool_name)
    if not defaults:
        return
    for key, default_value in defaults.items():
        current = tool_args.get(key)
        if isinstance(default_value, (int, float)):
            if current is None or current < default_value:
                tool_args[key] = default_value
        else:
            if not current:
                tool_args[key] = default_value

def _harvest_sources(state: RadarState, items: list, source_label: Optional[str] = None):
    for ci in items:
        url = (ci.url or "").strip()
        if not url:
            continue
        lower_url = url.lower()
        
        # Track generic web domains
        domain = urlparse(url).netloc
        if domain:
            web_list = state.discovered_sources.setdefault("web", [])
            if domain not in web_list:
                web_list.append(domain)
                state.logs.append(f"【发现】新增站点 {domain}")
        
        # YouTube video -> derive channel
        if ci.platform == "youtube" or "youtube.com" in lower_url:
            channel_url = None
            if ci.author_id:
                channel_url = f"https://www.youtube.com/channel/{ci.author_id}"
            else:
                channel_url = _extract_youtube_channel(lower_url)
            if channel_url:
                _enqueue_source(state, "youtube", channel_url)
        
        # Bilibili UP 主
        if ci.platform == "bilibili" or "bilibili.com" in lower_url:
            mid = ci.author_id or ci.raw_data.get("author_id") if isinstance(ci.raw_data, dict) else None
            if mid:
                _enqueue_source(state, "bilibili", str(mid))

        if source_label:
            chain = ci.raw_data.get("source_chain")
            if isinstance(chain, list):
                if source_label not in chain:
                    chain.append(source_label)
            elif chain:
                ci.raw_data["source_chain"] = list({chain, source_label})
            else:
                ci.raw_data["source_chain"] = [source_label]

def _extract_youtube_channel(url: str) -> str:
    if "/channel/" in url:
        return "https://www.youtube.com" + url.split("youtube.com")[1].split("?")[0]
    if "/@" in url:
        idx = url.index("/@")
        return "https://www.youtube.com" + url[idx:].split("?")[0]
    if "/user/" in url:
        idx = url.index("/user/")
        return "https://www.youtube.com" + url[idx:].split("?")[0]
    return ""

def _enqueue_source(state: RadarState, platform: str, identifier: str):
    if not identifier:
        return
    identifier = identifier.rstrip("/")
    # Ensure dicts exist
    if platform not in state.pending_monitors:
        state.pending_monitors[platform] = []
    if platform not in state.monitoring_list:
        state.monitoring_list[platform] = []
    if platform not in state.discovered_sources:
        state.discovered_sources[platform] = []
    if platform not in state.monitored_sources:
        state.monitored_sources[platform] = []

    # 🔑 修复关键问题 2: 检查是否已经监控过，避免重复监控
    if identifier in state.monitored_sources[platform]:
        return  # 已经监控过，跳过

    if identifier in state.pending_monitors[platform]:
        return  # 已经在待监控队列中

    # 🔑 修复关键问题 3: 限制待监控队列长度，防止失控
    MAX_PENDING_PER_PLATFORM = 10
    if len(state.pending_monitors[platform]) >= MAX_PENDING_PER_PLATFORM:
        return  # 队列已满，不再添加

    if identifier in state.monitoring_list[platform]:
        # Already part of whitelist, ensure pending
        state.pending_monitors[platform].append(identifier)
        return
    if identifier not in state.discovered_sources[platform]:
        state.discovered_sources[platform].append(identifier)
    state.pending_monitors[platform].append(identifier)
    state.logs.append(f"【发现】加入{platform}待监控：{identifier}")

def _update_topic_progress(state: RadarState, topic_hint: Any, delta: int):
    if delta <= 0:
        return
    topic = topic_hint or "general"
    state.topic_progress.setdefault(topic, 0)
    state.topic_progress[topic] += delta

def _log_collection_summary(state: RadarState, tool_name: str, topic_hint: Any, delta: int, summary: str):
    topic = topic_hint or "general"
    target = state.topic_targets.get(topic)
    progress = state.topic_progress.get(topic, 0)
    if target:
        msg = f"【采集】{tool_name} -> {topic} (+{delta}) 累计 {progress}/{target} | {summary}"
    else:
        msg = f"【采集】{tool_name} -> {topic} (+{delta}) 累计 {progress} | {summary}"
    state.logs.append(msg)


def _mark_platform_search_done(state: RadarState, tool_name: str):
    mapping = {
        "youtube_search": "youtube",
        "bilibili_search": "bilibili"
    }
    platform = mapping.get(tool_name)
    if platform:
        state.platform_search_progress[platform] = True


def _mark_source_monitored(state: RadarState, tool_name: str, tool_args: Dict[str, Any]):
    """
    🔑 修复关键问题 4: 监控完成后，将频道标记为已监控，避免重复监控
    """
    monitor_mapping = {
        "youtube_monitor": ("youtube", "channel_url"),
        "bilibili_monitor": ("bilibili", "user_id")
    }

    if tool_name in monitor_mapping:
        platform, arg_key = monitor_mapping[tool_name]
        identifier = tool_args.get(arg_key)
        if identifier:
            identifier = identifier.rstrip("/")
            if platform not in state.monitored_sources:
                state.monitored_sources[platform] = []
            if identifier not in state.monitored_sources[platform]:
                state.monitored_sources[platform].append(identifier)
                print(f"✓ 标记 {platform} 频道已监控: {identifier}")


def _ingest_leads(state: RadarState, raw_items: list, topic_hint: Any, source_tool: str) -> int:
    """
    Store generic web search hits as lightweight leads for downstream planner use.
    """
    added = 0
    seen_urls = {lead.url for lead in state.leads}
    topic = topic_hint or "general"

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or item.get("name") or "").strip()
        url = (item.get("url") or item.get("href") or "").strip()
        snippet = (item.get("content") or item.get("summary") or item.get("description") or "").strip()
        source = item.get("source") or source_tool

        if not title and not url:
            continue
        if url and url in seen_urls:
            continue

        tags = _extract_lead_tags(title, snippet)
        lead = LeadItem(
            title=title or url,
            url=url or f"-/{hash(title)}",
            snippet=snippet[:500],
            source=source,
            topic_hint=topic,
            tags=tags
        )
        state.leads.append(lead)
        seen_urls.add(lead.url)
        added += 1

    return added


def _extract_lead_tags(title: str, snippet: str) -> List[str]:
    """
    Quick heuristics to capture potential creator names or keywords from web hits.
    """
    tags = set()
    text = f"{title} {snippet}".strip()
    if not text:
        return []

    # @handles
    tags.update(re.findall(r"@([\w\-]+)", text))
    # 《作品》 or “引号”
    tags.update(re.findall(r"《([^》]{2,25})》", text))
    tags.update(re.findall(r"“([^”]{2,25})”", text))

    # Split by separators to capture candidate names (limit length)
    for part in re.split(r"[|｜\-—–:：]", title):
        clean = part.strip()
        if 2 <= len(clean) <= 24:
            tags.add(clean)

    return [t for t in tags if t]


def _run_quality_check(
    state: RadarState,
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_result: Any,
    reasoning: str
):
    """
    运行质量检查（智能判断）

    根据工具类型和预期构建智能检查
    """
    # 构建期望描述（基于reasoning和工具类型）
    expectation = _build_expectation(tool_name, tool_args, reasoning, state)

    # 构建上下文
    context = {
        "target_domains": state.target_domains,
        "current_candidates_count": len(state.candidates),
        "current_phase": state.current_phase,
        "recent_quality_checks": state.quality_checks[-3:] if len(state.quality_checks) > 0 else []
    }

    # 调用质量门
    try:
        quality_result = _quality_gate.check_quality(
            tool_name=tool_name,
            tool_params=tool_args,
            tool_result=tool_result,
            expectation=expectation,
            context=context
        )
        return quality_result
    except Exception as e:
        print(f"   ⚠️ 质量检查异常: {e}")
        # 返回默认通过
        from core.quality_gate import QualityCheckResult
        return QualityCheckResult(
            passed=True,
            confidence=0.5,
            score=0.7,
            suggested_action="continue",
            reasoning=f"质量检查异常，默认通过: {e}"
        )


def _build_expectation(
    tool_name: str,
    tool_args: Dict[str, Any],
    reasoning: str,
    state: RadarState
) -> str:
    """
    智能构建期望描述（通用化）

    基于工具类型、参数和reasoning自动生成期望
    """
    # 提取主题（从keyword或query参数）
    topic = tool_args.get("keyword") or tool_args.get("query") or ""

    # 从reasoning中提取引擎和任务类型
    if "发现博主" in reasoning or "discovery" in reasoning.lower():
        task_type = "发现相关博主"
    elif "顺藤摸瓜" in reasoning or "influencer" in reasoning.lower():
        task_type = f"搜索博主'{tool_args.get('influencer_name', '未知')}' 的相关内容"
    elif "监控" in reasoning or "monitor" in reasoning.lower():
        task_type = "监控博主的最新视频"
    else:
        task_type = "搜索相关视频内容"

    # 构建期望
    if "web_search" in tool_name:
        return f"{task_type}，期望找到推荐优质博主的文章，主题: {topic}"
    elif "search" in tool_name:
        platform = "YouTube" if "youtube" in tool_name else "Bilibili"
        return f"在{platform}上{task_type}，期望返回高质量、相关性强的视频，主题: {topic}"
    elif "monitor" in tool_name:
        platform = "YouTube" if "youtube" in tool_name else "Bilibili"
        return f"监控{platform}博主的最新内容，期望返回该博主的近期视频"
    else:
        return f"{task_type}，主题: {topic}"


def _extract_task_id(reasoning: str) -> Optional[str]:
    """从reasoning中提取任务ID"""
    # 格式: [task_id] reasoning...
    match = re.match(r"\[([^\]]+)\]", reasoning)
    if match:
        return match.group(1)
    return None


def _extract_engine(reasoning: str) -> str:
    """从reasoning中提取引擎标识"""
    if "engine1" in reasoning.lower() or "引擎1" in reasoning or "顺藤摸瓜" in reasoning:
        return "engine1"
    elif "engine2" in reasoning.lower() or "引擎2" in reasoning or "关键词搜索" in reasoning:
        return "engine2"
    return "unknown"


def _mark_task_completed(state: RadarState, task_id: str):
    """标记任务为已完成"""
    for task in state.task_queue:
        if task.task_id == task_id:
            task.status = "completed"
            if task_id not in state.completed_tasks:
                state.completed_tasks.append(task_id)
            break


def _maybe_compress_candidates(state: RadarState):
    """
    🔑 P0: 检查并压缩候选内容到外部存储
    
    当候选内容超过阈值时，将完整数据存储到文件系统，
    内存中只保留轻量引用，减少 LLM 上下文负担。
    """
    if state.candidates_externalized:
        # 已经压缩过，不重复处理
        return
    
    if len(state.candidates) < CANDIDATES_COMPRESS_THRESHOLD:
        # 未达到阈值，不压缩
        return
    
    try:
        # 转换为字典列表（FileMemory 需要字典格式）
        candidates_dict = [c.model_dump() for c in state.candidates]
        
        # 压缩并存储
        compressed, was_compressed = compress_candidates_if_needed(
            candidates_dict, 
            threshold=CANDIDATES_COMPRESS_THRESHOLD
        )
        
        if was_compressed:
            # 更新状态：用压缩引用替换完整数据
            # 注意：这里我们保留原始 ContentItem 对象，但标记已外部化
            # 完整数据已存储到 data/memory/candidates/
            state.candidates_externalized = True
            print(f"   💾 候选内容已外部化存储 ({len(state.candidates)} 条)")
            state.logs.append(f"【存储】{len(state.candidates)} 条候选内容已外部化到文件系统")
    except Exception as e:
        # 压缩失败不影响主流程
        print(f"   ⚠️ 外部化存储失败: {e}")


def get_error_summary_for_planner(state: RadarState, limit: int = 3) -> str:
    """
    🔑 P0: 生成错误摘要供 Planner 参考
    
    返回最近的错误记录摘要，帮助 LLM 避免重复犯错。
    """
    if not state.error_history:
        return ""
    
    recent_errors = state.error_history[-limit:]
    summary_lines = ["【最近错误记录】"]
    
    for err in recent_errors:
        tool = err.get("tool_name", "unknown")
        error_type = err.get("error_type", "Error")
        error_msg = err.get("error", "")[:100]
        summary_lines.append(f"- {tool}: {error_type} - {error_msg}")
    
    summary_lines.append("请避免重复上述失败的操作。")
    return "\n".join(summary_lines)


# ============ P3: Reducer 辅助函数 ============

def _dedupe_candidates(existing: List[ContentItem], new_items: List[ContentItem]) -> List[ContentItem]:
    """
    🔑 P3: 使用 Reducer 模式去重候选内容
    
    按 URL 去重，避免重复添加相同内容
    """
    existing_urls = set(c.url for c in existing)
    unique_new = [item for item in new_items if item.url not in existing_urls]
    return unique_new


def _safe_extend_candidates(state: RadarState, new_items: List[ContentItem]) -> int:
    """
    🔑 P3: 安全扩展候选内容列表
    
    使用 Reducer 模式：
    1. 自动去重
    2. 返回实际添加数量
    """
    unique_items = _dedupe_candidates(state.candidates, new_items)
    state.candidates.extend(unique_items)
    return len(unique_items)


def _safe_append_error(state: RadarState, error_record: Dict[str, Any], max_errors: int = 50):
    """
    🔑 P3: 安全追加错误记录
    
    使用 capped_append_reducer 模式，限制最大数量
    """
    state.error_history = capped_append_reducer(
        state.error_history, 
        [error_record], 
        max_size=max_errors
    )


def _safe_merge_progress(state: RadarState, engine: str, count: int):
    """
    🔑 P3: 安全合并引擎进度
    
    使用 merge_dict_reducer 模式
    """
    current = state.engine_progress.get(engine, 0)
    state.engine_progress = merge_dict_reducer(
        state.engine_progress,
        {engine: current + count}
    )

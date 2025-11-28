"""
分级日志系统 - 简洁清晰的输出

日志级别：
- SILENT: 无输出
- MINIMAL: 只显示关键进度（推荐生产环境）
- NORMAL: 默认，显示主要步骤
- VERBOSE: 详细调试信息

使用方式：
    from utils.logger import log_progress, log_step, log_debug, set_log_level, LogLevel
    
    set_log_level(LogLevel.MINIMAL)  # 设置日志级别
    log_progress("开始采集")  # 进度信息
    log_step("执行 youtube_search")  # 步骤信息
    log_debug("返回 15 条结果")  # 调试信息
"""

import os
import sys
from enum import IntEnum
from typing import Any, Dict, List, Optional
from datetime import datetime

# ============ 日志级别 ============

class LogLevel(IntEnum):
    SILENT = 0    # 无输出
    MINIMAL = 1   # 只显示关键进度
    NORMAL = 2    # 默认，显示主要步骤
    VERBOSE = 3   # 详细调试信息

# 从环境变量读取日志级别，默认 NORMAL
_LOG_LEVEL = LogLevel(int(os.getenv("LOG_LEVEL", "2")))

# 是否使用 emoji（Windows 兼容性）
_USE_EMOJI = os.getenv("LOG_EMOJI", "1") == "1"

def set_log_level(level: LogLevel):
    """设置日志级别"""
    global _LOG_LEVEL
    _LOG_LEVEL = level

def get_log_level() -> LogLevel:
    """获取当前日志级别"""
    return _LOG_LEVEL

def set_emoji(enabled: bool):
    """设置是否使用 emoji"""
    global _USE_EMOJI
    _USE_EMOJI = enabled

# ============ 安全输出 ============

def _safe_print(msg: str):
    """安全打印，处理 Windows 编码问题"""
    try:
        print(msg)
    except UnicodeEncodeError:
        # 移除 emoji，使用纯文本
        import re
        clean_msg = re.sub(r'[^\x00-\x7F]+', '', msg)
        print(clean_msg)

def _emoji(emoji_char: str, fallback: str = "") -> str:
    """根据设置返回 emoji 或 fallback"""
    return emoji_char if _USE_EMOJI else fallback

# ============ 分级日志函数 ============

def log_critical(msg: str):
    """关键信息 - 始终显示（错误、异常）"""
    _safe_print(f"[!] {msg}")

def log_progress(msg: str):
    """进度信息 - MINIMAL 及以上（阶段性进展）"""
    if _LOG_LEVEL >= LogLevel.MINIMAL:
        _safe_print(f">>> {msg}")

def log_step(msg: str):
    """步骤信息 - NORMAL 及以上（具体操作）"""
    if _LOG_LEVEL >= LogLevel.NORMAL:
        _safe_print(f"    {msg}")

def log_debug(msg: str):
    """调试信息 - VERBOSE 及以上（详细数据）"""
    if _LOG_LEVEL >= LogLevel.VERBOSE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        _safe_print(f"    [{timestamp}] {msg}")

def log_warn(msg: str):
    """警告信息 - NORMAL 及以上"""
    if _LOG_LEVEL >= LogLevel.NORMAL:
        _safe_print(f"    [WARN] {msg}")

def log_error(msg: str):
    """错误信息 - 始终显示"""
    _safe_print(f"[ERROR] {msg}")

# ============ 结构化输出 ============

def print_phase_header(phase: str):
    """打印阶段标题 - MINIMAL 及以上"""
    if _LOG_LEVEL < LogLevel.MINIMAL:
        return
        
    phase_map = {
        "init": "初始化",
        "discovery": f"{_emoji('🔴', '[E1]')} 引擎1 - 发现博主",
        "collection": f"{_emoji('🔴🔵', '[E1+E2]')} 双引擎并行收集",
        "filtering": f"{_emoji('📊', '[F]')} 智能筛选与策划",
        "complete": f"{_emoji('✅', '[OK]')} 完成"
    }
    
    title = phase_map.get(phase, phase)
    _safe_print(f"\n{'='*50}")
    _safe_print(f"  {title}")
    _safe_print(f"{'='*50}")

def print_progress_compact(collected: int, target: int, yt: int, bl: int):
    """紧凑的进度显示 - MINIMAL 及以上"""
    if _LOG_LEVEL < LogLevel.MINIMAL:
        return
        
    pct = collected * 100 // target if target > 0 else 0
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    _safe_print(f">>> [{bar}] {collected}/{target} ({pct}%) | YT:{yt} BL:{bl}")

def print_tool_result(tool: str, success: bool, count: int = 0, msg: str = ""):
    """工具执行结果 - NORMAL 及以上"""
    if _LOG_LEVEL < LogLevel.NORMAL:
        return
        
    status = _emoji("✅", "[OK]") if success else _emoji("❌", "[FAIL]")
    result = f"+{count}" if count > 0 else (msg[:40] if msg else "")
    _safe_print(f"    {status} {tool}: {result}")

def print_quality_summary(relevance: float, threshold: float, passed: bool):
    """质量检查摘要 - NORMAL 及以上"""
    if _LOG_LEVEL < LogLevel.NORMAL:
        return
        
    status = _emoji("✅", "PASS") if passed else _emoji("⚠️", "WARN")
    _safe_print(f"    {status} 相关性: {relevance:.0%} (阈值: {threshold:.0%})")

def print_separator():
    """打印分隔线 - NORMAL 及以上"""
    if _LOG_LEVEL >= LogLevel.NORMAL:
        _safe_print(f"{'─'*50}")

# ============ 兼容旧 API（逐步迁移） ============

def print_progress_dashboard(state):
    """打印进度仪表盘 - 简化版"""
    if _LOG_LEVEL < LogLevel.NORMAL:
        return
        
    from core.state import RadarState
    if not isinstance(state, RadarState):
        return
        
    youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
    bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
    total = len(state.candidates)
    target = 50
    
    print_progress_compact(total, target, youtube_count, bilibili_count)
    
    # VERBOSE 模式下显示详细信息
    if _LOG_LEVEL >= LogLevel.VERBOSE:
        engine1_count = state.engine_progress.get("engine1", 0)
        engine2_count = state.engine_progress.get("engine2", 0)
        log_debug(f"引擎1: {engine1_count} 条, 引擎2: {engine2_count} 条")
        log_debug(f"发现博主: {len(state.discovered_influencers)} 个")

def print_task_selected(task):
    """打印选中的任务 - 简化版"""
    if _LOG_LEVEL < LogLevel.NORMAL:
        return
        
    engine = _emoji("🔴", "E1") if task.engine == "engine1" else _emoji("🔵", "E2")
    _safe_print(f">>> {engine} 执行: {task.tool_name} @ {task.platform}")
    
    if _LOG_LEVEL >= LogLevel.VERBOSE:
        log_debug(f"任务ID: {task.task_id}")
        log_debug(f"优先级: {task.priority}")
        log_debug(f"理由: {task.reasoning}")

def print_task_result(task, success: bool, summary: str):
    """打印任务执行结果 - 简化版"""
    print_tool_result(task.tool_name, success, msg=summary)

def print_task_queue_status(state):
    """打印任务队列状态 - 简化版"""
    if _LOG_LEVEL < LogLevel.VERBOSE:
        return
        
    from core.state import RadarState
    if not isinstance(state, RadarState):
        return
        
    pending = len([t for t in state.task_queue if t.status == "pending"])
    completed = len(state.completed_tasks)
    
    log_debug(f"任务队列: {pending} 待执行, {completed} 已完成")

def print_influencer_extraction_result(influencers: List[Dict], total_articles: int):
    """打印博主提取结果 - 简化版"""
    if _LOG_LEVEL < LogLevel.NORMAL:
        return
        
    youtube_count = len([i for i in influencers if i.get("platform") == "youtube"])
    bilibili_count = len([i for i in influencers if i.get("platform") == "bilibili"])
    
    log_progress(f"博主提取: {len(influencers)} 个 (YT:{youtube_count} BL:{bilibili_count})")
    
    if _LOG_LEVEL >= LogLevel.VERBOSE:
        for inf in influencers[:5]:
            log_debug(f"  - {inf.get('name')} @ {inf.get('platform')}")

def print_filter_result(input_count: int, engine1_count: int, engine2_count: int, output_count: int):
    """打印筛选结果 - 简化版"""
    if _LOG_LEVEL < LogLevel.MINIMAL:
        return
        
    log_progress(f"筛选: {input_count} 条 → {output_count} 条")
    
    if _LOG_LEVEL >= LogLevel.VERBOSE:
        log_debug(f"引擎1: {engine1_count}, 引擎2: {engine2_count}")


# ============ 新增：一次性打印最终摘要 ============

def print_final_summary(
    total_collected: int,
    youtube_count: int,
    bilibili_count: int,
    filtered_count: int,
    proposals_count: int,
    analysis_count: int,
    duration_seconds: float
):
    """打印最终摘要 - MINIMAL 及以上"""
    if _LOG_LEVEL < LogLevel.MINIMAL:
        return
    
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    
    _safe_print(f"\n{'='*50}")
    _safe_print(f"  {_emoji('🎉', '[DONE]')} 任务完成")
    _safe_print(f"{'='*50}")
    _safe_print(f"  采集: {total_collected} 条 (YT:{youtube_count} BL:{bilibili_count})")
    _safe_print(f"  筛选: {filtered_count} 条优质内容")
    _safe_print(f"  产出: {proposals_count} 个选题, {analysis_count} 份分析")
    _safe_print(f"  耗时: {minutes}分{seconds}秒")
    _safe_print(f"{'='*50}\n")

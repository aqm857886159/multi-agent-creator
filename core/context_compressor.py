"""
上下文压缩器 - 智能压缩 RadarState 以减少 Token 消耗

核心功能：
1. 候选内容压缩：将 100+ 条 ContentItem 压缩为摘要
2. 博主信息压缩：聚合博主列表
3. 任务队列压缩：只保留关键信息
4. 错误历史压缩：聚合相似错误

使用方式：
    from core.context_compressor import compress_state, get_compressed_context
    
    # 获取压缩后的上下文（供 LLM 使用）
    context = get_compressed_context(state)
    
    # 压缩特定部分
    candidates_summary = compress_candidates(state.candidates)
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
from core.prompt_manager import get_compression_template


class ContextCompressor:
    """上下文压缩器"""
    
    # 压缩阈值
    CANDIDATES_THRESHOLD = 20  # 超过此数量时压缩
    TASKS_THRESHOLD = 10
    ERRORS_THRESHOLD = 5
    INFLUENCERS_THRESHOLD = 10
    
    def __init__(self):
        pass
    
    def compress_candidates(
        self, 
        candidates: List, 
        top_n: int = 3,
        template: str = None
    ) -> str:
        """
        压缩候选内容列表
        
        Args:
            candidates: ContentItem 列表
            top_n: 每个平台显示的 Top N
            template: 可选的自定义模板
        
        Returns:
            压缩后的摘要文本
        """
        if not candidates:
            return "【候选内容】无"
        
        # 按平台分组
        by_platform = defaultdict(list)
        for item in candidates:
            platform = getattr(item, 'platform', 'unknown')
            by_platform[platform].append(item)
        
        # 统计
        total = len(candidates)
        youtube_items = by_platform.get('youtube', [])
        bilibili_items = by_platform.get('bilibili', [])
        
        youtube_count = len(youtube_items)
        bilibili_count = len(bilibili_items)
        
        # 计算平均播放量
        youtube_avg = self._calc_avg_views(youtube_items)
        bilibili_avg = self._calc_avg_views(bilibili_items)
        
        # 获取 Top N
        youtube_top = self._get_top_items(youtube_items, top_n)
        bilibili_top = self._get_top_items(bilibili_items, top_n)
        
        # 尝试使用模板
        if template is None:
            template = get_compression_template("candidates_summary_template")
        
        if template:
            try:
                return template.format(
                    total=total,
                    youtube_count=youtube_count,
                    youtube_avg_views=self._format_number(youtube_avg),
                    youtube_top3=", ".join(youtube_top),
                    bilibili_count=bilibili_count,
                    bilibili_avg_views=self._format_number(bilibili_avg),
                    bilibili_top3=", ".join(bilibili_top)
                )
            except KeyError:
                pass
        
        # 默认格式
        lines = [
            f"【候选内容摘要】共 {total} 条",
            f"├─ YouTube: {youtube_count} 条",
            f"│  ├─ 平均播放: {self._format_number(youtube_avg)}",
            f"│  └─ Top {top_n}: {', '.join(youtube_top) if youtube_top else '无'}",
            f"├─ Bilibili: {bilibili_count} 条",
            f"│  ├─ 平均播放: {self._format_number(bilibili_avg)}",
            f"│  └─ Top {top_n}: {', '.join(bilibili_top) if bilibili_top else '无'}",
        ]
        
        return "\n".join(lines)
    
    def compress_influencers(
        self, 
        influencers: List[Dict], 
        template: str = None
    ) -> str:
        """
        压缩博主列表
        
        Args:
            influencers: 博主信息列表
            template: 可选的自定义模板
        
        Returns:
            压缩后的摘要文本
        """
        if not influencers:
            return "【发现的博主】无"
        
        # 按平台分组
        by_platform = defaultdict(list)
        for inf in influencers:
            platform = inf.get('platform', 'unknown')
            name = inf.get('name', 'unknown')
            by_platform[platform].append(name)
        
        total = len(influencers)
        youtube_names = by_platform.get('youtube', [])[:5]
        bilibili_names = by_platform.get('bilibili', [])[:5]
        
        # 尝试使用模板
        if template is None:
            template = get_compression_template("influencers_summary_template")
        
        if template:
            try:
                return template.format(
                    total=total,
                    youtube_influencers=", ".join(youtube_names) if youtube_names else "无",
                    bilibili_influencers=", ".join(bilibili_names) if bilibili_names else "无"
                )
            except KeyError:
                pass
        
        # 默认格式
        lines = [
            f"【发现的博主】共 {total} 个",
            f"├─ YouTube: {', '.join(youtube_names) if youtube_names else '无'}",
            f"└─ Bilibili: {', '.join(bilibili_names) if bilibili_names else '无'}",
        ]
        
        return "\n".join(lines)
    
    def compress_tasks(
        self, 
        tasks: List, 
        template: str = None
    ) -> str:
        """
        压缩任务队列
        
        Args:
            tasks: TaskItem 列表
            template: 可选的自定义模板
        
        Returns:
            压缩后的摘要文本
        """
        if not tasks:
            return "【任务队列】无"
        
        # 统计状态
        status_counts = defaultdict(int)
        for task in tasks:
            status = getattr(task, 'status', 'unknown')
            status_counts[status] += 1
        
        total = len(tasks)
        pending = status_counts.get('pending', 0)
        in_progress = status_counts.get('in_progress', 0)
        completed = status_counts.get('completed', 0)
        
        # 获取待执行任务的简要信息
        pending_tasks = [t for t in tasks if getattr(t, 'status', '') == 'pending'][:5]
        pending_info = []
        for t in pending_tasks:
            tool = getattr(t, 'tool_name', 'unknown')
            platform = getattr(t, 'platform', '')
            pending_info.append(f"{tool}({platform})")
        
        # 尝试使用模板
        if template is None:
            template = get_compression_template("tasks_summary_template")
        
        if template:
            try:
                return template.format(
                    total=total,
                    pending=pending,
                    in_progress=in_progress,
                    completed=completed
                )
            except KeyError:
                pass
        
        # 默认格式
        lines = [
            f"【任务队列】共 {total} 个",
            f"├─ 待执行: {pending}",
            f"├─ 进行中: {in_progress}",
            f"├─ 已完成: {completed}",
        ]
        
        if pending_info:
            lines.append(f"└─ 待执行任务: {', '.join(pending_info)}")
        
        return "\n".join(lines)
    
    def compress_errors(
        self, 
        errors: List[Dict], 
        max_show: int = 3
    ) -> str:
        """
        压缩错误历史
        
        Args:
            errors: 错误记录列表
            max_show: 最大显示数量
        
        Returns:
            压缩后的摘要文本
        """
        if not errors:
            return ""
        
        # 聚合相似错误
        error_groups = defaultdict(list)
        for err in errors:
            tool = err.get('tool_name', err.get('tool', 'unknown'))
            error_type = err.get('error_type', 'Error')
            key = f"{tool}:{error_type}"
            error_groups[key].append(err)
        
        lines = [f"【错误历史】共 {len(errors)} 条"]
        
        # 显示聚合后的错误
        shown = 0
        for key, group in sorted(error_groups.items(), key=lambda x: -len(x[1])):
            if shown >= max_show:
                break
            
            tool, error_type = key.split(':', 1)
            count = len(group)
            latest_msg = str(group[-1].get('error', ''))[:50]
            
            if count > 1:
                lines.append(f"├─ {tool}: {error_type} × {count} 次 (最近: {latest_msg})")
            else:
                lines.append(f"├─ {tool}: {error_type} - {latest_msg}")
            
            shown += 1
        
        remaining = len(error_groups) - shown
        if remaining > 0:
            lines.append(f"└─ ... 还有 {remaining} 种错误")
        
        return "\n".join(lines)
    
    def compress_state(self, state) -> str:
        """
        压缩整个 RadarState
        
        Args:
            state: RadarState 实例
        
        Returns:
            压缩后的完整上下文
        """
        from core.state import RadarState
        
        if not isinstance(state, RadarState):
            return ""
        
        sections = []
        
        # 1. 基本进度
        total = len(state.candidates)
        target = 50  # 从配置获取
        progress_pct = total * 100 // target if target > 0 else 0
        
        sections.append(f"【进度】{total}/{target} ({progress_pct}%)")
        sections.append(f"【阶段】{state.current_phase}")
        
        # 2. 候选内容（如果超过阈值则压缩）
        if len(state.candidates) > self.CANDIDATES_THRESHOLD:
            sections.append(self.compress_candidates(state.candidates))
        else:
            # 少量时显示简要列表
            youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
            bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
            sections.append(f"【候选内容】YouTube: {youtube_count}, Bilibili: {bilibili_count}")
        
        # 3. 博主信息
        if state.discovered_influencers:
            if len(state.discovered_influencers) > self.INFLUENCERS_THRESHOLD:
                sections.append(self.compress_influencers(state.discovered_influencers))
            else:
                names = [inf.get('name', '?') for inf in state.discovered_influencers[:5]]
                sections.append(f"【博主】{', '.join(names)}")
        
        # 4. 任务队列
        pending_tasks = [t for t in state.task_queue if t.status == "pending"]
        if len(pending_tasks) > self.TASKS_THRESHOLD:
            sections.append(self.compress_tasks(state.task_queue))
        else:
            sections.append(f"【待执行任务】{len(pending_tasks)} 个")
        
        # 5. 错误历史
        if state.error_history:
            sections.append(self.compress_errors(state.error_history))
        
        return "\n\n".join(sections)
    
    def _calc_avg_views(self, items: List) -> int:
        """计算平均播放量"""
        if not items:
            return 0
        
        total_views = sum(getattr(item, 'view_count', 0) for item in items)
        return total_views // len(items) if items else 0
    
    def _get_top_items(self, items: List, n: int) -> List[str]:
        """获取 Top N 项目标题"""
        if not items:
            return []
        
        # 按播放量排序
        sorted_items = sorted(
            items, 
            key=lambda x: getattr(x, 'view_count', 0), 
            reverse=True
        )
        
        titles = []
        for item in sorted_items[:n]:
            title = getattr(item, 'title', '未知')
            # 截断长标题
            if len(title) > 30:
                title = title[:27] + "..."
            titles.append(title)
        
        return titles
    
    def _format_number(self, num: int) -> str:
        """格式化数字（万/亿）"""
        if num >= 100000000:
            return f"{num / 100000000:.1f}亿"
        elif num >= 10000:
            return f"{num / 10000:.1f}万"
        else:
            return str(num)


# ============ 全局单例 ============

_compressor: Optional[ContextCompressor] = None

def get_compressor() -> ContextCompressor:
    """获取压缩器单例"""
    global _compressor
    if _compressor is None:
        _compressor = ContextCompressor()
    return _compressor


# ============ 便捷函数 ============

def compress_candidates(candidates: List, top_n: int = 3) -> str:
    """压缩候选内容"""
    return get_compressor().compress_candidates(candidates, top_n)

def compress_influencers(influencers: List[Dict]) -> str:
    """压缩博主列表"""
    return get_compressor().compress_influencers(influencers)

def compress_tasks(tasks: List) -> str:
    """压缩任务队列"""
    return get_compressor().compress_tasks(tasks)

def compress_errors(errors: List[Dict], max_show: int = 3) -> str:
    """压缩错误历史"""
    return get_compressor().compress_errors(errors, max_show)

def compress_state(state) -> str:
    """压缩整个状态"""
    return get_compressor().compress_state(state)

def get_compressed_context(state) -> str:
    """获取压缩后的上下文（别名）"""
    return compress_state(state)


# ============ Token 估算 ============

def estimate_tokens(text: str) -> int:
    """
    估算文本的 Token 数量
    
    简单估算：中文约 1.5 tokens/字，英文约 0.75 tokens/词
    """
    if not text:
        return 0
    
    # 简单估算
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    
    # 中文字符约 1.5 tokens，其他字符约 0.25 tokens
    return int(chinese_chars * 1.5 + other_chars * 0.25)

def should_compress(state) -> bool:
    """
    判断是否需要压缩状态
    
    Args:
        state: RadarState 实例
    
    Returns:
        是否需要压缩
    """
    from core.state import RadarState
    
    if not isinstance(state, RadarState):
        return False
    
    compressor = get_compressor()
    
    # 任一条件满足则需要压缩
    if len(state.candidates) > compressor.CANDIDATES_THRESHOLD:
        return True
    if len(state.task_queue) > compressor.TASKS_THRESHOLD:
        return True
    if len(state.error_history) > compressor.ERRORS_THRESHOLD:
        return True
    if len(state.discovered_influencers) > compressor.INFLUENCERS_THRESHOLD:
        return True
    
    return False


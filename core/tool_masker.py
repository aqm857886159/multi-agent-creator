"""
动态工具屏蔽器 - 基于阶段和状态智能过滤可用工具

核心功能：
1. 根据当前阶段（init/discovery/collection/filtering/analysis）返回可用工具
2. 根据状态条件动态调整（如：无博主时屏蔽 monitor 工具）
3. 生成精简的工具描述供 LLM 使用

使用方式：
    from core.tool_masker import get_masked_tools, get_tool_descriptions
    
    # 获取当前阶段可用的工具
    tools = get_masked_tools(state)
    
    # 获取工具描述（供 LLM prompt）
    descriptions = get_tool_descriptions(state)
"""

from typing import List, Dict, Any, Optional
from core.prompt_manager import get_prompt_manager


class ToolMasker:
    """动态工具屏蔽器"""
    
    # 工具描述（简洁版，供 LLM 使用）
    TOOL_DESCRIPTIONS = {
        "web_search": {
            "name": "web_search",
            "description": "搜索互联网文章，发现博主和趋势",
            "params": ["query", "limit"],
            "example": '{"query": "best AI YouTubers 2025", "limit": 10}'
        },
        "web_scrape": {
            "name": "web_scrape",
            "description": "抓取网页内容，提取详细信息",
            "params": ["url"],
            "example": '{"url": "https://example.com/article"}'
        },
        "youtube_search": {
            "name": "youtube_search",
            "description": "搜索 YouTube 视频（纯英文关键词）",
            "params": ["keyword", "limit", "days"],
            "example": '{"keyword": "AI video tutorial 2025", "limit": 15, "days": 60}'
        },
        "bilibili_search": {
            "name": "bilibili_search",
            "description": "搜索 Bilibili 视频（纯中文关键词）",
            "params": ["keyword", "limit", "days"],
            "example": '{"keyword": "AI视频教程 保姆级 2025年", "limit": 15, "days": 60}'
        },
        "youtube_monitor": {
            "name": "youtube_monitor",
            "description": "监控 YouTube 频道最新视频",
            "params": ["channel_url", "limit"],
            "example": '{"channel_url": "@TwoMinutePapers", "limit": 10}',
            "requires": "discovered_influencers"  # 需要先发现博主
        },
        "bilibili_monitor": {
            "name": "bilibili_monitor",
            "description": "监控 Bilibili UP主最新视频",
            "params": ["up_id", "limit"],
            "example": '{"up_id": "946974", "limit": 10}',
            "requires": "discovered_influencers"
        },
        "arxiv_search": {
            "name": "arxiv_search",
            "description": "搜索学术论文（深度分析用）",
            "params": ["query", "max_results"],
            "example": '{"query": "large language model", "max_results": 5}'
        }
    }
    
    def __init__(self):
        self._prompt_manager = get_prompt_manager()
    
    def get_phase_tools(self, phase: str) -> List[str]:
        """
        获取指定阶段的基础工具列表
        
        Args:
            phase: 当前阶段 (init/discovery/collection/filtering/analysis)
        
        Returns:
            工具名称列表
        """
        return self._prompt_manager.get_available_tools(phase)
    
    def get_masked_tools(self, state) -> List[str]:
        """
        根据状态动态获取可用工具
        
        Args:
            state: RadarState 实例
        
        Returns:
            当前可用的工具名称列表
        """
        from core.state import RadarState
        
        if not isinstance(state, RadarState):
            return []
        
        # 1. 获取阶段基础工具
        phase = state.current_phase
        base_tools = self.get_phase_tools(phase)
        
        # 2. 根据状态条件过滤
        available_tools = []
        
        for tool_name in base_tools:
            tool_info = self.TOOL_DESCRIPTIONS.get(tool_name, {})
            requires = tool_info.get("requires")
            
            # 检查前置条件
            if requires:
                if requires == "discovered_influencers":
                    # monitor 工具需要先发现博主
                    if not state.discovered_influencers:
                        continue
            
            available_tools.append(tool_name)
        
        # 3. 特殊规则
        available_tools = self._apply_special_rules(available_tools, state)
        
        return available_tools
    
    def _apply_special_rules(self, tools: List[str], state) -> List[str]:
        """
        应用特殊规则
        
        Args:
            tools: 当前工具列表
            state: RadarState 实例
        
        Returns:
            过滤后的工具列表
        """
        from core.state import RadarState
        
        if not isinstance(state, RadarState):
            return tools
        
        filtered = list(tools)
        
        # 规则1: 如果某平台已达到数量上限，屏蔽该平台的搜索工具
        youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
        bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
        
        # 如果一个平台已经是另一个的 2 倍以上，优先补充落后平台
        if youtube_count > bilibili_count * 2 and youtube_count > 10:
            # YouTube 过多，考虑降低 YouTube 工具优先级（但不完全屏蔽）
            pass
        
        if bilibili_count > youtube_count * 2 and bilibili_count > 10:
            # Bilibili 过多，考虑降低 Bilibili 工具优先级
            pass
        
        # 规则2: 如果错误历史中某工具连续失败 3 次，暂时屏蔽
        if state.error_history:
            tool_error_counts = {}
            for err in state.error_history[-10:]:  # 只看最近 10 条
                tool = err.get("tool_name", err.get("tool", ""))
                tool_error_counts[tool] = tool_error_counts.get(tool, 0) + 1
            
            for tool, count in tool_error_counts.items():
                if count >= 3 and tool in filtered:
                    # 不完全屏蔽，但可以在描述中标记
                    pass
        
        return filtered
    
    def get_tool_descriptions(self, state, format: str = "markdown") -> str:
        """
        生成当前可用工具的描述文本
        
        Args:
            state: RadarState 实例
            format: 输出格式 (markdown/json/brief)
        
        Returns:
            工具描述文本
        """
        available_tools = self.get_masked_tools(state)
        
        if not available_tools:
            return "当前阶段无可用工具。"
        
        if format == "brief":
            return ", ".join(available_tools)
        
        if format == "json":
            import json
            tools_info = []
            for tool_name in available_tools:
                info = self.TOOL_DESCRIPTIONS.get(tool_name, {"name": tool_name})
                tools_info.append(info)
            return json.dumps(tools_info, ensure_ascii=False, indent=2)
        
        # markdown 格式
        lines = ["## 可用工具", ""]
        
        for tool_name in available_tools:
            info = self.TOOL_DESCRIPTIONS.get(tool_name, {})
            desc = info.get("description", "无描述")
            params = info.get("params", [])
            example = info.get("example", "")
            
            lines.append(f"### {tool_name}")
            lines.append(f"- 描述: {desc}")
            lines.append(f"- 参数: {', '.join(params)}")
            if example:
                lines.append(f"- 示例: `{example}`")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_tool_hints(self, state) -> str:
        """
        生成工具使用提示（基于当前状态）
        
        Args:
            state: RadarState 实例
        
        Returns:
            工具使用提示文本
        """
        from core.state import RadarState
        
        if not isinstance(state, RadarState):
            return ""
        
        hints = []
        
        # 根据状态生成提示
        youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
        bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
        
        # 平台平衡提示
        if youtube_count > bilibili_count + 5:
            hints.append(f"⚠️ YouTube ({youtube_count}) 比 Bilibili ({bilibili_count}) 多，建议优先使用 bilibili_search")
        elif bilibili_count > youtube_count + 5:
            hints.append(f"⚠️ Bilibili ({bilibili_count}) 比 YouTube ({youtube_count}) 多，建议优先使用 youtube_search")
        
        # 博主发现提示
        if state.discovered_influencers and not state.searched_influencers:
            hints.append(f"💡 已发现 {len(state.discovered_influencers)} 个博主，可以使用 youtube_search/bilibili_search 搜索他们的内容")
        
        # 错误提示
        if state.error_history:
            recent_errors = state.error_history[-3:]
            failed_tools = set(err.get("tool_name", err.get("tool", "")) for err in recent_errors)
            if failed_tools:
                hints.append(f"⚠️ 最近失败的工具: {', '.join(failed_tools)}，考虑调整参数或换用其他工具")
        
        return "\n".join(hints) if hints else ""
    
    def should_allow_tool(self, tool_name: str, state) -> tuple:
        """
        检查是否应该允许使用某个工具
        
        Args:
            tool_name: 工具名称
            state: RadarState 实例
        
        Returns:
            (allowed: bool, reason: str)
        """
        available_tools = self.get_masked_tools(state)
        
        if tool_name not in available_tools:
            # 检查原因
            phase_tools = self.get_phase_tools(state.current_phase)
            
            if tool_name not in phase_tools:
                return False, f"工具 {tool_name} 在当前阶段 ({state.current_phase}) 不可用"
            
            tool_info = self.TOOL_DESCRIPTIONS.get(tool_name, {})
            requires = tool_info.get("requires")
            if requires == "discovered_influencers" and not state.discovered_influencers:
                return False, f"工具 {tool_name} 需要先发现博主"
            
            return False, f"工具 {tool_name} 当前不可用"
        
        return True, "允许使用"


# ============ 全局单例 ============

_tool_masker: Optional[ToolMasker] = None

def get_tool_masker() -> ToolMasker:
    """获取工具屏蔽器单例"""
    global _tool_masker
    if _tool_masker is None:
        _tool_masker = ToolMasker()
    return _tool_masker


# ============ 便捷函数 ============

def get_masked_tools(state) -> List[str]:
    """获取当前可用的工具列表"""
    return get_tool_masker().get_masked_tools(state)

def get_tool_descriptions(state, format: str = "markdown") -> str:
    """获取工具描述文本"""
    return get_tool_masker().get_tool_descriptions(state, format)

def get_tool_hints(state) -> str:
    """获取工具使用提示"""
    return get_tool_masker().get_tool_hints(state)

def should_allow_tool(tool_name: str, state) -> tuple:
    """检查是否允许使用工具"""
    return get_tool_masker().should_allow_tool(tool_name, state)


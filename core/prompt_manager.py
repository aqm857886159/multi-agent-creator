"""
统一提示词管理器 - 基于 Claude Prompt Engineering 最佳实践

核心原则（来自 claude.com/blog/best-practices-for-prompt-engineering）：
1. Be explicit and clear - 明确直接，使用动词开头
2. Provide context and motivation - 提供背景和动机
3. Be specific - 具体详细，包含约束条件
4. Use examples - 使用示例展示期望格式
5. Give permission to express uncertainty - 允许表达不确定性

使用方式：
    from core.prompt_manager import get_prompt, build_agent_context
    
    # 获取系统提示词
    system_prompt = get_prompt("planner", "system", topic="AI视频")
    
    # 构建完整上下文（包含状态、错误历史、Skills）
    context = build_agent_context(
        agent_name="planner",
        state_summary="已采集 30 条",
        error_history="youtube_search 超时 2 次",
        skills_context="YouTube 搜索技巧..."
    )
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

# ============ 提示词管理器 ============

class PromptManager:
    """统一管理所有提示词"""
    
    def __init__(self, config_path: str = "config/prompts.yaml"):
        self.config_path = config_path
        self._prompts: Dict[str, Any] = {}
        self._loaded = False
        
    def load(self) -> Dict[str, Any]:
        """延迟加载提示词配置"""
        if self._loaded:
            return self._prompts
        
        config_file = Path(self.config_path)
        if not config_file.exists():
            # 使用默认配置
            self._prompts = self._get_default_prompts()
        else:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._prompts = yaml.safe_load(f) or {}
        
        self._loaded = True
        return self._prompts
    
    def reload(self):
        """强制重新加载配置（用于热更新）"""
        self._loaded = False
        return self.load()
    
    def get_prompt(
        self, 
        agent_name: str, 
        prompt_type: str = "system",
        **kwargs
    ) -> str:
        """
        获取格式化后的提示词
        
        Args:
            agent_name: 智能体名称 (planner, keyword_designer, etc.)
            prompt_type: 提示词类型 (system, user, goal_recap, state_summary)
            **kwargs: 用于格式化的变量
        """
        self.load()
        
        agent_config = self._prompts.get(agent_name, {})
        template_key = f"{prompt_type}_template"
        template = agent_config.get(template_key, "")
        
        if not template:
            # 尝试获取通用模板
            template = agent_config.get("system_template", "")
        
        # 注入通用变量
        kwargs.setdefault("current_year", datetime.now().strftime("%Y"))
        kwargs.setdefault("current_month", datetime.now().strftime("%Y年%m月"))
        kwargs.setdefault("current_date", datetime.now().strftime("%Y-%m-%d"))
        
        # 注入角色信息
        kwargs.setdefault("role", agent_config.get("role", "AI助手"))
        kwargs.setdefault("goal", agent_config.get("goal", ""))
        
        # 注入全局配置
        global_config = self._prompts.get("global", {})
        kwargs.setdefault("target_items", global_config.get("target_items", 50))
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # 如果格式化失败，返回原始模板
            return template
    
    def get_template(self, section: str, template_name: str) -> str:
        """
        获取特定部分的模板（如 compression, error_handling）
        
        Args:
            section: 配置部分名称
            template_name: 模板名称
        """
        self.load()
        section_config = self._prompts.get(section, {})
        return section_config.get(template_name, "")
    
    def get_tool_phases(self) -> Dict[str, Any]:
        """获取工具阶段映射配置"""
        self.load()
        return self._prompts.get("tool_phases", {})
    
    def get_available_tools(self, phase: str) -> List[str]:
        """获取指定阶段可用的工具列表"""
        tool_phases = self.get_tool_phases()
        phase_config = tool_phases.get(phase, {})
        return phase_config.get("available", [])
    
    def get_error_handling_config(self) -> Dict[str, Any]:
        """获取错误处理配置"""
        self.load()
        return self._prompts.get("error_handling", {})
    
    def get_compression_template(self, template_name: str) -> str:
        """获取压缩模板"""
        self.load()
        compression_config = self._prompts.get("compression", {})
        return compression_config.get(template_name, "")
    
    def build_context(
        self,
        agent_name: str,
        state_summary: str = "",
        error_history: str = "",
        skills_context: str = "",
        additional_context: str = ""
    ) -> str:
        """
        构建完整的上下文（Manus Context Engineering 最佳实践）
        
        结构：
        1. 角色定义
        2. 当前状态摘要（复述机制 - Retelling）
        3. 错误历史（避免重复 - Error Context）
        4. 相关 Skills（专业知识注入）
        5. 附加上下文
        """
        self.load()
        
        agent_config = self._prompts.get(agent_name, {})
        role = agent_config.get("role", "AI助手")
        goal = agent_config.get("goal", "完成用户任务")
        
        context_parts = []
        
        # 1. 角色定义
        context_parts.append(f"# 角色：{role}")
        context_parts.append(f"# 目标：{goal}")
        context_parts.append("")
        
        # 2. 当前状态摘要（复述机制）
        if state_summary:
            context_parts.append("## 当前状态")
            context_parts.append(state_summary)
            context_parts.append("")
        
        # 3. 错误历史
        if error_history:
            context_parts.append("## 历史错误（请避免重复）")
            context_parts.append(error_history)
            context_parts.append("")
        
        # 4. Skills 上下文
        if skills_context:
            context_parts.append("## 专业知识参考")
            context_parts.append(skills_context)
            context_parts.append("")
        
        # 5. 附加上下文
        if additional_context:
            context_parts.append("## 补充信息")
            context_parts.append(additional_context)
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def get_role(self, agent_name: str) -> str:
        """获取智能体角色"""
        self.load()
        return self._prompts.get(agent_name, {}).get("role", "AI助手")
    
    def get_goal(self, agent_name: str) -> str:
        """获取智能体目标"""
        self.load()
        return self._prompts.get(agent_name, {}).get("goal", "")
    
    def get_global_config(self, key: str, default: Any = None) -> Any:
        """获取全局配置"""
        self.load()
        return self._prompts.get("global", {}).get(key, default)
    
    def _get_default_prompts(self) -> Dict[str, Any]:
        """默认提示词配置"""
        return {
            "global": {
                "target_items": 50,
                "max_steps": 50,
                "platforms": ["youtube", "bilibili"]
            },
            "planner": {
                "role": "内容采集规划师",
                "goal": "智能调度双平台搜索任务，确保数据质量和平台平衡",
                "system_template": """你是一个{role}。你的目标是{goal}。

## 调度原则
1. 平台平衡: YouTube和Bilibili数量差距不超过5条
2. 引擎平衡: 博主发现(引擎1)和关键词搜索(引擎2)并重
3. 质量优先: 宁缺毋滥，低相关性结果不入库

## 搜索词设计
- 英文博主 + 英文主题词（避免混合语言）
- 中文博主 + 中文主题词

如果信息不足以做出决策，请明确说明而不是猜测。"""
            },
            "keyword_designer": {
                "role": "跨平台视频SEO专家",
                "goal": "为YouTube和Bilibili设计高性能、无歧义的搜索词",
                "system_template": """你是一个{role}。你的目标是{goal}。

## 核心原则
1. YouTube: 使用3-5词英文查询，避免触发Shorts的词汇（short, quick）
2. Bilibili: 使用B站黑话（保姆级、干货、避坑指南）
3. 时间锚定: 只用年份{current_year}，不用月份

## 输出要求
- 格式: 严格JSON
- 语言: YouTube用英文，Bilibili用中文

如果主题太宽泛无法设计精准搜索词，请明确指出并建议细化方向。"""
            },
            "influencer_extractor": {
                "role": "博主信息提取专家",
                "goal": "从文章中准确提取博主/创作者信息",
                "system_template": """你是一个{role}。你的目标是{goal}。

## 提取规则
1. 只提取明确提到的博主，不要推测
2. 平台识别: YouTube频道、B站UP主、Twitter账号等
3. 置信度: high(有明确链接) / medium(有名字) / low(仅提及)

## 输出格式
严格JSON，包含: name, platform, identifier, confidence

如果文章中没有明确的博主信息，返回空列表并说明原因。"""
            },
            "architect": {
                "role": "爆款选题架构师",
                "goal": "基于数据策划极具吸引力的视频选题",
                "system_template": """你是一个{role}。你的目标是{goal}。

## 选题标准
1. 标题3秒抓眼球: 数字、对比、悬念
2. 数据驱动: 每个选题必须基于高热度数据
3. 差异化: 提供新的切入点，不照搬

## 质量门槛
- 素材相关性 > 30% 才生成选题
- 相关性不足时，明确告知用户调整搜索词

所有输出必须使用中文。"""
            },
            "analyst": {
                "role": "深度分析专家",
                "goal": "挖掘选题背后的底层逻辑和反直觉洞察",
                "system_template": """你是一个{role}，融合了麦肯锡顾问、调查记者和哲学家的思维。

## 分析框架
1. 底层逻辑: 这个现象为什么会发生？
2. 主流观点: 大多数人怎么看？
3. 反直觉洞察: 有什么被忽视的角度？
4. 情感钩子: 贪婪/恐惧/好奇

## 输出要求
- 置信度: 0-1之间
- 引用来源: 标注信息出处

如果信息不足以得出结论，请明确说明而不是编造。"""
            },
            "quality_gate": {
                "role": "内容质量检查员",
                "goal": "评估搜索结果的相关性、数量和质量",
                "system_template": """你是一个{role}。你的目标是{goal}。

## 评估维度
1. 相关性: 结果标题是否匹配搜索意图？
2. 数量: 是否达到预期数量？
3. 质量: 是否为垃圾内容或重复内容？

## 决策
- pass: 全部通过
- adjust_params: 需要调整参数重试
- skip: 放弃此次搜索

请给出具体的问题诊断和调整建议。"""
            },
            "tool_phases": {
                "init": {"available": []},
                "discovery": {"available": ["web_search", "web_scrape"]},
                "collection": {"available": ["youtube_search", "bilibili_search", "youtube_monitor", "bilibili_monitor"]},
                "filtering": {"available": []},
                "analysis": {"available": ["web_search", "arxiv_search"]}
            }
        }


# ============ 全局单例 ============

_prompt_manager: Optional[PromptManager] = None

def get_prompt_manager() -> PromptManager:
    """获取提示词管理器单例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager

def get_prompt(agent_name: str, prompt_type: str = "system", **kwargs) -> str:
    """便捷函数：获取提示词"""
    return get_prompt_manager().get_prompt(agent_name, prompt_type, **kwargs)

def build_agent_context(agent_name: str, **kwargs) -> str:
    """便捷函数：构建智能体上下文"""
    return get_prompt_manager().build_context(agent_name, **kwargs)

def get_role(agent_name: str) -> str:
    """便捷函数：获取角色"""
    return get_prompt_manager().get_role(agent_name)

def get_goal(agent_name: str) -> str:
    """便捷函数：获取目标"""
    return get_prompt_manager().get_goal(agent_name)

def get_available_tools(phase: str) -> List[str]:
    """便捷函数：获取阶段可用工具"""
    return get_prompt_manager().get_available_tools(phase)

def get_compression_template(template_name: str) -> str:
    """便捷函数：获取压缩模板"""
    return get_prompt_manager().get_compression_template(template_name)


# ============ 上下文构建辅助函数 ============

def build_state_summary(state, template: str = None) -> str:
    """
    从 RadarState 构建状态摘要
    
    Args:
        state: RadarState 实例
        template: 可选的自定义模板
    """
    from core.state import RadarState
    if not isinstance(state, RadarState):
        return ""
    
    youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
    bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
    total = len(state.candidates)
    pending_tasks = len([t for t in state.task_queue if t.status == "pending"])
    
    if template:
        try:
            return template.format(
                total=total,
                youtube_count=youtube_count,
                bilibili_count=bilibili_count,
                pending_tasks=pending_tasks,
                current_phase=state.current_phase,
                target_items=get_prompt_manager().get_global_config("target_items", 50),
                collected=total,
                progress_pct=total * 100 // 50 if total > 0 else 0
            )
        except KeyError:
            pass
    
    # 默认格式
    lines = [
        f"- 已采集: {total} 条内容",
        f"  - YouTube: {youtube_count} 条",
        f"  - Bilibili: {bilibili_count} 条",
        f"- 发现博主: {len(state.discovered_influencers)} 个",
        f"- 待处理线索: {len(state.leads)} 条",
        f"- 任务队列: {pending_tasks} 个待执行",
    ]
    
    return "\n".join(lines)

def build_error_summary(state, max_errors: int = 5, template: str = None) -> str:
    """
    从 RadarState 构建错误摘要
    
    Args:
        state: RadarState 实例
        max_errors: 最大显示错误数
        template: 可选的自定义模板
    """
    from core.state import RadarState
    if not isinstance(state, RadarState):
        return ""
    
    if not state.error_history:
        return ""
    
    recent_errors = state.error_history[-max_errors:]
    
    # 获取错误处理配置
    error_config = get_prompt_manager().get_error_handling_config()
    item_template = error_config.get("error_item_template", "- {tool_name}: [{error_type}] {error_msg}")
    
    lines = []
    for err in recent_errors:
        tool = err.get("tool_name", err.get("tool", "unknown"))
        error_type = err.get("error_type", "Error")
        error_msg = str(err.get("error", ""))[:100]
        
        try:
            line = item_template.format(
                tool_name=tool,
                error_type=error_type,
                error_msg=error_msg
            )
        except KeyError:
            line = f"- {tool}: [{error_type}] {error_msg}"
        
        lines.append(line)
    
    return "\n".join(lines)

def build_skills_summary(state) -> str:
    """从 RadarState 获取相关 Skills 上下文"""
    try:
        from skills import get_skill_context
        from core.state import RadarState
        
        if not isinstance(state, RadarState):
            return ""
        
        # 根据当前任务类型获取相关 Skills
        keywords = []
        if state.session_focus:
            keywords.append(str(state.session_focus))
        
        # 添加平台关键词
        pending_tasks = [t for t in state.task_queue if t.status == "pending"]
        for task in pending_tasks[:3]:
            if task.platform:
                keywords.append(task.platform)
        
        if keywords:
            return get_skill_context(" ".join(keywords))
        return ""
    except ImportError:
        return ""


# ============ 目标提醒构建器 ============

def build_goal_recap(state, target_items: int = 50) -> str:
    """
    构建目标提醒（复述机制）
    
    Args:
        state: RadarState 实例
        target_items: 目标数量
    """
    from core.state import RadarState
    if not isinstance(state, RadarState):
        return ""
    
    collected = len(state.candidates)
    youtube_count = len([c for c in state.candidates if c.platform == "youtube"])
    bilibili_count = len([c for c in state.candidates if c.platform == "bilibili"])
    progress_pct = collected * 100 // target_items if target_items > 0 else 0
    
    # 尝试从配置获取模板
    template = get_prompt_manager().get_prompt("planner", "goal_recap")
    
    if template:
        try:
            # 构建错误摘要
            error_summary = ""
            if state.error_history:
                recent_errors = state.error_history[-2:]
                error_lines = [f"   ⚠️ 最近错误: {len(state.error_history)} 条"]
                for err in recent_errors:
                    tool = err.get("tool_name", "unknown")
                    msg = str(err.get("error", ""))[:50]
                    error_lines.append(f"      - {tool}: {msg}")
                error_summary = "\n".join(error_lines)
            
            return template.format(
                target_items=target_items,
                collected=collected,
                progress_pct=progress_pct,
                youtube_count=youtube_count,
                bilibili_count=bilibili_count,
                error_summary=error_summary
            )
        except KeyError:
            pass
    
    # 默认格式
    lines = [
        f"📌 【目标提醒】",
        f"   🎯 目标: 收集 {target_items} 条内容",
        f"   📊 进度: {collected}/{target_items} ({progress_pct}%)",
        f"   ⚖️ 平台: YouTube={youtube_count} Bilibili={bilibili_count}",
    ]
    
    if state.error_history:
        lines.append(f"   ⚠️ 最近错误: {len(state.error_history)} 条")
    
    return "\n".join(lines)

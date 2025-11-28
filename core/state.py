from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ContentItem(BaseModel):
    """Represents a single piece of content discovered."""
    platform: str  # youtube, bilibili
    source_type: str  # monitor_kol, keyword_search
    title: str
    url: str
    author_name: str
    author_id: str
    author_fans: int = 0
    author_avg_views: int = 0
    publish_time: str  # ISO format or datetime string
    view_count: int = 0
    interaction: int = 0  # likes + comments + shares
    score: float = 0.0
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class InfluencerInfo(BaseModel):
    """博主信息（用于双引擎发现）"""
    name: str = Field(..., description="博主名称")
    platform: str = Field(..., description="平台: youtube 或 bilibili")
    identifier: str = Field(..., description="博主标识（@handle, 频道URL, 或 UP主ID）")
    mention_count: int = Field(default=1, description="在文章中出现次数（权重）")
    source_url: str = Field(default="", description="来源文章URL")
    confidence: str = Field(default="medium", description="置信度: high/medium/low")


class LeadItem(BaseModel):
    """Represents a lightweight clue extracted from generic web search."""
    title: str
    url: str
    source: str = "web_search"
    snippet: str = ""
    topic_hint: str = "general"
    tags: List[str] = Field(default_factory=list)


# 🔑 新增: 结构化搜索词
class TopicSearchQueries(BaseModel):
    """单个主题的结构化搜索词"""
    topic: str = Field(..., description="主题名称")
    discovery_query_en: str = Field(..., description="发现博主的英文搜索词")
    discovery_query_zh: str = Field(..., description="发现博主的中文搜索词")
    content_query_en: str = Field(..., description="搜索内容的英文关键词")
    content_query_zh: str = Field(..., description="搜索内容的中文关键词")


# 🔑 新增: 任务队列
class TaskItem(BaseModel):
    """单个任务"""
    task_id: str = Field(..., description="任务唯一ID")
    task_type: str = Field(..., description="discovery | influencer_search | content_search | monitor")
    priority: int = Field(..., description="优先级 1-100, 数字越大优先级越高")
    engine: str = Field(..., description="engine1 | engine2")
    platform: str = Field(..., description="youtube | bilibili | both")
    tool_name: str = Field(..., description="要调用的工具名")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    status: str = Field(default="pending", description="pending | in_progress | completed | failed")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    reasoning: str = Field(default="", description="任务理由")

class TopicBrief(BaseModel):
    """
    The standard output artifact of the RadarAgent.
    Passed to the AnalystAgent for deep dive.
    """
    id: str = Field(..., description="Unique identifier for the topic")
    title: str
    core_angle: str       # The unique hook/angle
    rationale: str        # Why this was selected
    source_type: str      # "viral_hit" | "competitor" | "tech_news"
    reference_data: List[Dict[str, Any]] # The raw data backing this choice


# 🔑 Analyst Agent 数据结构 (Three-Level Rocket Architecture)

class ResearchPlan(BaseModel):
    """
    Level 1: Adaptive Scout Output
    动态侦察规划结果 - 决定去哪找源头
    """
    topic_category: str = Field(..., description="选题类型: tech_ai | business_finance | social_cognition | general")
    search_strategy: str = Field(..., description="搜索策略描述")
    search_instructions: List[Dict[str, Any]] = Field(..., description="3-5个定向搜索指令")
    reasoning: str = Field(default="", description="为什么选择这个策略")


class KeyInsight(BaseModel):
    """
    Level 2: Excavator Output
    智能萃取的情报卡片 - 高信噪比的结构化信息
    """
    source: str = Field(..., description="来源（如: OpenAI Technical Report）")
    url: str = Field(..., description="链接")
    is_primary: bool = Field(..., description="是否一手资料（AI判断）")
    quote: str = Field(..., description="原话/原文数据（拒绝编造）")
    insight: str = Field(..., description="对选题的价值解读")
    conflict: str = Field(default="", description="是否存在与主流观点的冲突点")
    confidence: str = Field(default="medium", description="信息可信度: high/medium/low")


class DeepAnalysisReport(BaseModel):
    """
    Level 3: Philosopher Output
    最终深度研报 - 基于事实的逻辑重构
    """
    topic_id: str = Field(..., description="对应的TopicBrief ID")
    topic_title: str = Field(..., description="选题标题")

    # === 事实层 (Fact Layer) ===
    hard_evidence: List[str] = Field(default_factory=list, description="硬核数据/论文结论（必须带引用）")
    verified_facts: List[Dict[str, Any]] = Field(default_factory=list, description="核实过的事实列表")

    # === 逻辑层 (Logic Layer) ===
    root_cause: str = Field(default="", description="5-Why导出的底层归因（如: 边际成本递减）")
    theoretical_model: str = Field(default="", description="使用的学科模型（如: 熵增定律、网络效应）")
    first_principles_analysis: str = Field(default="", description="第一性原理推导过程")

    # === 冲突与洞察层 (Insight Layer) ===
    mainstream_view: str = Field(default="", description="大众怎么看")
    contrarian_view: str = Field(default="", description="反直觉的洞察（High Value）")
    conflict_analysis: str = Field(default="", description="主流观点的反面，构建冲突")

    # === 叙事层 (Narrative Layer) ===
    emotional_hook: str = Field(default="", description="击中用户哪个底层心理（贪婪/恐惧/懒惰）")
    content_strategy: str = Field(default="", description="给Writer的具体建议")

    # === 元数据 (Metadata) ===
    sources_used: List[KeyInsight] = Field(default_factory=list, description="使用的情报卡片")
    confidence_score: float = Field(default=0.0, description="整体置信度 0-1")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class RadarState(BaseModel):
    """Global state for the RadarAgent workflow."""
    # Configuration & Inputs
    target_domains: List[str] = Field(default_factory=list)
    monitoring_list: Dict[str, List[str]] = Field(default_factory=lambda: {
        "youtube": [],
        "bilibili": []
    })
    
    # Runtime Data
    keywords: List[str] = Field(default_factory=list)
    candidates: List[ContentItem] = Field(default_factory=list)
    filtered_candidates: List[ContentItem] = Field(default_factory=list)
    
    # Session Focus & Progress
    session_focus: Dict[str, Any] = Field(default_factory=dict)
    topic_targets: Dict[str, int] = Field(default_factory=dict)
    topic_progress: Dict[str, int] = Field(default_factory=dict)
    
    # Output Data (Standardized for Inter-Agent Communication)
    proposals: List[TopicBrief] = Field(default_factory=list)
    
    # Execution Flags
    logs: List[str] = Field(default_factory=list)
    leads: List[LeadItem] = Field(default_factory=list)
    
    # Dynamic Discovery & Monitoring
    pending_monitors: Dict[str, List[str]] = Field(default_factory=lambda: {
        "youtube": [],
        "bilibili": []
    })
    discovered_sources: Dict[str, List[str]] = Field(default_factory=lambda: {
        "youtube": [],
        "bilibili": [],
        "web": []
    })
    discovery_history: List[str] = Field(default_factory=list)
    platform_search_progress: Dict[str, bool] = Field(default_factory=lambda: {
        "youtube": False,
        "bilibili": False
    })
    monitor_autoruns: Dict[str, int] = Field(default_factory=lambda: {
        "youtube": 0,
        "bilibili": 0
    })

    # 🔑 修复关键问题 2: 记录已监控过的频道，避免重复监控
    monitored_sources: Dict[str, List[str]] = Field(default_factory=lambda: {
        "youtube": [],
        "bilibili": []
    })

    # 🔑 双引擎发现系统 (Dual-Engine Discovery System)
    # 引擎 1 准备阶段：搜索词设计 + 博主发现
    discovery_queries: List[str] = Field(default_factory=list, description="发现博主的搜索词（用于找推荐文章）")
    content_queries: List[str] = Field(default_factory=list, description="发现内容的搜索词（用于直接搜索视频）")

    # 🔑 新增: 结构化搜索词（存储为字典列表以兼容LangGraph状态更新）
    topic_queries: List[Dict[str, Any]] = Field(default_factory=list, description="结构化的主题搜索词")

    discovered_influencers: List[Dict[str, Any]] = Field(default_factory=list, description="从文章中发现的博主列表（字典格式）")
    searched_influencers: List[str] = Field(default_factory=list, description="已搜索过的博主标识列表")
    influencer_search_done: bool = Field(default=False, description="博主搜索是否完成")

    # 🔑 新增: 任务队列系统
    task_queue: List[TaskItem] = Field(default_factory=list, description="待执行任务队列")
    completed_tasks: List[str] = Field(default_factory=list, description="已完成任务ID列表")
    current_phase: str = Field(default="init", description="init | discovery | collection | filtering")

    # 🔑 新增: 引擎进度追踪
    engine_progress: Dict[str, int] = Field(default_factory=lambda: {
        "engine1": 0,
        "engine2": 0
    }, description="各引擎收集的内容数量")

    # 双引擎执行阶段标记
    dual_engine_phase: str = Field(default="design", description="design | discover | search_influencers | broad_search | monitor | done")

    # ReAct Planner State
    plan_scratchpad: List[Dict[str, Any]] = Field(default_factory=list, description="History of tool calls and thoughts")
    plan_status: str = Field(default="planning", description="planning | executing | finished")

    # 🔑 自适应反馈系统
    quality_checks: List[Dict[str, Any]] = Field(default_factory=list, description="质量检查历史记录")
    retry_count: int = Field(default=0, description="当前会话重试总次数")
    feedback_enabled: bool = Field(default=True, description="是否启用自适应反馈（可关闭用于调试）")

    # 🔑 P0: 错误历史记录（Manus最佳实践：保留失败尝试在上下文中）
    error_history: List[Dict[str, Any]] = Field(default_factory=list, description="工具执行错误历史，帮助LLM避免重复犯错")

    # 🔑 P0: 外部记忆标记
    candidates_externalized: bool = Field(default=False, description="候选内容是否已外部化存储")

    # 🔑 Analyst Agent 输出
    analysis_reports: List[Dict[str, Any]] = Field(default_factory=list, description="深度分析报告")

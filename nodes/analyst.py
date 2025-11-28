"""
Analyst Agent - 深度分析智能体
==================================

功能: 将 TopicBrief 转化为 DeepAnalysisReport
架构: 三级火箭模型 (Scout → Excavator → Philosopher)

作者: AI Assistant
日期: 2025-11-27
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from core.state import TopicBrief, ResearchPlan, KeyInsight, DeepAnalysisReport
from core.llm import get_llm_with_schema
from tools.web_search import SearchGateway
from tools.arxiv_search import ArxivSearcher


# ============================================
# Level 1: Adaptive Scout (动态侦察规划)
# ============================================

def _summarize_reference_data(reference_data: List[Dict[str, Any]]) -> str:
    """
    将 reference_data 转换为简洁的摘要文本，供 LLM 参考
    """
    if not reference_data:
        return "无已有素材"

    summary_lines = []
    for idx, ref in enumerate(reference_data[:10], 1):  # 最多展示 10 条
        # 兼容 ContentItem dict 和原始 dict
        platform = ref.get('platform', '未知平台')
        title = ref.get('title', '无标题')
        view_count = ref.get('view_count', 0)
        author = ref.get('author_name', '未知作者')

        # 提取描述信息（如果有）
        desc = ""
        if 'raw_data' in ref and isinstance(ref['raw_data'], dict):
            desc = ref['raw_data'].get('description', '') or ref['raw_data'].get('summary', '')
            if desc:
                desc = desc[:150] + "..." if len(desc) > 150 else desc

        summary_lines.append(
            f"{idx}. [{platform}] {title}\n"
            f"   播放: {view_count:,} | 作者: {author}"
            + (f"\n   简介: {desc}" if desc else "")
        )

    if len(reference_data) > 10:
        summary_lines.append(f"\n... 以及其他 {len(reference_data) - 10} 条素材")

    return "\n\n".join(summary_lines)


def plan_research_strategy(topic_brief: TopicBrief) -> ResearchPlan:
    """
    Level 1: Scout - 理解选题意图，设计最优搜索策略

    逻辑: 从"分类驱动"转向"意图驱动"
    - 不再强制分类（tech/business/social）
    - 而是推理：这个选题需要什么信息？应该去哪找？
    模型: Fast Model (creative)
    """

    # 🔑 提取 reference_data 信息
    ref_count = len(topic_brief.reference_data)
    ref_summary = _summarize_reference_data(topic_brief.reference_data)

    # 🔑 提取平台信息
    platforms = set()
    for ref in topic_brief.reference_data:
        if isinstance(ref, dict) and 'platform' in ref:
            platforms.add(ref['platform'])
    platform_str = ', '.join(platforms) if platforms else '未知'

    user_prompt = f"""
# 你的任务：理解选题意图，设计最优搜索策略

## 背景信息

**选题**:
- 标题: {topic_brief.title}
- 切入点: {topic_brief.core_angle}
- 推荐理由: {topic_brief.rationale}
- 来源类型: {topic_brief.source_type}
  （说明: "search" = 从视频平台搜索得到, "viral_hit" = 爆款视频, "competitor" = 竞品分析）

**已有素材** ({ref_count} 条，来自 {platform_str}):
{ref_summary}

---

## 你的推理过程（请逐步思考）

### Step 1: 理解选题的真实意图

**思考**:
1. 这个选题的核心价值是什么？
   - 理论验证（需要学术论文支撑）
   - 实战教程（需要操作手册和案例）
   - 观点评论（需要专家访谈和数据）
   - 案例分享（需要真实经验和故事）

2. 目标受众是谁？
   - 学术研究者 vs 普通用户 vs 专业人士

3. 选题来自哪里？
   - 如果来自 "Bilibili" → 可能是实战方法、教程
   - 如果来自 "YouTube" → 可能是科普、评测
   - 如果来自 "Web文章" → 可能是新闻、观点

**你的判断**: （用1-2句话说明选题意图）

---

### Step 2: 分析已有素材

**思考**:
1. 已有 {ref_count} 条素材说明什么？
   - 如果数量 >= 2 且来自同一平台 → 说明这个话题在该平台有热度
   - 标题中的关键词（如"实测"、"教程"、"深度"）暗示内容类型

2. 这些素材已经覆盖了哪些内容？还缺什么？
   - 已有: 视频本身可能包含操作演示、方法讲解
   - 缺少: 可能缺理论支撑、数据验证、多样化案例

**你的判断**: （说明已有素材的价值和缺口）

---

### Step 3: 设计搜索策略

**优先级 1**: 是否需要搜索？

- 如果已有素材 >= 2条且质量高（来自爆款视频） → 可能无需额外搜索，直接分析已有素材即可
- 如果选题需要理论支撑 → 需要搜索学术资料
- 如果需要多样化案例 → 需要搜索社区经验

**优先级 2**: 如果需要搜索，搜什么？

**实战类选题**（学习方法、效率技巧、工具使用）:
- 优先: 中文实战社区（知乎、小红书、B站专栏）
- 次要: 英文实战资源（Reddit, Medium, GitHub实用工具）
- 避免: 学术论文（太理论，不适合实战）

**理论类选题**（技术原理、算法、学术综述）:
- 优先: 学术资源（Arxiv, GitHub开源实现, 官方文档）
- 次要: 技术博客
- 避免: 营销号文章

**观点类选题**（行业分析、趋势预测）:
- 优先: 权威观点（专家访谈、行业报告）
- 次要: 社区讨论（知乎高赞、HackerNews）

**优先级 3**: 关键词设计

- 如果选题包含中文俗语/黑话（如"2+3+5"） → 保留中文搜索，不要翻译
- 如果是通用概念 → 中英文结合
- 避免: 生硬直译专有名词

---

## 输出要求

请输出 ResearchPlan，包含:
- topic_category: 选题类型的简短标签（如"实战教程"、"理论分析"、"观点评论"）
- search_strategy: 你的搜索策略描述（1-2句话）
- search_instructions: 3-5个搜索指令，每个包含：
  * tool: "web_search" 或 "arxiv_search"
  * query: 具体搜索词
  * target: 期望找到什么
  * priority: 1-3（1最高）
- reasoning: 为什么选择这个策略

**关键词设计示例**:
- ✅ 好: "知乎 2+3+5 学习法"（保留中文黑话）
- ❌ 差: "2-3-5 time blocking study"（生硬翻译）
- ✅ 好: "Feynman technique practical guide"（通用概念用英文）
- ❌ 差: "费曼技巧 实用指南"（通用概念强行中文）

**重要**: 所有输出使用中文，但搜索词根据实际需要选择中英文
"""

    try:
        plan: ResearchPlan = get_llm_with_schema(
            user_prompt=user_prompt,
            response_model=ResearchPlan,
            capability="creative",  # Use creative for planning
            system_prompt="""你是一位专业的研究策略专家。你的任务是为深度分析找到最佳的一手资料来源。

核心原则：
- 所有输出必须使用中文
- 优先寻找一手资料而非二手信息
- 搜索策略要具体、可执行"""
        )

        print(f"\n📋 Research Plan Generated:")
        print(f"   Category: {plan.topic_category}")
        print(f"   Strategy: {plan.search_strategy}")
        print(f"   Search Instructions: {len(plan.search_instructions)} actions")

        return plan

    except Exception as e:
        print(f"⚠️ Research planning failed: {e}")
        # Fallback: 通用搜索策略
        return ResearchPlan(
            topic_category="general",
            search_strategy="Fallback to general web search due to planning error",
            search_instructions=[
                {
                    "tool": "web_search",
                    "query": f"{topic_brief.title} authoritative analysis",
                    "target": "General information",
                    "priority": 1
                }
            ],
            reasoning="Fallback strategy due to error"
        )


# ============================================
# Level 2: Excavator (智能萃取)
# ============================================

class ContentProcessor:
    """
    Level 2: Excavator - 挖掘与智能萃取

    功能: 从长文本中提取高信噪比的情报卡片
    模型: Fast Model (DeepSeek V3 / Gemini Flash) - 长文本 + 低成本
    """

    def __init__(self, reference_data: List[Dict[str, Any]] = None):
        self.search_gateway = SearchGateway()
        self.arxiv_searcher = ArxivSearcher()
        self.reference_data = reference_data or []  # 🔑 存储已有素材

    def execute_search_plan(self, plan: ResearchPlan, topic_title: str) -> List[Dict[str, Any]]:
        """
        执行搜索计划，获取原始数据

        Returns:
            List of raw search results with long text content
        """
        all_results = []

        # 按优先级排序
        sorted_instructions = sorted(
            plan.search_instructions,
            key=lambda x: x.get('priority', 99)
        )

        for instruction in sorted_instructions[:5]:  # 限制最多5个搜索
            tool = instruction.get('tool', 'web_search')
            query = instruction.get('query', '')
            target = instruction.get('target', '')

            print(f"\n🔍 Executing: {tool} | {query}")
            print(f"   Target: {target}")

            try:
                if tool == "analyze_existing":
                    # 🔑 新工具: 直接分析已有素材
                    results = self._analyze_existing_materials(query, target)
                    all_results.extend(results)

                elif tool == "arxiv_search":
                    results = self.arxiv_searcher.search(query, max_results=3)
                    for r in results:
                        all_results.append({
                            "source": r.get('title', 'Unknown'),
                            "url": r.get('url', ''),
                            "content": r.get('summary', ''),
                            "is_primary": True,  # Arxiv papers are primary sources
                            "search_target": target
                        })

                elif tool == "web_search":
                    # 🔑 使用 include_raw_content=True 获取完整文本
                    results = self.search_gateway.search(
                        query=query,
                        limit=3,
                        depth="advanced",
                        include_raw_content=True
                    )
                    for r in results:
                        # 优先使用 raw_content，否则使用摘要
                        content = r.get('raw_content', r.get('content', ''))
                        all_results.append({
                            "source": r.get('title', 'Unknown'),
                            "url": r.get('url', ''),
                            "content": content,
                            "is_primary": False,  # Web content needs verification
                            "search_target": target
                        })

                else:
                    print(f"   ⚠️ Unknown tool: {tool}, skipping")

            except Exception as e:
                print(f"   ❌ Search failed: {e}")
                continue

        print(f"\n✅ Collected {len(all_results)} raw sources")
        return all_results

    def _analyze_existing_materials(self, query: str, target: str) -> List[Dict[str, Any]]:
        """
        🔑 新功能: 分析已有素材（reference_data）

        参数:
            query: 分析关键词（用于筛选相关素材，"*" 表示分析所有）
            target: 期望提取的信息类型

        返回:
            标准化的搜索结果格式，供 extract_insights 使用
        """
        if not self.reference_data:
            print(f"   ⚠️ 无已有素材可分析")
            return []

        results = []
        query_lower = query.lower()

        for ref in self.reference_data[:10]:  # 最多分析10条
            # 提取基础信息
            title = ref.get('title', '')
            platform = ref.get('platform', '未知平台')
            author = ref.get('author_name', '未知作者')
            url = ref.get('url', '')
            view_count = ref.get('view_count', 0)

            # 提取描述/摘要作为内容
            raw_data = ref.get('raw_data', {})
            content = raw_data.get('description', '') or raw_data.get('summary', '')

            # 简单的相关性筛选（可选）
            is_relevant = (
                query_lower in title.lower() or
                query_lower in content.lower() or
                query == "*"  # "*" 表示分析所有素材
            )

            if is_relevant and content:
                results.append({
                    "source": f"[{platform}] {title} - {author}",
                    "url": url,
                    "content": f"""
**平台**: {platform}
**标题**: {title}
**作者**: {author}
**播放量**: {view_count:,}
**链接**: {url}

**内容描述**:
{content}
""",
                    "is_primary": True,  # 已收集的视频是一手素材
                    "search_target": target
                })
                print(f"   ✅ 匹配到素材: {title[:40]}...")

        print(f"   📦 从已有素材中提取了 {len(results)} 条相关内容")
        return results

    def extract_insights(self, raw_results: List[Dict[str, Any]], topic_title: str) -> List[KeyInsight]:
        """
        智能萃取: 从长文本中提取结构化情报卡片

        输入: 20k tokens 的原始杂乱文本
        输出: 结构化的 KeyInsight 卡片
        模型: Fast Model (低成本长文本处理)
        """

        insights = []

        for idx, result in enumerate(raw_results[:10], 1):  # 最多处理10个来源
            source = result.get('source', 'Unknown')
            url = result.get('url', '')
            content = result.get('content', '')
            is_primary = result.get('is_primary', False)

            if not content or len(content) < 50:
                continue

            # 截断过长内容 (最多15k tokens ≈ 60k chars)
            if len(content) > 60000:
                content = content[:60000] + "... [truncated]"

            print(f"\n📄 Extracting insights from [{idx}] {source[:50]}...")

            user_prompt = f"""
You are an expert information extractor. Extract KEY INSIGHTS from this source about the topic: "{topic_title}".

**Source**: {source}
**URL**: {url}
**Content**:
{content}

**Task**: Extract the MOST VALUABLE insights for understanding "{topic_title}".

**Extraction Rules**:
1. **Quote Original Text**: Copy exact quotes/data (NO fabrication)
2. **Filter Noise**: Ignore ads, fluff, promotional content
3. **Find Conflicts**: Identify claims that contradict mainstream views
4. **Verify Facts**: Mark confidence (high/medium/low)

**Output**: Up to 3 KeyInsight cards for this source.

**KeyInsight Schema**:
- source: Source name/title
- url: Source URL
- is_primary: true if this is first-hand (paper/official doc), false if secondary
- quote: Exact quote or data from the source (MUST be verbatim)
- insight: Your interpretation of why this matters for "{topic_title}"
- conflict: (optional) Does this contradict common beliefs?
- confidence: high/medium/low

**Example**:
```json
{{
  "source": "OpenAI Technical Report: GPT-4",
  "url": "https://arxiv.org/abs/2303.08774",
  "is_primary": true,
  "quote": "GPT-4 achieves human-level performance on various professional benchmarks",
  "insight": "This shows AI has reached capability threshold for professional work, implying major productivity shifts",
  "conflict": "Contradicts belief that AI can only do simple tasks",
  "confidence": "high"
}}
```

**CRITICAL**:
- If the content is irrelevant, return empty list
- If no solid facts/quotes, skip it
- Quality > Quantity
"""

            try:
                class MultiInsightOutput(BaseModel):
                    insights: List[KeyInsight] = Field(default_factory=list)

                result_obj: MultiInsightOutput = get_llm_with_schema(
                    user_prompt=user_prompt,
                    response_model=MultiInsightOutput,
                    capability="creative",  # Fast model for extraction
                    system_prompt="""你是一位专业的信息提取专家。你的任务是从长文本中提取可验证的事实和原文引用。

核心原则：
- 所有输出必须使用中文
- 只提取可验证的事实，拒绝编造
- 保留原文引用（quote字段），确保准确性
- 如果内容不相关，返回空列表"""
                )

                extracted = result_obj.insights
                if extracted:
                    insights.extend(extracted)
                    print(f"   ✅ Extracted {len(extracted)} insights")
                else:
                    print(f"   ⚠️ No insights extracted (likely irrelevant)")

            except Exception as e:
                print(f"   ❌ Extraction failed: {e}")
                continue

        print(f"\n✅ Total Insights Extracted: {len(insights)}")
        return insights


# ============================================
# Level 3: Philosopher (认知重构)
# ============================================

def deep_analysis(
    topic_brief: TopicBrief,
    insights: List[KeyInsight]
) -> DeepAnalysisReport:
    """
    Level 3: Philosopher - 基于事实进行逻辑外科手术

    输入: 高信噪比的情报卡片
    输出: 深度研报
    模型: Reasoning Model (DeepSeek-R1 / Kimi K2 / Claude 3.5 Sonnet)
    """

    # 准备情报卡片上下文
    insights_context = ""
    for idx, insight in enumerate(insights[:15], 1):  # 最多使用15个洞察
        insights_context += f"""
【情报卡片 {idx}】
来源: {insight.source}
链接: {insight.url}
一手资料: {'是' if insight.is_primary else '否'}
原文引用: {insight.quote}
价值解读: {insight.insight}
冲突点: {insight.conflict if insight.conflict else '无'}
可信度: {insight.confidence}
---
        """.strip() + "\n\n"

    user_prompt = f"""
You are a top-tier research analyst with expertise in First Principles Thinking, Dialectics, and Mental Models.

**Topic**: {topic_brief.title}
**Core Angle**: {topic_brief.core_angle}
**Rationale**: {topic_brief.rationale}

**Intelligence Cards** (Verified Facts):
{insights_context}

**Your Mission**: Transform these facts into a DEEP ANALYSIS REPORT that reveals the UNDERLYING LOGIC and CONTRARIAN INSIGHTS.

---

## 🧠 Thinking Framework

### 1. **First Principles Thinking** (第一性原理)
- Ask "WHY" 5 times to reach the root cause
- Strip away assumptions and get to fundamental truths
- Example: "Why is RAG popular?" → "Why do LLMs hallucinate?" → "Why is training data limited?" → ... → **Root: Information is sparse in reality**

### 2. **Dialectic Method** (辩证法)
- Find the OPPOSITE of mainstream views
- Construct conflicts and contradictions
- Example: Mainstream = "AI will replace humans" | Contrarian = "AI amplifies human uniqueness"

### 3. **Mental Models** (思维模型库)
Auto-match relevant models from:
- **Physics**: Entropy (熵增定律), Energy Conservation
- **Economics**: Network Effects, Marginal Cost, Supply/Demand
- **Psychology**: Loss Aversion (损失厌恶), Cognitive Bias
- **Evolution**: Selection Pressure, Adaptation

---

## 📋 Output Structure: DeepAnalysisReport

### A. **Fact Layer** (事实层)
- `hard_evidence`: List of verified facts with citations (e.g., "[Source: Arxiv] GPT-4 achieves 86% on MMLU")
- `verified_facts`: Structured list of key facts with sources

### B. **Logic Layer** (逻辑层)
- `root_cause`: The FUNDAMENTAL reason (from 5-Why analysis)
- `theoretical_model`: Which mental model applies (e.g., "Network Effects", "Entropy")
- `first_principles_analysis`: The step-by-step reasoning from basics

### C. **Insight Layer** (洞察层)
- `mainstream_view`: What most people think
- `contrarian_view`: The counter-intuitive insight (HIGH VALUE)
- `conflict_analysis`: Where does the contradiction lie?

### D. **Narrative Layer** (叙事层)
- `emotional_hook`: Which deep human emotion does this touch? (Greed, Fear, Laziness, Curiosity, Pride)
- `content_strategy`: Concrete advice for the Writer Agent (e.g., "Open with shocking stat, use before/after structure")

### E. **Metadata**
- `sources_used`: List of KeyInsights used
- `confidence_score`: Overall confidence (0-1)

---

## 🎯 Quality Standards

**MUST HAVE**:
✅ Every claim must cite a source
✅ Root cause must be non-obvious (not surface-level)
✅ Contrarian view must be backed by logic/data
✅ Emotional hook must be specific (not generic)

**MUST AVOID**:
❌ Generic statements ("AI is changing the world")
❌ Fabricated quotes or data
❌ Obvious observations without depth
❌ Buzzwords without substance

---

## 💡 Example (Partial)

**Topic**: "RAG vs Long Context"

**hard_evidence**:
- "[Arxiv 2024] GPT-4 with 128k context still hallucinates on needle-in-haystack tests"
- "[Anthropic Blog] Claude 2 retrieves facts with 99% accuracy using RAG vs 87% with long context"

**root_cause**: "Information retrieval is fundamentally a search problem, not a storage problem. Long context = storing everything; RAG = indexing smartly. Physics favors indexing (lower entropy)."

**theoretical_model**: "Entropy (熵增定律) - Systems tend toward disorder. Long context increases disorder (noise); RAG maintains order (structured retrieval)."

**contrarian_view**: "Mainstream believes 'longer context = better'. But physics says: unlimited context creates infinite noise. RAG wins because it REDUCES entropy."

**emotional_hook**: "Fear - Developers fear RAG complexity. But long context is a trap: you're drowning in noise."

**content_strategy**: "Open with shocking stat: 'GPT-4 fails 13% of retrieval with 128k context'. Then reveal: RAG = 99% accuracy. Use analogy: Long context = hoarding; RAG = Marie Kondo."

---

**Now, analyze the intelligence cards and produce your DeepAnalysisReport.**

**🔑 关键要求**:
- 所有字段必须使用中文输出
- 包括 root_cause, mainstream_view, contrarian_view, emotional_hook 等所有文本字段
- 保持专业性和分析深度
"""

    try:
        report: DeepAnalysisReport = get_llm_with_schema(
            user_prompt=user_prompt,
            response_model=DeepAnalysisReport,
            capability="reasoning",  # 🔑 Use reasoning model for deep analysis
            system_prompt="""你是一位世界级的深度分析专家，融合了：
- 科学家的严谨性（验证一切）
- 哲学家的洞察力（发现深层真理）
- 故事讲述者的表达力（清晰传达）

核心原则：
1. 所有输出必须使用中文
2. 每个结论必须有证据支撑
3. 追求反直觉的洞察（而非显而易见的观点）
4. 使用思维模型解释"为什么"
5. 让分析结果可用于内容创作"""
        )

        # 填充元数据
        report.topic_id = topic_brief.id
        report.topic_title = topic_brief.title
        report.sources_used = insights

        print(f"\n✅ Deep Analysis Completed:")
        print(f"   Root Cause: {report.root_cause[:80]}...")
        print(f"   Contrarian View: {report.contrarian_view[:80]}...")
        print(f"   Confidence: {report.confidence_score}")

        return report

    except Exception as e:
        print(f"❌ Deep analysis failed: {e}")
        # 返回空报告
        return DeepAnalysisReport(
            topic_id=topic_brief.id,
            topic_title=topic_brief.title,
            hard_evidence=["Analysis failed due to error"],
            root_cause="Unable to determine",
            confidence_score=0.0
        )


# ============================================
# Main Workflow: Three-Level Rocket
# ============================================

def run_analyst(topic_brief: TopicBrief) -> DeepAnalysisReport:
    """
    完整的分析流程: Scout → Excavator → Philosopher

    输入: TopicBrief (来自 Radar Agent)
    输出: DeepAnalysisReport (给 Writer Agent)
    """

    print("\n" + "="*60)
    print("🚀 ANALYST AGENT - Three-Level Rocket Launch")
    print("="*60)

    # 🚀 Level 1: Scout - 动态侦察规划
    print("\n🚀 Level 1: Adaptive Scout - Planning Research Strategy")
    research_plan = plan_research_strategy(topic_brief)

    # 🚀 Level 2: Excavator - 挖掘与萃取
    print("\n🚀 Level 2: Excavator - Digging and Extracting Insights")
    processor = ContentProcessor(reference_data=topic_brief.reference_data)  # 🔑 传递已有素材

    # 2.1 执行搜索计划
    raw_results = processor.execute_search_plan(research_plan, topic_brief.title)

    # 2.2 智能萃取
    insights = processor.extract_insights(raw_results, topic_brief.title)

    if not insights:
        print("⚠️ No insights extracted! Falling back to basic report.")
        return DeepAnalysisReport(
            topic_id=topic_brief.id,
            topic_title=topic_brief.title,
            hard_evidence=["No data collected"],
            root_cause="Insufficient information",
            confidence_score=0.1
        )

    # 🚀 Level 3: Philosopher - 认知重构
    print("\n🚀 Level 3: Philosopher - Deep Analysis & Reconstruction")
    report = deep_analysis(topic_brief, insights)

    print("\n" + "="*60)
    print("✅ ANALYST AGENT - Mission Complete")
    print("="*60)

    return report


# ============================================
# LangGraph Node Interface
# ============================================

def analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph 节点接口

    输入 state 字段:
    - proposals: List[TopicBrief] (来自 Radar Agent)

    输出 state 字段:
    - analysis_reports: List[DeepAnalysisReport]
    """

    from core.state import RadarState

    # 🔑 修复: state 可能是 RadarState 对象或字典，兼容处理
    if isinstance(state, dict):
        proposals = state.get("proposals", [])
        logs = state.get("logs", [])
    else:
        # RadarState 对象
        proposals = state.proposals if hasattr(state, 'proposals') else []
        logs = state.logs if hasattr(state, 'logs') else []

    if not proposals:
        print("⚠️ No proposals to analyze")
        return {"logs": logs + ["【Analyst】跳过: 无选题"]}

    reports = []

    for idx, proposal_item in enumerate(proposals[:3], 1):  # 最多分析3个选题
        print(f"\n{'='*60}")
        print(f"Analyzing Proposal {idx}/{min(len(proposals), 3)}")
        print(f"{'='*60}")

        # 转换为 TopicBrief 对象
        try:
            # 🔑 兼容处理：可能是字典或已经是 TopicBrief 对象
            if isinstance(proposal_item, TopicBrief):
                topic_brief = proposal_item
            elif isinstance(proposal_item, dict):
                topic_brief = TopicBrief(**proposal_item)
            else:
                print(f"⚠️ Unknown proposal type: {type(proposal_item)}, skipping")
                continue

            report = run_analyst(topic_brief)
            reports.append(report.model_dump())
        except Exception as e:
            print(f"❌ Failed to analyze proposal {idx}: {e}")
            import traceback
            traceback.print_exc()
            continue

    return {
        "analysis_reports": reports,
        "logs": logs + [f"【Analyst】完成 {len(reports)} 个深度分析"]
    }


if __name__ == "__main__":
    # 测试代码
    print("=== Testing Analyst Agent ===\n")

    # 创建测试 TopicBrief
    test_topic = TopicBrief(
        id="test_001",
        title="AI绘图技术",
        core_angle="Stable Diffusion vs MidJourney 技术对比",
        rationale="高热度话题，技术深度足够",
        source_type="tech_news",
        reference_data=[{"platform": "youtube", "title": "AI Art Tutorial"}]
    )

    # 运行分析
    report = run_analyst(test_topic)

    # 打印结果
    print("\n" + "="*60)
    print("FINAL REPORT")
    print("="*60)
    print(f"Topic: {report.topic_title}")
    print(f"\nRoot Cause: {report.root_cause}")
    print(f"\nMainstream View: {report.mainstream_view}")
    print(f"\nContrarian View: {report.contrarian_view}")
    print(f"\nEmotional Hook: {report.emotional_hook}")
    print(f"\nConfidence: {report.confidence_score}")

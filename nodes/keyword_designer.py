"""
搜索词设计师 v2.0
核心改进: 结构化输出，每个主题生成配对的中英文搜索词
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from core.state import RadarState, TopicSearchQueries
from core.llm import get_llm_with_schema
from datetime import datetime


class KeywordDesignerOutputV2(BaseModel):
    """搜索词设计输出 v2.0"""
    topic_queries: List[TopicSearchQueries] = Field(..., description="结构化的主题搜索词列表")
    reasoning: str = Field(..., description="设计理由")


def run_keyword_designer(state: RadarState) -> Dict[str, Any]:
    """
    节点: 搜索词设计师 v2.0

    功能: 为每个主题生成配对的中英文搜索词
    输出: topic_queries (结构化搜索词)
    """
    print("\n--- 节点: 搜索词设计师 v2.0 (Node: Keyword Designer) ---")

    # 获取目标领域和用户输入
    target_domains = state.target_domains
    user_topics = state.session_focus.get("priority_topics", [])

    # 合并主题
    all_topics = list(set(target_domains + user_topics))

    if not all_topics:
        print("⚠️ 没有目标主题，使用默认")
        all_topics = ["AI News"]

    # 获取当前日期
    current_year = datetime.now().strftime("%Y")
    current_month_num = datetime.now().strftime("%m")
    current_month_zh = datetime.now().strftime("%Y年%m月")  # 中文友好格式

    topics_str = ", ".join(all_topics)

    user_prompt = f"""
Role: You are a Cross-Platform Video SEO Expert specializing in YouTube (Global) and Bilibili (China).
Goal: Design high-performance, ambiguity-free search queries for topics: {topics_str}
Current Date: {current_month_zh}

# 🎯 CORE PRINCIPLES FOR CROSS-PLATFORM QUERY DESIGN (2025 Research-Based):

## 1. YouTube Search Optimization (Research-Based 2025)

### A. KEYWORD LENGTH STRATEGY
**CRITICAL**: YouTube's algorithm favors **3-5 word queries** for broad discovery, **4-8 word long-tail** for precision.

**Length Rules**:
- ✅ **Sweet Spot**: 3-5 words for content queries, 4-8 for discovery
- ❌ **Avoid**: 1-2 words (too competitive), 9+ words (too specific, zero results)

**Examples**:
```
Too Short (1-2 words): "AI video" → 10M results, impossible to rank
✅ OPTIMAL (3-5 words): "AI filmmaking tutorial {current_year}" → Target-able
Long-Tail (4-8 words): "best AI video generation channels {current_year}" → Low competition
Too Long (9+ words): "AI short drama workflow tutorial step-by-step guide {current_year}" → Zero results
```

### B. NATURAL LANGUAGE PATTERNS
**Principle**: Match how real users type in the search bar.

**Intent-Based Templates**:
- Tutorial: "[topic] tutorial {current_year}", "how to [action]", "[topic] guide"
- Discovery: "best [topic] channels {current_year}", "top [topic] creators {current_year}"
- Review: "[topic] review {current_year}", "[product] explained"

**Real User Test**: Ask "Would a normal person type this exact phrase?" If NO → simplify.

### C. AMBIGUITY AVOIDANCE
**Word Traps to Avoid**:
1. **"Short"** → Triggers YouTube Shorts (60s vertical videos)
   - ❌ "AI short drama tutorial" → Returns Shorts
   - ✅ "AI video series tutorial" OR "AI mini-series guide"

2. **"Quick"** → May trigger Shorts
   - ❌ "quick AI tutorial" → Shorts contamination
   - ✅ "AI tutorial for beginners"

3. **Overly Compound Concepts** → Confuses algorithm
   - ❌ "AI video drama workflow production" (4 concepts)
   - ✅ "AI filmmaking workflow" (2 concepts)

### D. TIME ANCHORING
- ✅ Use YEAR only: "{current_year}"
- ❌ NO month: YouTube catalog updates slowly, month filters kill discoverability

## 2. Bilibili Search Optimization (Platform-Specific 2025)

### A. COMMUNITY SLANG (B站黑话)
**Critical**: Bilibili users respond to platform-specific terminology, NOT generic Chinese.

**High-Value Slang Terms**:
- 教程 → **"保姆级教程"** (nanny-level = extremely detailed)
- 教程 → **"全流程教学"** (full workflow)
- 评测 → **"深度评测"** (deep review)
- 推荐 → **"避坑指南"** (pitfall guide)
- 内容 → **"干货"** (pure valuable content, no fluff)
- 教程 → **"实操"** (hands-on practical)
- 推荐 → **"良心盘点"** (conscientious roundup)

**Quality Signals** (Anti-Repost):
- Add **"原创"** (original) to filter out reposts
- ✅ "原创AI视频教程" > "AI视频教程"

### B. TIME FORMAT - AMBIGUITY KILLER
**CRITICAL ISSUE**: Month numbers trigger e-commerce!

**Dangerous Patterns**:
- ❌ "2025-11" → Triggers "双11" (Singles Day shopping festival)
- ❌ "2025-06" → Triggers "618" (JD.com shopping festival)
- ❌ "11月" standalone → Shopping contamination

**Safe Patterns**:
- ✅ "2025年11月" → Full format reduces ambiguity
- ✅ "{current_year}年" → Year only (safest)
- ✅ "最新" (latest) → Time-agnostic, algorithmically fresh

**Example**:
```
❌ WRONG: "AI最新动态 深度解析 2025-11"
         → Returns: "2025年双11手机推荐！" (shopping)

✅ RIGHT: "AI最新动态 深度解析 {current_year}年"
         → Returns: Actual AI news content
```

### C. KEYWORD LENGTH
- ✅ **Optimal**: 5-8 Chinese characters (equals 3-5 English words in info density)
- Examples: "AI视频制作 保姆级教程" (11 chars, high value)

### D. PLATFORM CULTURAL FIT
- Use **"UP主"** (not just "博主") → Bilibili-native term for creators
- Add **"B站"** when doing discovery → "B站顶级AI UP主推荐"

## 3. Query Type Strategies

### A. Discovery Queries (找博主/Influencers)
**Goal**: Find articles/videos that RECOMMEND top creators

**YouTube (4-8 words long-tail)**:
```
Pattern: "best [topic] [channels/creators] {{year}}"
Examples:
- "best AI filmmaking channels {current_year}"
- "top Python tutorial creators {current_year}"
- "who to follow for tech reviews {current_year}"
```

**Bilibili (5-8 chars + B站黑话)**:
```
Pattern: "[B站/顶级/优质] [topic] [UP主] [推荐/盘点] {{year}}"
Examples:
- "B站顶级AI视频UP主推荐 {current_year}年"
- "优质Python教程UP主良心盘点 {current_year}年"
- "科技评测UP主避坑指南" (avoid month!)
```

**CRITICAL**: MUST use "UP主" (not "博主") for Bilibili authenticity.

### B. Content Queries (搜视频/Videos)
**Goal**: Find high-quality video content

**YouTube (3-5 words + intent)**:
```
Pattern Templates:
- "[topic] tutorial {current_year}"
- "[topic] guide"
- "[topic] explained"
- "how to [action]"

Real Examples:
- "AI filmmaking tutorial {current_year}" ✅ (NOT "AI short drama workflow tutorial")
- "Python beginner guide" ✅ (NOT "Python programming tutorial for beginners step-by-step")
- "tech review {current_year}" ✅ (NOT "comprehensive technology product review comparison")

Ambiguity Check:
- Does query contain "short"? → Replace with "video series" OR "mini-series"
- Does query contain "quick"? → Replace with "beginner" OR "fast"
- Word count > 5? → Simplify to core 3-5 words
```

**Bilibili (5-8 chars + B站黑话)**:
```
Pattern Templates (AMBIGUITY-FREE):
- Tech/Tutorial: "[topic] [保姆级教程/全流程/实操] {current_year}年"
- News: "[topic] [最新动态/深度解析] 最新" ← Use "最新" NOT month!
- Review: "[topic] [深度评测/避坑指南] {current_year}年"

Real Examples:
- "AI视频制作 保姆级教程 {current_year}年" ✅
- "AI最新动态 深度解析 最新" ✅ (NOT "2025-11" → shopping!)
- "科技产品 深度评测 避坑指南 {current_year}年" ✅

Ambiguity Killers:
- NEVER use "2025-11", "2025-06", "618", "双11"
- ALWAYS use "{current_year}年11月" (full format) OR "最新" (latest)
- Does query trigger e-commerce? → Remove month, add "原创" filter
```

## 4. Cross-Platform Pairing & Quality Standards

**Paired Queries MUST**:
1. Same topic, different cultural adaptation (NOT translation)
2. Match intent (both discovery OR both content)
3. Pass ambiguity checks

**Quality Checklist** (Every query):
- [ ] Word count: YouTube 3-5, Bilibili 5-8 chars
- [ ] No ambiguity triggers ("short", "11", "618")
- [ ] Platform-native terms (YouTube: natural English, Bilibili: UP主/保姆级/干货)
- [ ] Time format correct (YouTube: year only, Bilibili: avoid "-11")
- [ ] Real user test: "Would someone actually type this?"

## 5. OUTPUT FORMAT

Return KeywordDesignerOutputV2 with 4 queries per topic:
```
discovery_query_en: "[4-8 words long-tail] best [topic] channels {current_year}"
discovery_query_zh: "[B站黑话] [topic] UP主推荐 {current_year}年"
content_query_en: "[3-5 words + intent] [topic] tutorial {current_year}"
content_query_zh: "[topic] [保姆级/全流程/深度] 最新"  ← Use "最新" NOT month!
```

**CRITICAL REMINDER**:
- You are a cultural adapter, NOT a translator
- Bilibili in November? Use "最新" OR "{current_year}年" (NOT "2025-11" → shopping!)
- YouTube with "short" topic? Use "video series" OR "mini-series" (NOT "short" → Shorts!)

Now generate queries for: {topics_str}
    """

    try:
        result: KeywordDesignerOutputV2 = get_llm_with_schema(
            user_prompt=user_prompt,
            response_model=KeywordDesignerOutputV2,
            capability="reasoning",
            system_prompt="你是一个专业的搜索引擎优化专家，擅长设计精准的中英文搜索词。"
        )

        print(f"\n✅ 搜索词设计: {len(result.topic_queries)} 个主题")
        for idx, tq in enumerate(result.topic_queries, 1):
            print(f"   [{idx}] {tq.topic}")

        # 转换为字典列表
        topic_queries_dicts = [tq.model_dump() for tq in result.topic_queries]

        # 同时保留兼容性：生成旧格式的 discovery_queries 和 content_queries
        discovery_queries = []
        content_queries = []
        for tq in result.topic_queries:
            discovery_queries.extend([tq.discovery_query_en, tq.discovery_query_zh])
            content_queries.extend([tq.content_query_en, tq.content_query_zh])

        return {
            "topic_queries": topic_queries_dicts,
            "discovery_queries": discovery_queries,
            "content_queries": content_queries,
            "logs": state.logs + [f"【搜索词】设计完成: {len(result.topic_queries)} 个主题"]
        }

    except Exception as e:
        print(f"❌ 搜索词设计失败: {e}")

        # 兜底策略：为每个主题生成简单的中英文搜索词（使用安全格式）
        fallback_queries = []
        for topic in all_topics:
            fallback_queries.append(TopicSearchQueries(
                topic=topic,
                discovery_query_en=f"best {topic} YouTube channels {current_year}",
                discovery_query_zh=f"B站顶级{topic} UP主推荐 {current_year}年",
                content_query_en=f"{topic} tutorial {current_year}",
                content_query_zh=f"{topic} 最新动态 最新"  # 使用"最新"而不是具体月份
            ))

        fallback_dicts = [tq.model_dump() for tq in fallback_queries]

        discovery_queries = []
        content_queries = []
        for tq in fallback_queries:
            discovery_queries.extend([tq.discovery_query_en, tq.discovery_query_zh])
            content_queries.extend([tq.content_query_en, tq.content_query_zh])

        return {
            "topic_queries": fallback_dicts,
            "discovery_queries": discovery_queries,
            "content_queries": content_queries,
            "logs": state.logs + [f"【搜索词】使用兜底策略: {e}"]
        }

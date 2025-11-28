from typing import Dict, Any, List
from pydantic import BaseModel, Field
from core.state import RadarState
from core.llm import get_llm_with_schema

class InfluencerInfo(BaseModel):
    """博主信息"""
    name: str = Field(..., description="博主名称")
    platform: str = Field(..., description="平台: youtube 或 bilibili")
    identifier: str = Field(..., description="博主标识（@handle, 频道URL, 或 UP主ID）")
    mention_count: int = Field(default=1, description="在文章中出现次数（权重）")
    source_url: str = Field(default="", description="来源文章URL")
    confidence: str = Field(default="medium", description="置信度: high/medium/low")

class InfluencerExtractorOutput(BaseModel):
    """提取的博主列表"""
    influencers: List[InfluencerInfo] = Field(default_factory=list, description="发现的博主列表")
    summary: str = Field(..., description="提取总结")
    total_sources_analyzed: int = Field(default=0, description="分析的文章数量")

def run_influencer_extractor(state: RadarState) -> Dict[str, Any]:
    """
    节点: 博主提取器 (Influencer Extractor)

    功能: 从 Web 搜索结果中提取顶级博主信息
    - 输入: state.leads (Web 搜索结果)
    - 输出: discovered_influencers (博主列表)
    """
    print("\n--- 节点: 博主提取器 (Node: Influencer Extractor) ---")

    # 获取 Web 搜索结果
    web_results = state.leads
    if not web_results:
        print("⚠️ 没有 Web 搜索结果，跳过博主提取")
        return {
            "discovered_influencers": [],
            "logs": state.logs + ["【博主提取】跳过: 无 Web 搜索结果"]
        }

    # 准备上下文：汇总所有 Web 搜索结果
    context_parts = []
    for idx, lead in enumerate(web_results, 1):
        context_parts.append(f"""
【文章 {idx}】
标题: {lead.title}
URL: {lead.url}
摘要: {lead.snippet}
标签: {', '.join(lead.tags) if lead.tags else '无'}
        """.strip())

    context_str = "\n\n".join(context_parts)
    target_domains = ", ".join(state.target_domains) if state.target_domains else "未指定领域"

    user_prompt = f"""
Role: You are an expert at extracting content creator information from articles.
Target Domain: {target_domains}

Article Data:
{context_str}

Task: Extract top content creators mentioned in these articles.

🔑 **PLATFORM IDENTIFICATION STRATEGY** (分层提取):

## Tier 1: High Confidence (Preferred)
**Extract WITH platform fingerprint**:

1. **YouTube**:
   - ✅ "@channelname" (e.g., "@MKBHD")
   - ✅ "youtube.com/@handle"
   - ✅ "youtube.com/c/ChannelName"
   - → `confidence="high"`

2. **Bilibili**:
   - ✅ "UID: 946974"
   - ✅ "space.bilibili.com/946974"
   - → `confidence="high"`

## Tier 2: Medium Confidence (Acceptable) - ⭐ PRIORITIZE THIS TIER
**Extract name-only IF the creator is clearly recommended**:

**CRITICAL**: Most articles don't include @handles or UIDs! Extract the name anyway!

1. **YouTube**:
   - ⚠️ "Two Minute Papers" (no @, but clearly a YouTube channel)
   - ⚠️ "MKBHD" (well-known tech reviewer)
   - ⚠️ "Corridor Digital" (production team)
   - → `confidence="medium"`, `identifier=name`

2. **Bilibili**:
   - ⚠️ "李永乐老师" (famous science educator)
   - ⚠️ "影视飓风" (well-known production team)
   - ⚠️ "老番茄" (gaming creator)
   - → `confidence="medium"`, `identifier=name`

**Requirements for Tier 2** (Looser requirements):
- Article mentions this creator in ANY positive context
- Name appears in article content (doesn't have to be in title)
- Clear indication this is a content creator (not article author)
- **NO need for @handle or UID** - we'll search by name later!

## Tier 3: Low Confidence (Extract but flag)
**Ambiguous cases**:
- Mentioned in passing
- Unclear if creator or subject
- → `confidence="low"`, `identifier=name`

## DO NOT Extract:
- ❌ Article authors (unless article is about recommending creators)
- ❌ Random names without context
- ❌ Subjects of videos (not the creator)

## identifier Field Strategy:
```
if @handle or URL available:
    identifier = "@handle" or "URL"
    confidence = "high"
else if clear creator recommendation:
    identifier = name
    confidence = "medium"
else:
    identifier = name
    confidence = "low"
```

**Examples**:

✅ Tier 1 (High Confidence):
```json
{{
  "name": "MKBHD",
  "platform": "youtube",
  "identifier": "@MKBHD",
  "confidence": "high"
}}
```

✅ Tier 2 (Medium - Acceptable):
```json
{{
  "name": "Two Minute Papers",
  "platform": "youtube",
  "identifier": "Two Minute Papers",  // No @handle, but clearly recommended
  "confidence": "medium"
}}
```

⚠️ Tier 3 (Low - Extract but risky):
```json
{{
  "name": "Ken Jee",
  "platform": "youtube",
  "identifier": "Ken Jee",
  "confidence": "low"  // Might be irrelevant, but extract anyway
}}
```
→ Note: Low confidence will be deprioritized in task queue

❌ DO NOT Extract:
```json
{{
  "name": "John Doe",  // Article author
  "platform": "youtube",
  "identifier": "John Doe",
  "confidence": "low"
}}
```
→ This is the article author, not a recommended creator

**Strategy** (In order of importance):
1. **MAXIMIZE Tier 2**: Most real articles don't have @handles - extract names aggressively!
2. Prefer Tier 1 (with @handle/UID) when available
3. Include Tier 3 for completeness (mark as low confidence)
4. Quality gate and search algorithms will filter bad results later

**Better to over-extract than under-extract** - The system can handle false positives via:
- Priority de-ranking (low confidence = priority 45 < keyword search priority 50)
- Quality gate filtering during search
- Deduplica if multiple sources mention same creator

**Common Mistake to Avoid**:
❌ "No @handle found, skip this creator" → TOO STRICT
✅ "No @handle, but creator mentioned → extract with medium/low confidence"

**Output**: Return InfluencerExtractorOutput with ALL discovered creators, even without handles.
    """

    try:
        result: InfluencerExtractorOutput = get_llm_with_schema(
            user_prompt=user_prompt,
            response_model=InfluencerExtractorOutput,
            capability="creative",  # 使用 creative 能力处理长上下文
            system_prompt="""你是一个专业的信息提取专家，擅长从文章中提取博主和内容创作者信息。

核心原则: 宁可多提取也不要漏掉有价值的创作者！
- 即使没有@handle或UID，只要文章提到创作者名字，就应该提取
- 标记适当的confidence等级，让下游系统决定是否使用
- 不要因为信息不完整就跳过提取"""
        )

        # 按平台分组统计
        youtube_influencers = [i for i in result.influencers if i.platform == "youtube"]
        bilibili_influencers = [i for i in result.influencers if i.platform == "bilibili"]

        print(f"✅ 博主提取: {len(result.influencers)} 个 (YT:{len(youtube_influencers)} BL:{len(bilibili_influencers)})")

        # 按优先级排序：高置信度 > 多次提及 > 中置信度 > 低置信度
        confidence_score = {"high": 3, "medium": 2, "low": 1}
        sorted_influencers = sorted(
            result.influencers,
            key=lambda x: (confidence_score.get(x.confidence, 1), x.mention_count),
            reverse=True
        )

        # 🔑 显示提取到的博主详情（所有）
        if sorted_influencers:
            print(f"\n📋 提取到的博主列表:")
            for idx, inf in enumerate(sorted_influencers, 1):
                identifier_str = inf.identifier if inf.identifier else "无identifier"
                print(f"   [{idx}] {inf.name} | {inf.platform} | {inf.confidence} | {identifier_str[:40]}")

        # 🔑 先转换为字典，然后去重
        influencer_dicts_raw = [inf.model_dump() for inf in sorted_influencers]
        influencer_dicts = _deduplicate_influencers(influencer_dicts_raw)

        return {
            "discovered_influencers": influencer_dicts,
            "plan_status": "planning",  # 🔑 重置状态，让 Planner 继续规划
            "logs": state.logs + [
                f"【博主提取】发现 {len(result.influencers)} 个博主 (YouTube: {len(youtube_influencers)}, Bilibili: {len(bilibili_influencers)})"
            ]
        }

    except Exception as e:
        print(f"❌ 博主提取失败: {e}")
        # 兜底策略：返回空列表
        return {
            "discovered_influencers": [],
            "plan_status": "planning",  # 继续让 Planner 规划
            "logs": state.logs + [f"【博主提取】失败: {e}"]
        }


def _deduplicate_influencers(influencers: List) -> List:
    """去重博主，合并相同的"""
    deduped = {}
    for inf in influencers:
        identifier = inf.get("identifier", "").strip().lower() if inf.get("identifier") else inf.get("name", "").lower()
        key = f"{inf.get('platform')}:{identifier}"

        if key in deduped:
            # 合并：累加提及次数，保留最高置信度
            deduped[key]["mention_count"] += inf.get("mention_count", 1)
            if inf.get("confidence") == "high":
                deduped[key]["confidence"] = "high"
        else:
            deduped[key] = inf

    return list(deduped.values())

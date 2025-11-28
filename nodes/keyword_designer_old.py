from typing import Dict, Any, List
from pydantic import BaseModel, Field
from core.state import RadarState
from core.llm import get_llm_with_schema
from datetime import datetime

class KeywordDesignerOutput(BaseModel):
    """搜索词设计输出"""
    discovery_queries: List[str] = Field(..., description="发现博主的搜索词（用于找推荐文章）")
    content_queries: List[str] = Field(..., description="发现内容的搜索词（用于直接搜索视频）")
    reasoning: str = Field(..., description="设计理由")

def run_keyword_designer(state: RadarState) -> Dict[str, Any]:
    """
    节点: 搜索词设计师 (Keyword Designer)

    功能: 为双引擎设计精准搜索词
    - discovery_queries: 用于发现头部博主（引擎 1 准备）
    - content_queries: 用于直接搜索内容（引擎 2）
    """
    print("\n--- 节点: 搜索词设计师 (Node: Keyword Designer) ---")

    target_domains = state.target_domains
    if not target_domains:
        print("⚠️ 没有目标领域，使用默认搜索词")
        return {
            "discovery_queries": ["best YouTube channels 2025", "顶级博主推荐"],
            "content_queries": ["trending videos 2025"],
            "logs": state.logs + ["使用默认搜索词"]
        }

    # 获取当前日期
    current_year = datetime.now().strftime("%Y")
    current_month = datetime.now().strftime("%Y-%m")

    target_str = ", ".join(target_domains)

    user_prompt = f"""
    目标领域: {target_str}
    当前日期: {current_month}

    任务: 为双引擎内容发现系统设计精准搜索词。

    **背景**: 我们有两个发现引擎:

    🔴 引擎 1 (头部博主监控):
       - 目标: 找到该领域的顶级博主/频道
       - 方法: 先搜索推荐文章 → 提取博主列表 → 监控他们的内容
       - 需要: discovery_queries（发现博主的搜索词）

    🔵 引擎 2 (关键词搜索):
       - 目标: 广泛搜索该领域的内容，横向对比找爆款
       - 方法: 直接搜索视频/文章
       - 需要: content_queries（搜索内容的搜索词）

    **要求**:

    1. discovery_queries (3-5 个):
       - 目的: 找到"推荐文章"（如 "2025年必看的AI频道"）
       - 英文示例: "best {target_domains} YouTube channels {current_year}"
       - 英文示例: "top {target_domains} influencers to follow {current_year}"
       - 中文示例: "顶级{target_domains}博主推荐"
       - 中文示例: "必看的{target_domains}UP主"

    2. content_queries (3-5 个):
       - 目的: 直接搜索视频内容
       - 必须包含时间限定（{current_year} 或 {current_month}）
       - 英文示例: "{target_domains} news {current_month}"
       - 英文示例: "latest {target_domains} {current_year}"
       - 中文示例: "{target_domains}最新动态 {current_month}"
       - 中文示例: "{target_domains}教程 {current_year}"

    **注意**:
    - discovery_queries 应该能找到"推荐文章"、"频道合集"
    - content_queries 应该能直接找到视频内容
    - 两类搜索词的目的不同，不要混淆
    - 同时包含中英文搜索词，覆盖两个平台
    """

    try:
        result: KeywordDesignerOutput = get_llm_with_schema(
            user_prompt=user_prompt,
            response_model=KeywordDesignerOutput,
            capability="reasoning",
            system_prompt="你是一个专业的搜索引擎优化专家，擅长设计精准的搜索词。"
        )

        print(f"✅ 搜索词设计完成:")
        print(f"   发现博主: {len(result.discovery_queries)} 条")
        for q in result.discovery_queries:
            print(f"      - {q}")
        print(f"   搜索内容: {len(result.content_queries)} 条")
        for q in result.content_queries:
            print(f"      - {q}")
        print(f"   设计理由: {result.reasoning}")

        return {
            "discovery_queries": result.discovery_queries,
            "content_queries": result.content_queries,
            "logs": state.logs + [f"【搜索词】设计完成: 发现 {len(result.discovery_queries)} + 内容 {len(result.content_queries)}"]
        }

    except Exception as e:
        print(f"❌ 搜索词设计失败: {e}")
        # 兜底策略：使用通用搜索词
        fallback_discovery = [
            f"best {target_str} YouTube channels {current_year}",
            f"顶级{target_str}博主推荐"
        ]
        fallback_content = [
            f"{target_str} {current_month}",
            f"latest {target_str} {current_year}"
        ]

        return {
            "discovery_queries": fallback_discovery,
            "content_queries": fallback_content,
            "logs": state.logs + [f"【搜索词】使用兜底策略: {e}"]
        }

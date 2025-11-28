from datetime import datetime
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from core.llm import ModelGateway
from core.state import RadarState
from tools.web_search import FirecrawlScout

# Define Schema for Discovery Plan
class DiscoveryPlan(BaseModel):
    platform_queries: Dict[str, str] = Field(description="Search queries for each platform (youtube, douyin, reddit)")
    search_keywords: List[str] = Field(description="List of 3-5 core sub-niche keywords")

# Define Schema for Extraction
class ExtractedSources(BaseModel):
    youtube_urls: List[str] = Field(default_factory=list)
    douyin_urls: List[str] = Field(default_factory=list)
    reddit_urls: List[str] = Field(default_factory=list)

def run_discovery(state: RadarState) -> Dict[str, Any]:
    """
    节点 1: 全网侦察 (Discovery) - Structured Output Version
    """
    print("\n--- 节点: 全网侦察 (Node 1: Discovery) ---")
    
    llm = ModelGateway()
    firecrawl = FirecrawlScout()
    
    domains = state.target_domains
    now = datetime.now()
    current_year = now.year
    
    user_prompt = f"""
    背景: 我需要建立一个高质量的 "{domains}" 领域情报监控库。
    时间: {current_year} 年
    
    任务: 
    1. 为 YouTube, Douyin, Reddit 分别生成一个"找人/找榜单"的搜索查询。
    2. 拆解 3-5 个热点子赛道关键词。
    """
    
    try:
        print(f"🧠 正在策划全平台侦察方案...")
        
        plan: DiscoveryPlan = llm.call_with_schema(
            user_prompt=user_prompt,
            system_prompt="你是一个情报分析师。",
            schema_model=DiscoveryPlan,
            capability="reasoning"
        )
        
        print(f"🔑 侦察指令: {plan.platform_queries}")
        print(f"🔑 核心关键词: {plan.search_keywords}")
        
        for key in ["youtube", "douyin", "reddit"]:
            state.monitoring_list.setdefault(key, [])
            
        found_yt, found_dy, found_rd = [], [], []
        
        if firecrawl.api_key:
            # Execute searches
            for platform, query in plan.platform_queries.items():
                if not query: continue
                print(f"🕵️  搜索 {platform}: '{query}'")
                try:
                    # Use the fixed search method (no params dict)
                    results = firecrawl.search_and_scrape(query, limit=1)
                    if results:
                        extracted = _extract_sources(llm, str(results), platform)
                        if platform == 'youtube': found_yt.extend(extracted.youtube_urls)
                        if platform == 'douyin': found_dy.extend(extracted.douyin_urls)
                        if platform == 'reddit': found_rd.extend(extracted.reddit_urls)
                except Exception as e:
                    print(f"  ⚠️ {platform} 搜索失败: {e}")

            # Deduplicate and Merge
            new_yt = [u for u in found_yt if "youtube.com/" in u and u not in state.monitoring_list["youtube"]]
            state.monitoring_list["youtube"].extend(new_yt)
            
            new_dy = [u for u in found_dy if "douyin.com/" in u and u not in state.monitoring_list["douyin"]]
            state.monitoring_list["douyin"].extend(new_dy)
            
            new_rd = [u for u in found_rd if "reddit.com/r/" in u and u not in state.monitoring_list["reddit"]]
            state.monitoring_list["reddit"].extend(new_rd)
            
            print(f"✅ 侦察战果: YT +{len(new_yt)}, DY +{len(new_dy)}, Reddit +{len(new_rd)}")
        
        return {
            "keywords": plan.search_keywords,
            "monitoring_list": state.monitoring_list,
            "logs": state.logs + [f"Discovery: YT+{len(found_yt)} DY+{len(found_dy)} RD+{len(found_rd)}"]
        }
        
    except Exception as e:
        print(f"❌ 侦察阶段出错: {e}")
        return {"logs": state.logs + [f"Discovery failed: {e}"]}

def _extract_sources(llm: ModelGateway, text_content: str, platform_hint: str) -> ExtractedSources:
    """辅助函数：调用 LLM 提取链接 (Structured)"""
    prompt = f"""
    Context: Scraped search results for {platform_hint}.
    Goal: Extract valid profile URLs.
    Text: {text_content[:10000]}
    """
    try:
        return llm.call_with_schema(
            user_prompt=prompt,
            system_prompt="数据清洗专家。",
            schema_model=ExtractedSources,
            capability="fast"
        )
    except:
        return ExtractedSources()

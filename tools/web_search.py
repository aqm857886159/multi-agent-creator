import os
from typing import List, Dict, Any

# 尝试导入 Tavily，如果失败则提供 Mock 或回退
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

# 尝试导入 Firecrawl
try:
    from firecrawl import FirecrawlApp
except ImportError:
    FirecrawlApp = None

# 尝试导入 DuckDuckGo (作为免费兜底)
try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

class SearchGateway:
    """
    Unified Search Gateway
    Priority: Tavily -> Firecrawl -> DuckDuckGo
    """
    def __init__(self):
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        self.firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
        
        self.tavily_client = TavilyClient(api_key=self.tavily_key) if (self.tavily_key and TavilyClient) else None
        self.firecrawl_app = FirecrawlApp(api_key=self.firecrawl_key) if (self.firecrawl_key and FirecrawlApp) else None

    def search(self, query: str, limit: int = 5, depth: str = "advanced", include_raw_content: bool = False) -> List[Dict[str, Any]]:
        """
        执行搜索，自动降级策略

        Args:
            query: 搜索关键词
            limit: 返回结果数量
            depth: 搜索深度 (basic/advanced)
            include_raw_content: 是否包含完整网页内容（用于深度分析）
        """
        results = []

        # 1. 尝试 Tavily (最佳效果)
        if self.tavily_client:
            try:
                # print(f"🔍 [Search] Using Tavily: {query}")
                resp = self.tavily_client.search(
                    query=query,
                    search_depth=depth,
                    max_results=limit,
                    include_raw_content=include_raw_content  # 🔑 支持原始内容提取
                )
                # 统一格式
                for r in resp.get('results', []):
                    result_item = {
                        "title": r.get('title'),
                        "url": r.get('url'),
                        "content": r.get('content'),
                        "source": "tavily"
                    }
                    # 🔑 如果请求了原始内容，添加到结果中
                    if include_raw_content and 'raw_content' in r:
                        result_item['raw_content'] = r.get('raw_content')

                    results.append(result_item)
                return results
            except Exception as e:
                print(f"⚠️ Tavily Search Failed: {e}")

        # 2. 尝试 Firecrawl (备选)
        if self.firecrawl_app:
            try:
                # print(f"🔍 [Search] Using Firecrawl: {query}")
                # Firecrawl 的 search 接口参数
                resp = self.firecrawl_app.search(query, limit=limit)
                # 假设返回结构是 list
                if isinstance(resp, list):
                    for r in resp:
                        results.append({
                            "title": r.get('title'),
                            "url": r.get('url'),
                            "content": r.get('description') or r.get('metadata', {}).get('description'),
                            "source": "firecrawl"
                        })
                return results
            except Exception as e:
                 print(f"⚠️ Firecrawl Search Failed: {e}")

        # 3. 尝试 DuckDuckGo (免费兜底)
        if DDGS:
            try:
                # print(f"🔍 [Search] Using DuckDuckGo (Fallback): {query}")
                with DDGS() as ddgs:
                    ddg_gen = ddgs.text(query, max_results=limit)
                    for r in ddg_gen:
                        results.append({
                            "title": r.get('title'),
                            "url": r.get('href'),
                            "content": r.get('body'),
                            "source": "duckduckgo"
                        })
                return results
            except Exception as e:
                print(f"⚠️ DuckDuckGo Search Failed: {e}")

        print("❌ All search providers failed.")
        return []

    def scrape(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        网页抓取
        """
        scraped_data = []
        
        # 优先使用 Firecrawl (擅长抓取 Markdown)
        if self.firecrawl_app:
            for url in urls:
                try:
                    # scrape_url 返回结构
                    res = self.firecrawl_app.scrape_url(url, params={'formats': ['markdown']})
                    if res:
                        scraped_data.append({
                            "url": url,
                            "content": res.get('markdown', ''),
                            "metadata": res.get('metadata', {})
                        })
                except Exception as e:
                    print(f"⚠️ Firecrawl Scrape Error {url}: {e}")
        
        # 如果没有 Firecrawl，或者需要更多实现，可以用 Tavily 的 extract (如果支持) 
        # 或者简单的 requests + beautifulsoup (这里暂略)
        
        return scraped_data

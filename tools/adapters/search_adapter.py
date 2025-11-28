from typing import List, Optional
from pydantic import BaseModel, Field
from core.tool_registry import ToolResult
from tools.web_search import SearchGateway

# --- Input Schemas ---
class SearchInput(BaseModel):
    query: str = Field(..., description="The search query to execute")
    limit: int = Field(default=5, description="Max number of results to return")
    depth: str = Field(default="advanced", description="Search depth: 'basic' or 'advanced'")

class ScrapeInput(BaseModel):
    urls: List[str] = Field(..., description="List of URLs to scrape content from")

# --- Adapter Implementation ---
class SearchAdapter:
    def __init__(self):
        self.gateway = SearchGateway()

    def search_tool(self, params: SearchInput) -> ToolResult:
        try:
            results = self.gateway.search(params.query, params.limit, params.depth)
            summary = f"Found {len(results)} results for '{params.query}'"
            return ToolResult(
                status="success",
                data=results,
                summary=summary
            )
        except Exception as e:
            return ToolResult(status="error", error=str(e), summary="Search failed")

    def scrape_tool(self, params: ScrapeInput) -> ToolResult:
        try:
            results = self.gateway.scrape(params.urls)
            summary = f"Scraped {len(results)} pages"
            return ToolResult(
                status="success",
                data=results,
                summary=summary
            )
        except Exception as e:
            return ToolResult(status="error", error=str(e), summary="Scrape failed")


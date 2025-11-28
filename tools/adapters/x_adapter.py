from typing import List, Optional
from pydantic import BaseModel, Field
from core.tool_registry import ToolResult
from tools.x_scout import XScout

class XSearchInput(BaseModel):
    keyword: str = Field(..., description="Keyword to search for on X (Twitter)")
    limit: int = Field(default=5, description="Number of tweets to find")

class XMonitorInput(BaseModel):
    username: str = Field(..., description="X (Twitter) username (handle) to monitor, e.g. 'elonmusk'")
    limit: int = Field(default=5, description="Number of tweets to fetch")

class XAdapter:
    def __init__(self):
        self.scout = XScout()

    def search_x(self, params: XSearchInput) -> ToolResult:
        try:
            items = self.scout.search(params.keyword, params.limit)
            summary = f"Found {len(items)} tweets for '{params.keyword}'"
            return ToolResult(status="success", data=items, summary=summary)
        except Exception as e:
            return ToolResult(status="error", error=str(e), summary="X search failed")

    def monitor_x(self, params: XMonitorInput) -> ToolResult:
        try:
            items = self.scout.get_user_tweets(params.username, params.limit)
            summary = f"Retrieved {len(items)} tweets from @{params.username}"
            return ToolResult(status="success", data=items, summary=summary)
        except Exception as e:
            return ToolResult(status="error", error=str(e), summary="X monitor failed")


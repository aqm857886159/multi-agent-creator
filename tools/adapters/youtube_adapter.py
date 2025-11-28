from typing import List, Optional
from pydantic import BaseModel, Field
from core.tool_registry import ToolResult
from tools.youtube_scout import YoutubeScout

# --- Input Schemas ---
class YoutubeSearchInput(BaseModel):
    keyword: str = Field(..., description="Keyword to search for on YouTube")
    limit: int = Field(default=5, description="Number of videos to find")
    days: int = Field(default=7, description="Only keep videos within N days")
    sort_by: str = Field(default="relevance", description="Sorting mode: relevance or date")
    scan_limit: int = Field(default=0, description="Fast scan limit (0 = auto-calculate as limit*3)")

class YoutubeChannelInput(BaseModel):
    channel_url: str = Field(..., description="URL of the YouTube channel to monitor")
    days: int = Field(default=7, description="Time window in days")

# --- Adapter Implementation ---
class YoutubeAdapter:
    def __init__(self):
        self.scout = YoutubeScout()

    def search_videos(self, params: YoutubeSearchInput) -> ToolResult:
        try:
            # YoutubeScout.search_videos returns List[Dict]
            items = self.scout.search_videos(
                params.keyword,
                limit=params.limit,
                days=params.days,
                sort_by=params.sort_by,
                scan_limit=params.scan_limit  # 🔑 传递scan_limit参数
            )
            summary = f"Found {len(items)} videos for '{params.keyword}'"
            
            if not items:
                return ToolResult(status="failed", summary="No videos found", data=[])

            return ToolResult(
                status="success", 
                data=items, 
                summary=summary
            )
        except Exception as e:
            return ToolResult(status="error", error=str(e), summary="YouTube search failed")

    def get_channel_videos(self, params: YoutubeChannelInput) -> ToolResult:
        try:
            items = self.scout.get_channel_videos(params.channel_url, params.days)
            summary = f"Retrieved {len(items)} recent videos from channel"
            return ToolResult(status="success", data=items, summary=summary)
        except Exception as e:
            return ToolResult(status="error", error=str(e), summary="Channel monitor failed")


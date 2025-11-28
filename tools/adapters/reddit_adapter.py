from typing import List, Optional
from pydantic import BaseModel, Field
from core.tool_registry import ToolResult
from tools.reddit_scout import RedditScout


class RedditSearchInput(BaseModel):
    keyword: str = Field(..., description="搜索关键词")
    limit: int = Field(default=10, description="返回结果数量")
    days: int = Field(default=7, description="时间范围（天）")
    subreddit: str = Field(default="all", description="子版块名称，默认 all（全站搜索）")
    sort: str = Field(default="hot", description="排序方式: hot/new/top/relevance")


class RedditMonitorInput(BaseModel):
    subreddit: str = Field(..., description="要监控的子版块名称（如 MachineLearning）")
    limit: int = Field(default=10, description="返回结果数量")
    sort: str = Field(default="hot", description="排序方式: hot/new/top/rising")


class RedditAdapter:
    def __init__(self):
        self.scout = RedditScout()

    def search_reddit(self, params: RedditSearchInput) -> ToolResult:
        """搜索 Reddit 帖子"""
        try:
            items = self.scout.search_posts(
                keyword=params.keyword,
                limit=params.limit,
                days=params.days,
                subreddit=params.subreddit,
                sort=params.sort
            )

            if not items:
                return ToolResult(
                    status="failed",
                    summary=f"未找到关于 '{params.keyword}' 的帖子",
                    data=[]
                )

            summary = f"在 r/{params.subreddit} 找到 {len(items)} 条关于 '{params.keyword}' 的帖子"

            return ToolResult(
                status="success",
                data=items,
                summary=summary
            )

        except Exception as e:
            return ToolResult(
                status="error",
                error=str(e),
                summary="Reddit 搜索失败"
            )

    def monitor_reddit(self, params: RedditMonitorInput) -> ToolResult:
        """监控 Reddit 子版块"""
        try:
            items = self.scout.monitor_subreddit(
                subreddit=params.subreddit,
                limit=params.limit,
                sort=params.sort
            )

            if not items:
                return ToolResult(
                    status="failed",
                    summary=f"未能获取 r/{params.subreddit} 的帖子",
                    data=[]
                )

            summary = f"从 r/{params.subreddit} 获取 {len(items)} 条帖子"

            return ToolResult(
                status="success",
                data=items,
                summary=summary
            )

        except Exception as e:
            return ToolResult(
                status="error",
                error=str(e),
                summary="Reddit 监控失败"
            )

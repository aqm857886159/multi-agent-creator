"""
反馈分析器 - 分析工具执行结果并提供智能建议

核心功能：
1. 记录工具执行结果
2. 分析失败模式
3. 生成重试建议（调整参数）
4. 学习历史经验

使用方式：
    from core.feedback_analyzer import analyze_result, get_retry_suggestion
    
    # 分析执行结果
    analysis = analyze_result(tool_name, params, result, state)
    
    # 获取重试建议
    suggestion = get_retry_suggestion(tool_name, error, state)
"""

from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict
from datetime import datetime
from core.prompt_manager import get_prompt_manager


class FeedbackAnalyzer:
    """反馈分析器"""
    
    # 常见错误模式及建议
    ERROR_PATTERNS = {
        # 超时相关
        "timeout": {
            "keywords": ["timeout", "timed out", "超时", "TimeoutError"],
            "suggestion": "减少 limit 参数或增加 timeout",
            "param_adjustments": {
                "limit": lambda x: max(5, x - 5),
                "timeout": lambda x: x + 10 if x else 30
            }
        },
        # 无结果
        "no_results": {
            "keywords": ["no results", "empty", "0 条", "未找到", "没有找到"],
            "suggestion": "放宽搜索条件或更换关键词",
            "param_adjustments": {
                "days": lambda x: min(180, (x or 30) + 30),
                "limit": lambda x: max(5, (x or 10) + 5)
            }
        },
        # 限流
        "rate_limit": {
            "keywords": ["rate limit", "too many requests", "429", "限流"],
            "suggestion": "增加请求间隔",
            "param_adjustments": {
                "delay": lambda x: (x or 1) + 2
            }
        },
        # 认证错误
        "auth_error": {
            "keywords": ["401", "403", "unauthorized", "forbidden", "认证"],
            "suggestion": "检查 API 密钥或登录状态",
            "param_adjustments": {}
        },
        # 网络错误
        "network_error": {
            "keywords": ["connection", "network", "dns", "网络"],
            "suggestion": "检查网络连接，稍后重试",
            "param_adjustments": {}
        },
        # 参数错误
        "param_error": {
            "keywords": ["invalid", "parameter", "参数", "格式错误"],
            "suggestion": "检查参数格式",
            "param_adjustments": {}
        }
    }
    
    # 平台特定建议
    PLATFORM_SUGGESTIONS = {
        "youtube_search": {
            "low_results": "尝试使用更通用的英文关键词，避免专有名词",
            "irrelevant": "确保关键词为纯英文，避免混合语言"
        },
        "bilibili_search": {
            "low_results": "尝试使用 B站黑话（保姆级、干货、避坑指南）",
            "irrelevant": "确保关键词为纯中文，添加'原创'过滤搬运"
        },
        "youtube_monitor": {
            "low_results": "确认频道 URL 格式正确（@handle 或完整 URL）",
            "irrelevant": "频道可能不活跃，尝试其他博主"
        },
        "bilibili_monitor": {
            "low_results": "确认 UP主 ID 正确",
            "irrelevant": "UP主可能不活跃，尝试其他博主"
        }
    }
    
    def __init__(self):
        # 历史记录（用于模式学习）
        self._history: List[Dict[str, Any]] = []
        self._success_patterns: Dict[str, List[Dict]] = defaultdict(list)
        self._failure_patterns: Dict[str, List[Dict]] = defaultdict(list)
    
    def analyze_result(
        self, 
        tool_name: str, 
        params: Dict[str, Any], 
        result: Any, 
        state: Any = None
    ) -> Dict[str, Any]:
        """
        分析工具执行结果
        
        Args:
            tool_name: 工具名称
            params: 调用参数
            result: 执行结果
            state: RadarState 实例
        
        Returns:
            分析结果字典
        """
        analysis = {
            "tool_name": tool_name,
            "params": params,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "issues": [],
            "suggestions": [],
            "retry_recommended": False,
            "adjusted_params": None
        }
        
        # 判断成功/失败
        if hasattr(result, 'status'):
            analysis["success"] = result.status == "success"
        elif isinstance(result, dict):
            analysis["success"] = result.get("status") == "success"
        
        # 获取结果数量
        result_count = self._get_result_count(result)
        analysis["result_count"] = result_count
        
        # 分析问题
        if not analysis["success"]:
            # 失败分析
            error_msg = self._get_error_message(result)
            error_type = self._classify_error(error_msg)
            
            analysis["error_type"] = error_type
            analysis["error_message"] = error_msg
            analysis["issues"].append(f"执行失败: {error_type}")
            
            # 获取建议
            suggestion = self._get_error_suggestion(error_type, tool_name)
            if suggestion:
                analysis["suggestions"].append(suggestion)
            
            # 计算调整后的参数
            adjusted = self._calculate_adjusted_params(error_type, params)
            if adjusted:
                analysis["adjusted_params"] = adjusted
                analysis["retry_recommended"] = True
            
            # 记录失败模式
            self._failure_patterns[tool_name].append({
                "params": params,
                "error_type": error_type,
                "timestamp": analysis["timestamp"]
            })
        
        else:
            # 成功但结果不佳
            if result_count == 0:
                analysis["issues"].append("搜索成功但无结果")
                analysis["suggestions"].append(
                    self.PLATFORM_SUGGESTIONS.get(tool_name, {}).get("low_results", "尝试放宽搜索条件")
                )
                analysis["retry_recommended"] = True
                analysis["adjusted_params"] = self._calculate_adjusted_params("no_results", params)
            
            elif result_count < 5:
                analysis["issues"].append(f"结果数量较少 ({result_count} 条)")
                analysis["suggestions"].append("考虑扩大搜索范围")
            
            # 记录成功模式
            self._success_patterns[tool_name].append({
                "params": params,
                "result_count": result_count,
                "timestamp": analysis["timestamp"]
            })
        
        # 记录到历史
        self._history.append(analysis)
        
        return analysis
    
    def get_retry_suggestion(
        self, 
        tool_name: str, 
        error: str, 
        original_params: Dict[str, Any],
        state: Any = None
    ) -> Dict[str, Any]:
        """
        获取重试建议
        
        Args:
            tool_name: 工具名称
            error: 错误信息
            original_params: 原始参数
            state: RadarState 实例
        
        Returns:
            重试建议字典
        """
        error_type = self._classify_error(error)
        
        suggestion = {
            "should_retry": False,
            "reason": "",
            "adjusted_params": None,
            "alternative_tool": None,
            "wait_seconds": 0
        }
        
        # 检查是否已经重试过多次
        recent_failures = self._get_recent_failures(tool_name, minutes=5)
        if len(recent_failures) >= 3:
            suggestion["reason"] = f"{tool_name} 最近失败 {len(recent_failures)} 次，建议暂时跳过"
            suggestion["alternative_tool"] = self._get_alternative_tool(tool_name)
            return suggestion
        
        # 根据错误类型决定是否重试
        if error_type in ["timeout", "network_error"]:
            suggestion["should_retry"] = True
            suggestion["reason"] = "网络问题，建议重试"
            suggestion["wait_seconds"] = 5
            suggestion["adjusted_params"] = self._calculate_adjusted_params(error_type, original_params)
        
        elif error_type == "rate_limit":
            suggestion["should_retry"] = True
            suggestion["reason"] = "限流，等待后重试"
            suggestion["wait_seconds"] = 30
        
        elif error_type == "no_results":
            suggestion["should_retry"] = True
            suggestion["reason"] = "无结果，调整参数后重试"
            suggestion["adjusted_params"] = self._calculate_adjusted_params(error_type, original_params)
        
        elif error_type in ["auth_error", "param_error"]:
            suggestion["should_retry"] = False
            suggestion["reason"] = f"{error_type} 需要人工干预"
        
        else:
            suggestion["should_retry"] = True
            suggestion["reason"] = "未知错误，尝试重试"
            suggestion["wait_seconds"] = 2
        
        return suggestion
    
    def get_success_params(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取历史成功的参数模式
        
        Args:
            tool_name: 工具名称
        
        Returns:
            成功的参数模式（如果有）
        """
        patterns = self._success_patterns.get(tool_name, [])
        if not patterns:
            return None
        
        # 返回结果最多的参数组合
        best = max(patterns, key=lambda x: x.get("result_count", 0))
        return best.get("params")
    
    def get_failure_summary(self, tool_name: str = None) -> str:
        """
        获取失败摘要
        
        Args:
            tool_name: 可选的工具名称过滤
        
        Returns:
            失败摘要文本
        """
        if tool_name:
            failures = self._failure_patterns.get(tool_name, [])
        else:
            failures = []
            for patterns in self._failure_patterns.values():
                failures.extend(patterns)
        
        if not failures:
            return "无失败记录"
        
        # 聚合错误类型
        error_counts = defaultdict(int)
        for f in failures:
            error_counts[f.get("error_type", "unknown")] += 1
        
        lines = [f"失败统计 (共 {len(failures)} 次):"]
        for error_type, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {error_type}: {count} 次")
        
        return "\n".join(lines)
    
    def _classify_error(self, error_msg: str) -> str:
        """分类错误类型"""
        if not error_msg:
            return "unknown"
        
        error_lower = error_msg.lower()
        
        for error_type, pattern in self.ERROR_PATTERNS.items():
            for keyword in pattern["keywords"]:
                if keyword.lower() in error_lower:
                    return error_type
        
        return "unknown"
    
    def _get_error_message(self, result: Any) -> str:
        """从结果中提取错误信息"""
        if hasattr(result, 'error'):
            return str(result.error)
        if isinstance(result, dict):
            return str(result.get("error", ""))
        if isinstance(result, Exception):
            return str(result)
        return ""
    
    def _get_result_count(self, result: Any) -> int:
        """获取结果数量"""
        if hasattr(result, 'data') and isinstance(result.data, list):
            return len(result.data)
        if isinstance(result, dict):
            data = result.get("data", [])
            if isinstance(data, list):
                return len(data)
        return 0
    
    def _get_error_suggestion(self, error_type: str, tool_name: str) -> str:
        """获取错误建议"""
        # 先检查错误模式
        pattern = self.ERROR_PATTERNS.get(error_type, {})
        base_suggestion = pattern.get("suggestion", "")
        
        # 再检查平台特定建议
        platform_suggestion = self.PLATFORM_SUGGESTIONS.get(tool_name, {}).get("low_results", "")
        
        if base_suggestion and platform_suggestion:
            return f"{base_suggestion}。{platform_suggestion}"
        return base_suggestion or platform_suggestion or "检查参数和网络"
    
    def _calculate_adjusted_params(
        self, 
        error_type: str, 
        original_params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """计算调整后的参数"""
        pattern = self.ERROR_PATTERNS.get(error_type, {})
        adjustments = pattern.get("param_adjustments", {})
        
        if not adjustments:
            return None
        
        adjusted = dict(original_params)
        
        for param, adjuster in adjustments.items():
            if param in adjusted:
                adjusted[param] = adjuster(adjusted[param])
            elif callable(adjuster):
                # 参数不存在时使用默认值
                adjusted[param] = adjuster(None)
        
        return adjusted
    
    def _get_recent_failures(self, tool_name: str, minutes: int = 5) -> List[Dict]:
        """获取最近的失败记录"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        failures = self._failure_patterns.get(tool_name, [])
        recent = []
        
        for f in failures:
            try:
                ts = datetime.fromisoformat(f.get("timestamp", ""))
                if ts > cutoff:
                    recent.append(f)
            except ValueError:
                pass
        
        return recent
    
    def _get_alternative_tool(self, tool_name: str) -> Optional[str]:
        """获取替代工具"""
        alternatives = {
            "youtube_search": "bilibili_search",
            "bilibili_search": "youtube_search",
            "youtube_monitor": "youtube_search",
            "bilibili_monitor": "bilibili_search",
            "web_search": None,
            "web_scrape": "web_search"
        }
        return alternatives.get(tool_name)


# ============ 全局单例 ============

_analyzer: Optional[FeedbackAnalyzer] = None

def get_analyzer() -> FeedbackAnalyzer:
    """获取分析器单例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = FeedbackAnalyzer()
    return _analyzer


# ============ 便捷函数 ============

def analyze_result(
    tool_name: str, 
    params: Dict[str, Any], 
    result: Any, 
    state: Any = None
) -> Dict[str, Any]:
    """分析工具执行结果"""
    return get_analyzer().analyze_result(tool_name, params, result, state)

def get_retry_suggestion(
    tool_name: str, 
    error: str, 
    original_params: Dict[str, Any],
    state: Any = None
) -> Dict[str, Any]:
    """获取重试建议"""
    return get_analyzer().get_retry_suggestion(tool_name, error, original_params, state)

def get_success_params(tool_name: str) -> Optional[Dict[str, Any]]:
    """获取历史成功的参数"""
    return get_analyzer().get_success_params(tool_name)

def get_failure_summary(tool_name: str = None) -> str:
    """获取失败摘要"""
    return get_analyzer().get_failure_summary(tool_name)


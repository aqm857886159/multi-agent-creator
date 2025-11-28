"""
🔑 完整重试链条机制
基于业界最佳实践（Manus/OpenAI/Claude）

核心特性:
1. 分层降级策略 (Layer 1 → Layer 2 → Layer 3)
2. 熔断器保护 (Circuit Breaker)
3. 错误上下文保留 (Manus原则: Leave wrong turns in context)
4. 指数退避 + 抖动 (Exponential Backoff + Jitter)
"""

import time
import random
from typing import List, Dict, Any, Callable, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.layered_keyword_strategy import generate_fallback_keywords
from core.search_validator import validate_search_results


@dataclass
class CircuitBreaker:
    """
    熔断器 - 防止级联失败

    状态:
    - CLOSED: 正常工作
    - OPEN: 熔断打开（拒绝所有请求）
    - HALF_OPEN: 半开（允许少量探测请求）
    """
    failure_threshold: int = 3  # 连续失败3次后熔断
    reset_timeout: int = 60  # 60秒后尝试恢复

    failure_count: int = field(default=0, init=False)
    last_failure_time: Optional[datetime] = field(default=None, init=False)
    state: str = field(default="CLOSED", init=False)  # CLOSED | OPEN | HALF_OPEN

    def is_open(self) -> bool:
        """检查熔断器是否打开"""
        if self.state == "OPEN":
            # 检查是否到了重置时间
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).seconds >= self.reset_timeout:
                self.state = "HALF_OPEN"
                return False
            return True
        return False

    def record_success(self):
        """记录成功 - 重置计数"""
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        """记录失败 - 增加计数，可能触发熔断"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            print(f"""
╔══════════════════════════════════════════════════════════════╗
║  🔴 熔断器已打开 - 检测到连续{self.failure_count}次失败           ║
╚══════════════════════════════════════════════════════════════╝
将在 {self.reset_timeout} 秒后尝试恢复...
""")


@dataclass
class RetryAttempt:
    """单次重试记录"""
    attempt_number: int
    query: str
    layer: str  # "layer1_precise" | "layer2_functional" | "layer3_generic"
    success: bool
    relevance_score: float
    result_count: int
    validation_info: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class RetryChain:
    """
    完整重试链条

    流程:
    1. 尝试原始查询
    2. 验证结果质量
    3. 如果失败，生成降级查询（Layer 1 → 2 → 3）
    4. 依次重试降级查询
    5. 保留所有错误上下文（Manus原则）
    6. 熔断器保护
    """

    def __init__(
        self,
        max_retries: int = 5,
        relevance_threshold: float = 0.30,
        enable_backoff: bool = True,
        backoff_factor: float = 1.8,  # OpenAI推荐
        max_backoff: float = 16.0
    ):
        self.max_retries = max_retries
        self.relevance_threshold = relevance_threshold
        self.enable_backoff = enable_backoff
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff

        self.circuit_breaker = CircuitBreaker()
        self.retry_history: List[RetryAttempt] = []

    def execute_with_retry(
        self,
        original_query: str,
        search_func: Callable[[str], List[Dict[str, Any]]],
        platform: str = "youtube",
        preserve_context: bool = True
    ) -> Dict[str, Any]:
        """
        执行带重试的搜索

        参数:
            original_query: 原始查询
            search_func: 搜索函数 (query: str) -> results: List[Dict]
            platform: 平台 (youtube | bilibili)
            preserve_context: 是否保留错误上下文 (Manus原则)

        返回:
            {
                "success": bool,
                "results": List[Dict],
                "final_query": str,
                "attempts": int,
                "retry_history": List[RetryAttempt],  # 如果preserve_context=True
                "circuit_breaker_triggered": bool
            }
        """
        # 清空历史
        self.retry_history = []

        # 检查熔断器
        if self.circuit_breaker.is_open():
            return self._create_failure_response(
                "熔断器已打开，拒绝请求",
                circuit_breaker_triggered=True
            )

        # 生成分层降级查询
        fallback_layers = generate_fallback_keywords(original_query, platform)

        # 构建查询序列: 原始查询 + Layer1 + Layer2 + Layer3
        query_sequence = self._build_query_sequence(
            original_query,
            fallback_layers
        )

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║  🔄 重试链条已启动                                             ║
╚══════════════════════════════════════════════════════════════╝
📝 原始查询: {original_query}
📊 查询序列: {len(query_sequence)} 个备选查询
🎯 质量阈值: {self.relevance_threshold:.0%}
""")

        # 依次尝试查询
        for attempt_idx, (query, layer) in enumerate(query_sequence):
            if attempt_idx >= self.max_retries:
                print(f"⚠️  达到最大重试次数 ({self.max_retries})，停止重试")
                break

            # 指数退避 + 抖动
            if attempt_idx > 0 and self.enable_backoff:
                delay = self._calculate_backoff_delay(attempt_idx)
                print(f"⏱️  等待 {delay:.2f}s 后重试...")
                time.sleep(delay)

            # 执行搜索
            print(f"\n🔍 尝试 {attempt_idx + 1}/{self.max_retries}: {query} ({layer})")

            try:
                results = search_func(query)

                # 验证结果质量
                validation = validate_search_results(query, results)

                # 记录重试
                retry_record = RetryAttempt(
                    attempt_number=attempt_idx + 1,
                    query=query,
                    layer=layer,
                    success=validation["is_valid"],
                    relevance_score=validation["relevance_score"],
                    result_count=len(results),
                    validation_info=validation
                )
                self.retry_history.append(retry_record)

                # 打印验证结果
                self._print_validation_result(validation, attempt_idx + 1)

                # 检查是否成功
                if validation["is_valid"]:
                    # 成功！
                    self.circuit_breaker.record_success()
                    return self._create_success_response(
                        results=results,
                        final_query=query,
                        attempts=attempt_idx + 1,
                        preserve_context=preserve_context
                    )

                # 失败，继续下一次尝试
                print(f"❌ 查询失败: {', '.join(validation.get('issues', []))}")

            except Exception as e:
                print(f"⚠️  搜索异常: {e}")
                # 记录失败
                retry_record = RetryAttempt(
                    attempt_number=attempt_idx + 1,
                    query=query,
                    layer=layer,
                    success=False,
                    relevance_score=0.0,
                    result_count=0,
                    validation_info={"error": str(e)}
                )
                self.retry_history.append(retry_record)
                continue

        # 所有尝试都失败
        self.circuit_breaker.record_failure()
        return self._create_failure_response(
            f"所有查询尝试均失败 ({len(self.retry_history)} 次尝试)",
            preserve_context=preserve_context
        )

    def _build_query_sequence(
        self,
        original_query: str,
        fallback_layers: Dict[str, List[str]]
    ) -> List[Tuple[str, str]]:
        """
        构建查询序列

        返回: [(query, layer_name), ...]
        """
        sequence = [
            (original_query, "original")
        ]

        # Layer 1: Precise (精准)
        for q in fallback_layers.get("layer1_precise", []):
            sequence.append((q, "layer1_precise"))

        # Layer 2: Functional (功能描述) - 只取前2个
        for q in fallback_layers.get("layer2_functional", [])[:2]:
            sequence.append((q, "layer2_functional"))

        # Layer 3: Generic (泛化) - 只取第1个
        for q in fallback_layers.get("layer3_generic", [])[:1]:
            sequence.append((q, "layer3_generic"))

        return sequence

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        计算指数退避延迟 + 抖动

        公式: min(max_backoff, backoff_factor ^ attempt) + random_jitter
        """
        base_delay = min(self.max_backoff, self.backoff_factor ** attempt)
        jitter = random.uniform(0, base_delay * 0.1)  # 10% jitter
        return base_delay + jitter

    def _print_validation_result(self, validation: Dict, attempt: int):
        """打印验证结果"""
        score = validation["relevance_score"]
        is_valid = validation["is_valid"]

        if is_valid:
            print(f"✅ 验证通过: 相关性 {score:.1%} (阈值: {self.relevance_threshold:.0%})")
        else:
            print(f"❌ 验证失败: 相关性 {score:.1%} (阈值: {self.relevance_threshold:.0%})")

    def _create_success_response(
        self,
        results: List[Dict],
        final_query: str,
        attempts: int,
        preserve_context: bool
    ) -> Dict[str, Any]:
        """创建成功响应"""
        response = {
            "success": True,
            "results": results,
            "final_query": final_query,
            "attempts": attempts,
            "circuit_breaker_triggered": False
        }

        if preserve_context:
            response["retry_history"] = self.retry_history

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ✅ 重试链条成功                                               ║
╚══════════════════════════════════════════════════════════════╝
🎯 最终查询: {final_query}
📊 尝试次数: {attempts}
📦 结果数量: {len(results)}
""")

        return response

    def _create_failure_response(
        self,
        reason: str,
        preserve_context: bool = True,
        circuit_breaker_triggered: bool = False
    ) -> Dict[str, Any]:
        """创建失败响应"""
        response = {
            "success": False,
            "results": [],
            "final_query": None,
            "attempts": len(self.retry_history),
            "reason": reason,
            "circuit_breaker_triggered": circuit_breaker_triggered
        }

        if preserve_context:
            response["retry_history"] = self.retry_history

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ❌ 重试链条失败                                               ║
╚══════════════════════════════════════════════════════════════╝
💬 原因: {reason}
📊 尝试次数: {len(self.retry_history)}
""")

        return response

    def get_retry_summary(self) -> Dict[str, Any]:
        """
        获取重试摘要（用于日志和调试）

        返回:
            {
                "total_attempts": int,
                "successful_attempts": int,
                "failed_attempts": int,
                "layers_used": List[str],
                "final_success": bool
            }
        """
        successful = [r for r in self.retry_history if r.success]
        failed = [r for r in self.retry_history if not r.success]
        layers = list(set(r.layer for r in self.retry_history))

        return {
            "total_attempts": len(self.retry_history),
            "successful_attempts": len(successful),
            "failed_attempts": len(failed),
            "layers_used": layers,
            "final_success": len(successful) > 0
        }


# 全局单例
_retry_chain = RetryChain()


def search_with_retry(
    query: str,
    search_func: Callable[[str], List[Dict[str, Any]]],
    platform: str = "youtube"
) -> Dict[str, Any]:
    """
    便捷函数：执行带重试的搜索

    示例:
        def my_search(q):
            return youtube_search(q)

        result = search_with_retry(
            query="Manus AI tutorial",
            search_func=my_search,
            platform="youtube"
        )

        if result["success"]:
            videos = result["results"]
        else:
            print(f"搜索失败: {result['reason']}")
            print(f"重试历史: {result['retry_history']}")
    """
    return _retry_chain.execute_with_retry(query, search_func, platform)


if __name__ == "__main__":
    # 测试用例: 模拟搜索函数
    def mock_youtube_search(query: str) -> List[Dict[str, Any]]:
        """模拟YouTube搜索"""
        print(f"  → 执行搜索: {query}")

        # 模拟不同查询的结果
        if "Manus AI" in query or "why Manus" in query:
            # 原始查询失败 - 返回不相关结果
            return [
                {"title": "AI tools overview", "views": 10000},
                {"title": "Best automation platforms", "views": 5000}
            ]
        elif query == "Manus" or '"Manus"' in query:
            # Layer 1成功 - 返回相关结果
            return [
                {"title": "Manus AI Complete Guide", "views": 50000},
                {"title": "Manus Tutorial for Beginners", "views": 30000},
                {"title": "How to use Manus", "views": 20000}
            ]
        else:
            # 其他降级查询
            return [
                {"title": f"Generic result for {query}", "views": 1000}
            ]

    print("=== 测试用例: Manus AI 搜索 ===\n")
    result = search_with_retry(
        query="why Manus AI succeeded 2025",
        search_func=mock_youtube_search,
        platform="youtube"
    )

    print("\n" + "="*60)
    print("最终结果:")
    print(f"成功: {result['success']}")
    print(f"查询: {result['final_query']}")
    print(f"结果数: {len(result['results'])}")
    print(f"尝试次数: {result['attempts']}")

    if result.get("retry_history"):
        print("\n重试历史:")
        for attempt in result["retry_history"]:
            status = "✅" if attempt.success else "❌"
            print(f"  {status} 尝试{attempt.attempt_number}: {attempt.query} "
                  f"({attempt.layer}) - {attempt.relevance_score:.1%}")

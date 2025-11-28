"""
自适应质量门系统 (Adaptive Quality Gate)

核心设计原则:
1. 通用性 - 适用于任何工具结果的质量检查
2. 智能性 - 使用LLM自主判断和决策
3. 护栏机制 - 防止死循环和成本失控
🔑 P1增强 - 集成搜索结果相关性验证
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from core.llm import get_llm_with_schema
from core.search_validator import validate_search_results  # 🔑 P1新增


class QualityCheckResult(BaseModel):
    """质量检查结果（通用结构）"""
    passed: bool = Field(..., description="是否通过质量检查（true=继续，false=需要调整）")
    confidence: float = Field(..., description="判断的置信度 0-1，越高越确定")
    score: float = Field(..., description="结果质量分数 0-1，0=完全不符合预期，1=完全符合")

    # 智能诊断
    issues: List[str] = Field(default_factory=list, description="发现的具体问题（让LLM自由描述）")
    root_cause: Optional[str] = Field(None, description="根本原因分析")

    # 智能建议
    suggested_action: str = Field(..., description="建议的行动: continue | retry | adjust_params | change_strategy | skip")
    adjustment_plan: Optional[Dict[str, Any]] = Field(None, description="具体的调整方案（参数修改、策略变更等）")
    reasoning: str = Field(..., description="为什么做出这个判断（可解释性）")


class FeedbackLoopGuard(BaseModel):
    """反馈循环护栏"""
    tool_name: str
    original_params: Dict[str, Any]
    retry_count: int = 0
    max_retries: int = 2  # 最多重试2次
    total_cost_estimate: float = 0.0  # 累计成本估算
    max_cost: float = 1.0  # 最大允许成本（美元）
    feedback_history: List[Dict[str, Any]] = Field(default_factory=list)

    def can_retry(self) -> bool:
        """检查是否可以继续重试"""
        if self.retry_count >= self.max_retries:
            return False
        if self.total_cost_estimate >= self.max_cost:
            return False
        return True

    def record_attempt(self, result: QualityCheckResult, cost: float = 0.0):
        """记录一次尝试"""
        self.retry_count += 1
        self.total_cost_estimate += cost
        self.feedback_history.append({
            "attempt": self.retry_count,
            "passed": result.passed,
            "score": result.score,
            "action": result.suggested_action,
            "issues": result.issues,
            "cost": cost
        })


class AdaptiveQualityGate:
    """
    自适应质量门

    核心特点:
    1. 通用性 - 不针对特定工具，通用质量检查框架
    2. 智能性 - LLM自主分析问题和给出方案
    3. 自适应 - 根据历史反馈调整判断标准
    """

    def __init__(self, use_fast_model: bool = True):
        """
        Args:
            use_fast_model: 是否使用快速模型（haiku）降低成本
        """
        self.use_fast_model = use_fast_model
        self.capability = "base" if use_fast_model else "reasoning"

    def check_quality(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        tool_result: Any,
        expectation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QualityCheckResult:
        """
        通用质量检查（智能判断）
        🔑 P1增强: 对搜索工具增加快速相关性预检查

        Args:
            tool_name: 工具名称（如 youtube_search, bilibili_search）
            tool_params: 工具调用参数
            tool_result: 工具返回结果（可以是任何类型）
            expectation: 期望的结果描述（自然语言）
            context: 额外上下文信息（可选）

        Returns:
            QualityCheckResult: LLM智能判断的质量检查结果
        """

        # 🔑 P1: 快速预检查 - 搜索工具的关键词相关性验证
        if tool_name in ['youtube_search', 'bilibili_search', 'web_search']:
            query = tool_params.get('query', '')
            if query and hasattr(tool_result, 'data') and isinstance(tool_result.data, list):
                # 运行快速相关性检查
                validation_result = validate_search_results(query, tool_result.data)

                if not validation_result['is_valid']:
                    # 相关性不足，直接返回失败（跳过LLM调用，节省成本）
                    return QualityCheckResult(
                        passed=False,
                        confidence=0.9,  # 规则检查置信度高
                        score=validation_result['relevance_score'],
                        issues=validation_result['issues'] + [
                            f"核心实体: {validation_result['core_entities']}",
                            f"仅匹配: {validation_result['matched_keywords']}"
                        ],
                        root_cause=f"搜索引擎将'{query}'降级为泛化词'{validation_result['core_entities']}'，忽略核心实体",
                        suggested_action="adjust_params",
                        adjustment_plan={
                            "original_query": query,
                            "fallback_queries": validation_result['suggestions'],
                            "action": "try_simpler_keyword"
                        },
                        reasoning=f"关键词相关性检查: {validation_result['relevance_score']:.1%} < 30%阈值，建议降级为更简洁的关键词"
                    )

        # 构建智能提示词
        system_prompt = """你是一个智能质量检查专家，负责评估工具执行结果的质量。

你的任务：
1. 判断结果是否符合预期
2. 诊断存在的问题（如果有）
3. 给出智能的改进建议

评判原则：
- 相关性：结果是否与预期主题相关
- 数量：是否获取到足够的数据
- 质量：数据是否有价值（非垃圾内容）
- 多样性：是否有重复或单一来源

行动建议类型：
- continue: 质量良好，继续下一步
- retry: 临时问题，重试相同参数
- adjust_params: 需要调整参数（如增加limit、修改关键词）
- change_strategy: 策略性问题，需要换个方向
- skip: 无法修复，跳过这个任务
"""

        # 准备结果摘要（避免token过多）
        result_summary = self._summarize_result(tool_result)

        # 准备上下文
        context_str = ""
        if context:
            context_str = f"\n\n补充上下文:\n{self._format_context(context)}"

        user_prompt = f"""
请评估以下工具执行结果的质量：

【工具】: {tool_name}
【参数】: {tool_params}
【预期】: {expectation}

【实际结果】:
{result_summary}
{context_str}

请分析：
1. 这个结果是否符合预期？为什么？
2. 存在什么问题（如果有）？
3. 建议采取什么行动？
4. 如果需要调整，具体应该怎么改？

请给出你的专业判断。
"""

        try:
            result: QualityCheckResult = get_llm_with_schema(
                user_prompt=user_prompt,
                response_model=QualityCheckResult,
                capability=self.capability,
                system_prompt=system_prompt
            )
            return result

        except Exception as e:
            # 兜底：检查失败时默认通过（保守策略）
            print(f"⚠️ 质量检查失败: {e}，默认通过")
            return QualityCheckResult(
                passed=True,
                confidence=0.5,
                score=0.7,
                issues=[f"质量检查失败: {e}"],
                suggested_action="continue",
                reasoning="质量检查系统异常，采用保守策略默认通过"
            )

    def _summarize_result(self, result: Any) -> str:
        """总结结果（避免token过多）"""
        if result is None:
            return "结果为空 (None)"

        if isinstance(result, dict):
            if "data" in result and isinstance(result["data"], list):
                items = result["data"]
                count = len(items)
                if count == 0:
                    return f"返回0条数据"

                # 显示前3条的标题
                sample_titles = []
                for item in items[:3]:
                    if isinstance(item, dict) and "title" in item:
                        sample_titles.append(item["title"])

                summary = f"返回{count}条数据\n前3条标题:\n"
                for i, title in enumerate(sample_titles, 1):
                    summary += f"  {i}. {title}\n"

                return summary
            else:
                return f"字典结果: {str(result)[:300]}..."

        if isinstance(result, list):
            count = len(result)
            if count == 0:
                return "返回空列表"

            # 尝试提取标题
            sample_titles = []
            for item in result[:3]:
                if isinstance(item, dict) and "title" in item:
                    sample_titles.append(item["title"])

            if sample_titles:
                summary = f"返回{count}条数据\n前3条标题:\n"
                for i, title in enumerate(sample_titles, 1):
                    summary += f"  {i}. {title}\n"
                return summary
            else:
                return f"返回{count}条数据（无法提取标题）"

        # 其他类型
        return f"{type(result).__name__}: {str(result)[:200]}..."

    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文信息"""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                lines.append(f"- {key}: {len(value)} 项")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)


class FeedbackLoopManager:
    """
    反馈循环管理器

    功能：
    1. 管理重试逻辑
    2. 防止死循环
    3. 成本控制
    4. 自动应用调整建议
    """

    def __init__(self, max_retries: int = 2, max_cost: float = 1.0):
        self.max_retries = max_retries
        self.max_cost = max_cost
        self.active_guards: Dict[str, FeedbackLoopGuard] = {}

    def create_guard(self, tool_name: str, params: Dict[str, Any]) -> FeedbackLoopGuard:
        """为任务创建护栏"""
        guard_id = f"{tool_name}_{hash(str(params))}"

        guard = FeedbackLoopGuard(
            tool_name=tool_name,
            original_params=params.copy(),
            max_retries=self.max_retries,
            max_cost=self.max_cost
        )

        self.active_guards[guard_id] = guard
        return guard

    def should_retry(
        self,
        guard: FeedbackLoopGuard,
        quality_result: QualityCheckResult
    ) -> bool:
        """
        智能判断是否应该重试

        综合考虑：
        1. 质量检查建议
        2. 护栏限制
        3. 历史反馈
        """
        # 护栏检查
        if not guard.can_retry():
            print(f"   🛑 护栏阻止: 已重试{guard.retry_count}次 或 成本${guard.total_cost_estimate:.2f}")
            return False

        # LLM建议检查
        if quality_result.suggested_action in ["continue", "skip"]:
            return False

        if quality_result.suggested_action in ["retry", "adjust_params", "change_strategy"]:
            # 检查是否在重复同样的问题
            if self._is_repeating_issue(guard, quality_result):
                print(f"   🔁 检测到重复问题，停止重试")
                return False

            return True

        return False

    def _is_repeating_issue(
        self,
        guard: FeedbackLoopGuard,
        current_result: QualityCheckResult
    ) -> bool:
        """检测是否在重复遇到相同问题"""
        if len(guard.feedback_history) < 2:
            return False

        # 简单检查：如果最近两次的问题相似，认为是重复
        last_issues = guard.feedback_history[-1].get("issues", [])
        current_issues = current_result.issues

        if not last_issues or not current_issues:
            return False

        # 检查是否有相同的问题描述
        for last_issue in last_issues:
            for current_issue in current_issues:
                if last_issue.lower() in current_issue.lower() or current_issue.lower() in last_issue.lower():
                    return True

        return False

    def apply_adjustment(
        self,
        original_params: Dict[str, Any],
        quality_result: QualityCheckResult
    ) -> Dict[str, Any]:
        """
        应用LLM建议的调整

        智能合并原参数和调整建议
        """
        if not quality_result.adjustment_plan:
            return original_params.copy()

        adjusted = original_params.copy()

        # 应用调整建议
        for key, value in quality_result.adjustment_plan.items():
            adjusted[key] = value

        print(f"   🔧 参数调整: {quality_result.adjustment_plan}")

        return adjusted

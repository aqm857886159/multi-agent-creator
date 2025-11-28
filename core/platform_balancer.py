"""
平台平衡强制机制 (Platform Balance Enforcer)

基于 Manus Context Engineering 最佳实践:
- 硬性交替规则: YouTube → Bilibili → YouTube
- 任务队列按平台分组轮询
- 监控平台覆盖率指标

核心功能:
1. 强制交替执行 (Round-Robin)
2. 动态阈值调整
3. 平衡度监控与告警
"""

from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class BalanceMode(Enum):
    """平衡模式"""
    STRICT = "strict"          # 严格交替
    SOFT = "soft"              # 软平衡（允许一定偏差）
    ADAPTIVE = "adaptive"      # 自适应（根据任务可用性调整）


@dataclass
class PlatformStats:
    """平台统计"""
    youtube_count: int = 0
    bilibili_count: int = 0
    youtube_pending: int = 0
    bilibili_pending: int = 0
    last_platform: str = ""
    
    @property
    def total(self) -> int:
        return self.youtube_count + self.bilibili_count
    
    @property
    def balance_ratio(self) -> float:
        """平衡比例 (0-1, 0.5 为完美平衡)"""
        if self.total == 0:
            return 0.5
        return self.youtube_count / self.total
    
    @property
    def imbalance_degree(self) -> float:
        """不平衡程度 (0 为完美平衡, 1 为完全偏向一方)"""
        return abs(self.balance_ratio - 0.5) * 2
    
    def is_balanced(self, threshold: float = 0.3) -> bool:
        """是否平衡（默认允许 30% 偏差）"""
        return self.imbalance_degree <= threshold


class PlatformBalancer:
    """平台平衡器"""
    
    def __init__(
        self,
        mode: BalanceMode = BalanceMode.ADAPTIVE,
        soft_threshold: int = 5,      # 软平衡阈值
        strict_interval: int = 2,     # 严格模式下最大连续同平台次数
        min_tasks_for_balance: int = 4  # 最少任务数才启用平衡
    ):
        self.mode = mode
        self.soft_threshold = soft_threshold
        self.strict_interval = strict_interval
        self.min_tasks_for_balance = min_tasks_for_balance
        
        # 执行历史
        self.execution_history: List[str] = []
        self.balance_alerts: List[Dict[str, Any]] = []
    
    def get_stats(self, candidates: List[Any], task_queue: List[Any]) -> PlatformStats:
        """
        计算平台统计
        
        Args:
            candidates: 候选内容列表
            task_queue: 任务队列
        """
        stats = PlatformStats()
        
        # 统计已收集的内容
        for item in candidates:
            platform = getattr(item, 'platform', None) or item.get('platform', '')
            if platform == 'youtube':
                stats.youtube_count += 1
            elif platform == 'bilibili':
                stats.bilibili_count += 1
        
        # 统计待执行的任务
        for task in task_queue:
            status = getattr(task, 'status', None) or task.get('status', '')
            if status != 'pending':
                continue
            platform = getattr(task, 'platform', None) or task.get('platform', '')
            if platform == 'youtube':
                stats.youtube_pending += 1
            elif platform == 'bilibili':
                stats.bilibili_pending += 1
        
        # 最后执行的平台
        if self.execution_history:
            stats.last_platform = self.execution_history[-1]
        
        return stats
    
    def select_platform(
        self,
        stats: PlatformStats,
        available_platforms: List[str]
    ) -> Optional[str]:
        """
        选择下一个应该执行的平台
        
        Args:
            stats: 当前平台统计
            available_platforms: 可用的平台列表
            
        Returns:
            推荐的平台，None 表示任意
        """
        if not available_platforms:
            return None
        
        # 如果只有一个平台可用，直接返回
        if len(available_platforms) == 1:
            return available_platforms[0]
        
        # 根据模式选择
        if self.mode == BalanceMode.STRICT:
            return self._strict_select(stats, available_platforms)
        elif self.mode == BalanceMode.SOFT:
            return self._soft_select(stats, available_platforms)
        else:  # ADAPTIVE
            return self._adaptive_select(stats, available_platforms)
    
    def _strict_select(
        self,
        stats: PlatformStats,
        available_platforms: List[str]
    ) -> Optional[str]:
        """
        严格交替模式
        - 强制 YouTube → Bilibili → YouTube
        - 最多连续执行 strict_interval 次同平台
        """
        # 检查连续执行次数
        if len(self.execution_history) >= self.strict_interval:
            recent = self.execution_history[-self.strict_interval:]
            if len(set(recent)) == 1:  # 全是同一平台
                last_platform = recent[0]
                # 强制切换
                other = "bilibili" if last_platform == "youtube" else "youtube"
                if other in available_platforms:
                    logger.info(f"[STRICT] 强制切换: {last_platform} → {other}")
                    return other
        
        # 默认交替
        if stats.last_platform == "youtube" and "bilibili" in available_platforms:
            return "bilibili"
        elif stats.last_platform == "bilibili" and "youtube" in available_platforms:
            return "youtube"
        
        return available_platforms[0]
    
    def _soft_select(
        self,
        stats: PlatformStats,
        available_platforms: List[str]
    ) -> Optional[str]:
        """
        软平衡模式
        - 允许一定偏差（soft_threshold）
        - 超过阈值才强制切换
        """
        diff = stats.youtube_count - stats.bilibili_count
        
        if diff > self.soft_threshold and "bilibili" in available_platforms:
            logger.info(f"[SOFT] YouTube 领先 {diff} 条，优先 Bilibili")
            return "bilibili"
        
        if diff < -self.soft_threshold and "youtube" in available_platforms:
            logger.info(f"[SOFT] Bilibili 领先 {-diff} 条，优先 YouTube")
            return "youtube"
        
        # 在阈值内，不强制
        return None
    
    def _adaptive_select(
        self,
        stats: PlatformStats,
        available_platforms: List[str]
    ) -> Optional[str]:
        """
        自适应模式
        - 结合严格和软平衡
        - 根据任务可用性动态调整
        """
        # 如果任务太少，不做平衡
        if stats.total < self.min_tasks_for_balance:
            return None
        
        # 检查是否严重不平衡
        if stats.imbalance_degree > 0.5:  # 超过 50% 偏差
            # 强制切换到弱势平台
            if stats.youtube_count > stats.bilibili_count:
                if "bilibili" in available_platforms:
                    self._add_alert("severe_imbalance", stats, "bilibili")
                    return "bilibili"
            else:
                if "youtube" in available_platforms:
                    self._add_alert("severe_imbalance", stats, "youtube")
                    return "youtube"
        
        # 中度不平衡，使用软平衡
        if stats.imbalance_degree > 0.2:
            return self._soft_select(stats, available_platforms)
        
        # 轻度不平衡，检查连续执行
        if len(self.execution_history) >= 3:
            recent = self.execution_history[-3:]
            if len(set(recent)) == 1:
                # 连续 3 次同平台，建议切换
                last = recent[0]
                other = "bilibili" if last == "youtube" else "youtube"
                if other in available_platforms:
                    return other
        
        return None
    
    def record_execution(self, platform: str):
        """记录执行历史"""
        self.execution_history.append(platform)
        # 只保留最近 20 条
        if len(self.execution_history) > 20:
            self.execution_history = self.execution_history[-20:]
    
    def _add_alert(self, alert_type: str, stats: PlatformStats, action: str):
        """添加平衡告警"""
        self.balance_alerts.append({
            "type": alert_type,
            "youtube_count": stats.youtube_count,
            "bilibili_count": stats.bilibili_count,
            "imbalance_degree": stats.imbalance_degree,
            "action": action
        })
        logger.warning(f"[BALANCE ALERT] {alert_type}: YT={stats.youtube_count}, BL={stats.bilibili_count}, action={action}")
    
    def get_balance_report(self, stats: PlatformStats) -> Dict[str, Any]:
        """生成平衡报告"""
        return {
            "mode": self.mode.value,
            "youtube_count": stats.youtube_count,
            "bilibili_count": stats.bilibili_count,
            "balance_ratio": round(stats.balance_ratio, 2),
            "imbalance_degree": round(stats.imbalance_degree, 2),
            "is_balanced": stats.is_balanced(),
            "recent_executions": self.execution_history[-5:],
            "alerts_count": len(self.balance_alerts)
        }


# ============ 全局实例 ============

_balancer: Optional[PlatformBalancer] = None

def get_platform_balancer() -> PlatformBalancer:
    """获取全局平台平衡器"""
    global _balancer
    if _balancer is None:
        _balancer = PlatformBalancer(mode=BalanceMode.ADAPTIVE)
    return _balancer


# ============ 便捷函数 ============

def select_balanced_task(
    tasks: List[Any],
    candidates: List[Any],
    mode: BalanceMode = BalanceMode.ADAPTIVE
) -> Tuple[Optional[Any], str]:
    """
    选择平衡的任务
    
    Args:
        tasks: 待执行任务列表
        candidates: 已收集的候选内容
        mode: 平衡模式
        
    Returns:
        (选中的任务, 选择原因)
    """
    if not tasks:
        return None, "no_tasks"
    
    balancer = get_platform_balancer()
    balancer.mode = mode
    
    # 获取统计
    stats = balancer.get_stats(candidates, tasks)
    
    # 获取可用平台
    pending_tasks = [t for t in tasks if getattr(t, 'status', t.get('status', '')) == 'pending']
    available_platforms = list(set(
        getattr(t, 'platform', t.get('platform', '')) 
        for t in pending_tasks
    ))
    
    # 选择平台
    preferred_platform = balancer.select_platform(stats, available_platforms)
    
    if preferred_platform:
        # 从推荐平台选择最高优先级任务
        platform_tasks = [
            t for t in pending_tasks 
            if getattr(t, 'platform', t.get('platform', '')) == preferred_platform
        ]
        if platform_tasks:
            selected = max(platform_tasks, key=lambda t: getattr(t, 'priority', t.get('priority', 0)))
            reason = f"balanced_to_{preferred_platform}"
            balancer.record_execution(preferred_platform)
            return selected, reason
    
    # 没有推荐或推荐不可用，按优先级选择
    selected = max(pending_tasks, key=lambda t: getattr(t, 'priority', t.get('priority', 0)))
    platform = getattr(selected, 'platform', selected.get('platform', 'unknown'))
    balancer.record_execution(platform)
    return selected, "priority_based"


def get_balance_summary(candidates: List[Any], task_queue: List[Any]) -> str:
    """获取平衡摘要字符串"""
    balancer = get_platform_balancer()
    stats = balancer.get_stats(candidates, task_queue)
    report = balancer.get_balance_report(stats)
    
    status = "✅" if report["is_balanced"] else "⚠️"
    return (
        f"{status} 平台平衡: YT={report['youtube_count']} BL={report['bilibili_count']} "
        f"(偏差: {report['imbalance_degree']*100:.0f}%)"
    )


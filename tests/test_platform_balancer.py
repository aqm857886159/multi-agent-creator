"""
平台平衡强制机制测试
"""

import sys
import os

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.platform_balancer import (
    PlatformBalancer, 
    BalanceMode, 
    PlatformStats,
    select_balanced_task,
    get_balance_summary
)


def test_stats_calculation():
    """测试统计计算"""
    print("\n=== 测试 1: 统计计算 ===")
    
    balancer = PlatformBalancer()
    
    # 模拟候选内容
    candidates = [
        {"platform": "youtube", "title": "Video 1"},
        {"platform": "youtube", "title": "Video 2"},
        {"platform": "youtube", "title": "Video 3"},
        {"platform": "bilibili", "title": "视频 1"},
    ]
    
    # 模拟任务队列
    tasks = [
        {"platform": "youtube", "status": "pending"},
        {"platform": "bilibili", "status": "pending"},
        {"platform": "bilibili", "status": "completed"},
    ]
    
    stats = balancer.get_stats(candidates, tasks)
    
    assert stats.youtube_count == 3
    assert stats.bilibili_count == 1
    assert stats.youtube_pending == 1
    assert stats.bilibili_pending == 1
    print(f"✅ YouTube: {stats.youtube_count}, Bilibili: {stats.bilibili_count}")
    print(f"✅ 平衡比例: {stats.balance_ratio:.2f} (0.5 为完美)")
    print(f"✅ 不平衡度: {stats.imbalance_degree:.2f}")
    print(f"✅ 是否平衡: {stats.is_balanced()}")
    
    print("✅ 测试 1 通过!\n")


def test_strict_mode():
    """测试严格交替模式"""
    print("\n=== 测试 2: 严格交替模式 ===")
    
    balancer = PlatformBalancer(mode=BalanceMode.STRICT, strict_interval=2)
    
    # 模拟连续执行 YouTube
    balancer.execution_history = ["youtube", "youtube"]
    
    stats = PlatformStats(youtube_count=5, bilibili_count=3)
    
    # 应该强制切换到 Bilibili
    platform = balancer.select_platform(stats, ["youtube", "bilibili"])
    assert platform == "bilibili"
    print(f"✅ 连续 2 次 YouTube 后，强制切换到: {platform}")
    
    # 记录执行
    balancer.record_execution("bilibili")
    
    # 下一次应该可以选 YouTube
    platform = balancer.select_platform(stats, ["youtube", "bilibili"])
    assert platform == "youtube"
    print(f"✅ 执行 Bilibili 后，下一次: {platform}")
    
    print("✅ 测试 2 通过!\n")


def test_soft_mode():
    """测试软平衡模式"""
    print("\n=== 测试 3: 软平衡模式 ===")
    
    balancer = PlatformBalancer(mode=BalanceMode.SOFT, soft_threshold=5)
    
    # 轻度不平衡（差距 3）- 不强制
    stats1 = PlatformStats(youtube_count=8, bilibili_count=5)
    platform1 = balancer.select_platform(stats1, ["youtube", "bilibili"])
    assert platform1 is None  # 不强制
    print(f"✅ 差距 3 条: 不强制 (返回 {platform1})")
    
    # 超过阈值（差距 6）- 强制
    stats2 = PlatformStats(youtube_count=10, bilibili_count=4)
    platform2 = balancer.select_platform(stats2, ["youtube", "bilibili"])
    assert platform2 == "bilibili"
    print(f"✅ 差距 6 条: 强制 {platform2}")
    
    print("✅ 测试 3 通过!\n")


def test_adaptive_mode():
    """测试自适应模式"""
    print("\n=== 测试 4: 自适应模式 ===")
    
    balancer = PlatformBalancer(mode=BalanceMode.ADAPTIVE, min_tasks_for_balance=4)
    
    # 任务太少，不平衡
    stats1 = PlatformStats(youtube_count=2, bilibili_count=0)
    platform1 = balancer.select_platform(stats1, ["youtube", "bilibili"])
    assert platform1 is None  # 任务太少，不强制
    print(f"✅ 任务太少 (total={stats1.total}): 不强制")
    
    # 严重不平衡
    stats2 = PlatformStats(youtube_count=15, bilibili_count=2)
    platform2 = balancer.select_platform(stats2, ["youtube", "bilibili"])
    assert platform2 == "bilibili"
    print(f"✅ 严重不平衡 (YT:15 BL:2): 强制 {platform2}")
    
    # 检查告警
    assert len(balancer.balance_alerts) > 0
    print(f"✅ 触发告警: {len(balancer.balance_alerts)} 条")
    
    print("✅ 测试 4 通过!\n")


def test_select_balanced_task():
    """测试便捷函数"""
    print("\n=== 测试 5: 便捷函数 select_balanced_task ===")
    
    # 重置全局 balancer
    import core.platform_balancer as pb
    pb._balancer = None
    
    # 模拟任务
    tasks = [
        {"task_id": "yt_1", "platform": "youtube", "status": "pending", "priority": 80},
        {"task_id": "yt_2", "platform": "youtube", "status": "pending", "priority": 70},
        {"task_id": "bl_1", "platform": "bilibili", "status": "pending", "priority": 75},
    ]
    
    # YouTube 领先的候选内容 (差距 > 5)
    candidates = [
        {"platform": "youtube"},
        {"platform": "youtube"},
        {"platform": "youtube"},
        {"platform": "youtube"},
        {"platform": "youtube"},
        {"platform": "youtube"},
        {"platform": "youtube"},  # 7 个 YouTube
        {"platform": "bilibili"},  # 1 个 Bilibili
    ]
    
    selected, reason = select_balanced_task(tasks, candidates, BalanceMode.SOFT)
    
    print(f"✅ 选中任务: {selected['task_id']}")
    print(f"✅ 选择原因: {reason}")
    print(f"   平台: {selected['platform']}")
    
    # 在 SOFT 模式下，差距 6 条应该触发平衡
    # 应该选择 Bilibili 任务来平衡
    assert selected["platform"] == "bilibili", f"Expected bilibili, got {selected['platform']}"
    assert "balanced" in reason, f"Expected 'balanced' in reason, got {reason}"
    
    print("✅ 测试 5 通过!\n")


def test_balance_summary():
    """测试平衡摘要"""
    print("\n=== 测试 6: 平衡摘要 ===")
    
    candidates = [
        {"platform": "youtube"},
        {"platform": "youtube"},
        {"platform": "bilibili"},
        {"platform": "bilibili"},
    ]
    tasks = []
    
    summary = get_balance_summary(candidates, tasks)
    print(f"   {summary}")
    
    assert "YT=2" in summary
    assert "BL=2" in summary
    
    print("✅ 测试 6 通过!\n")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("平台平衡强制机制测试")
    print("=" * 60)
    
    try:
        test_stats_calculation()
        test_strict_mode()
        test_soft_mode()
        test_adaptive_mode()
        test_select_balanced_task()
        test_balance_summary()
        
        print("=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)


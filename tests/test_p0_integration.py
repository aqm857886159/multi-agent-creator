"""
P0 集成测试 - 验证 error_history 和 candidates 压缩功能
"""

import sys
import os

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_state_new_fields():
    """测试 RadarState 新增字段"""
    print("\n=== 测试 1: RadarState 新增字段 ===")
    
    from core.state import RadarState
    
    state = RadarState()
    
    # 检查 error_history 字段
    assert hasattr(state, 'error_history'), "缺少 error_history 字段"
    assert isinstance(state.error_history, list), "error_history 应该是列表"
    assert len(state.error_history) == 0, "error_history 初始应为空"
    print("✅ error_history 字段正常")
    
    # 检查 candidates_externalized 字段
    assert hasattr(state, 'candidates_externalized'), "缺少 candidates_externalized 字段"
    assert state.candidates_externalized == False, "candidates_externalized 初始应为 False"
    print("✅ candidates_externalized 字段正常")
    
    # 测试错误历史追加
    state.error_history.append({
        'tool_name': 'youtube_search',
        'error': 'API rate limit exceeded',
        'error_type': 'RateLimitError',
        'timestamp': '2025-11-28T12:00:00'
    })
    assert len(state.error_history) == 1
    print("✅ 错误历史追加成功")
    
    print("✅ 测试 1 通过!\n")


def test_compress_candidates():
    """测试候选内容压缩功能"""
    print("\n=== 测试 2: 候选内容压缩 ===")
    
    from core.memory import compress_candidates_if_needed
    
    # 小于阈值不压缩
    small_list = [{'url': f'http://test.com/{i}', 'title': f'Test {i}'} for i in range(5)]
    result, compressed = compress_candidates_if_needed(small_list, threshold=10)
    assert not compressed, "小于阈值不应压缩"
    assert len(result) == 5, "未压缩时应返回原列表"
    print("✅ 小于阈值不压缩")
    
    print("✅ 测试 2 通过!\n")


def test_executor_imports():
    """测试 executor 模块导入"""
    print("\n=== 测试 3: Executor 模块语法 ===")
    
    import ast
    
    # 检查语法
    executor_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'nodes', 'executor.py'
    )
    
    with open(executor_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # 解析 AST（验证语法正确）
    ast.parse(code)
    print("✅ executor.py 语法正确")
    
    # 检查新函数是否存在
    assert '_maybe_compress_candidates' in code, "缺少 _maybe_compress_candidates 函数"
    assert 'get_error_summary_for_planner' in code, "缺少 get_error_summary_for_planner 函数"
    assert 'error_history' in code, "executor 中应使用 error_history"
    assert 'compress_candidates_if_needed' in code, "executor 中应导入 compress_candidates_if_needed"
    print("✅ 新函数已添加")
    
    print("✅ 测试 3 通过!\n")


def test_platform_balancer():
    """测试平台平衡器"""
    print("\n=== 测试 4: 平台平衡器 ===")
    
    from core.platform_balancer import get_balance_summary, PlatformBalancer, BalanceMode
    
    # 基本功能
    summary = get_balance_summary([], [])
    assert "YT=" in summary and "BL=" in summary
    print(f"✅ 平衡摘要: {summary}")
    
    # 平衡器创建
    balancer = PlatformBalancer(mode=BalanceMode.ADAPTIVE)
    assert balancer.mode == BalanceMode.ADAPTIVE
    print("✅ 平衡器创建成功")
    
    print("✅ 测试 4 通过!\n")


def test_file_memory():
    """测试文件记忆"""
    print("\n=== 测试 5: 文件记忆 ===")
    
    import tempfile
    from core.memory import FileMemory
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = FileMemory(base_dir=tmpdir)
        
        # 存储
        candidates = [
            {'url': 'http://test.com/1', 'title': 'Test 1', 'platform': 'youtube'},
            {'url': 'http://test.com/2', 'title': 'Test 2', 'platform': 'bilibili'}
        ]
        compressed = memory.store_candidates(candidates)
        assert len(compressed) == 2
        print("✅ 候选内容存储成功")
        
        # 加载
        ref_id = compressed[0]['_ref_id']
        loaded = memory.load_candidate(ref_id)
        assert loaded is not None
        assert loaded['url'] == candidates[0]['url']
        print("✅ 候选内容加载成功")
        
        # 统计
        stats = memory.get_stats()
        assert stats['total_candidates'] == 2
        print(f"✅ 统计: {stats['total_candidates']} 条")
    
    print("✅ 测试 5 通过!\n")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("P0 集成测试")
    print("=" * 60)
    
    try:
        test_state_new_fields()
        test_compress_candidates()
        test_executor_imports()
        test_platform_balancer()
        test_file_memory()
        
        print("=" * 60)
        print("🎉 所有 P0 集成测试通过!")
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


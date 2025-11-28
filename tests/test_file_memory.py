"""
文件系统外部记忆机制测试

验证:
1. 候选内容存储和加载
2. 压缩和恢复机制
3. 索引管理
"""

import sys
import os

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import FileMemory, compress_candidates_if_needed
import tempfile
import shutil


def test_basic_storage():
    """测试基本存储功能"""
    print("\n=== 测试 1: 基本存储功能 ===")
    
    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = FileMemory(base_dir=tmpdir)
        
        # 创建测试数据
        candidates = [
            {
                "url": "https://youtube.com/watch?v=abc123",
                "title": "AI Tutorial Part 1",
                "platform": "youtube",
                "view_count": 10000,
                "author_name": "TechChannel",
                "raw_data": {"extra": "info"}
            },
            {
                "url": "https://bilibili.com/video/BV123",
                "title": "AI 教程第一集",
                "platform": "bilibili",
                "view_count": 5000,
                "author_name": "科技频道"
            }
        ]
        
        # 存储
        compressed = memory.store_candidates(candidates)
        print(f"✅ 存储 {len(candidates)} 条候选内容")
        print(f"   压缩后: {len(compressed)} 条引用")
        
        # 验证压缩引用包含必要字段
        assert len(compressed) == 2
        assert "_ref_id" in compressed[0]
        assert "url" in compressed[0]
        print(f"   引用示例: {compressed[0]}")
        
        # 加载单个
        ref_id = compressed[0]["_ref_id"]
        loaded = memory.load_candidate(ref_id)
        assert loaded is not None
        assert loaded["url"] == candidates[0]["url"]
        print(f"✅ 加载单个候选内容成功")
        
        # 批量加载
        all_refs = [c["_ref_id"] for c in compressed]
        batch_loaded = memory.load_candidates_batch(all_refs)
        assert len(batch_loaded) == 2
        print(f"✅ 批量加载 {len(batch_loaded)} 条成功")
        
        # 统计
        stats = memory.get_stats()
        print(f"✅ 统计: {stats}")
        
    print("✅ 测试 1 通过!\n")


def test_compression_threshold():
    """测试压缩阈值"""
    print("\n=== 测试 2: 压缩阈值 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = FileMemory(base_dir=tmpdir)
        
        # 创建超过阈值的数据
        threshold = 10
        candidates = [
            {
                "url": f"https://example.com/video/{i}",
                "title": f"Video {i}",
                "platform": "youtube",
                "view_count": i * 100
            }
            for i in range(15)
        ]
        
        # 测试 compress_candidates_if_needed
        # 小于阈值不压缩
        small_list = candidates[:5]
        result, compressed = compress_candidates_if_needed(small_list, threshold)
        assert not compressed
        print(f"✅ 小于阈值 ({len(small_list)}/{threshold}) 不压缩")
        
        # 大于阈值压缩
        # 注意：这里需要使用新的 memory 实例来避免重复
        memory2 = FileMemory(base_dir=tmpdir + "/mem2")
        
        # 手动测试压缩
        state = {"candidates": candidates}
        compressed_state = memory2.compress_state(state, threshold=10)
        
        assert compressed_state.get("_candidates_externalized") == True
        print(f"✅ 大于阈值 ({len(candidates)}/{threshold}) 触发压缩")
        
        # 恢复
        restored = memory2.restore_candidates(compressed_state["candidates"])
        assert len(restored) == len(candidates)
        print(f"✅ 恢复 {len(restored)} 条候选内容")
        
    print("✅ 测试 2 通过!\n")


def test_scratchpad():
    """测试 scratchpad 追加模式"""
    print("\n=== 测试 3: Scratchpad 追加模式 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = FileMemory(base_dir=tmpdir)
        
        # 追加多个条目
        entries = [
            {"type": "tool_call", "tool_name": "web_search", "args": {"query": "AI"}},
            {"type": "tool_result", "status": "success", "data": ["result1"]},
            {"type": "tool_call", "tool_name": "youtube_search", "args": {"keyword": "AI tutorial"}}
        ]
        
        for entry in entries:
            memory.append_scratchpad(entry)
        
        print(f"✅ 追加 {len(entries)} 条 scratchpad 条目")
        
        # 获取最近的
        recent = memory.get_recent_scratchpad(limit=2)
        assert len(recent) == 2
        print(f"✅ 获取最近 2 条: {[e['type'] for e in recent]}")
        
        # 验证顺序（最新的在后面）
        assert recent[-1]["tool_name"] == "youtube_search"
        print(f"✅ 顺序正确（追加模式）")
        
    print("✅ 测试 3 通过!\n")


def test_index_persistence():
    """测试索引持久化"""
    print("\n=== 测试 4: 索引持久化 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 第一次使用
        memory1 = FileMemory(base_dir=tmpdir)
        memory1.store_candidates([
            {"url": "https://test.com/1", "title": "Test 1", "platform": "youtube"}
        ])
        stats1 = memory1.get_stats()
        print(f"   第一次存储后: {stats1['total_candidates']} 条")
        
        # 第二次使用（模拟重启）
        memory2 = FileMemory(base_dir=tmpdir)
        stats2 = memory2.get_stats()
        print(f"   重新加载后: {stats2['total_candidates']} 条")
        
        assert stats2["total_candidates"] == stats1["total_candidates"]
        print(f"✅ 索引持久化成功")
        
        # 继续存储
        memory2.store_candidates([
            {"url": "https://test.com/2", "title": "Test 2", "platform": "bilibili"}
        ])
        stats3 = memory2.get_stats()
        assert stats3["total_candidates"] == 2
        print(f"✅ 增量存储成功: {stats3['total_candidates']} 条")
        
    print("✅ 测试 4 通过!\n")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("文件系统外部记忆机制测试")
    print("=" * 60)
    
    try:
        test_basic_storage()
        test_compression_threshold()
        test_scratchpad()
        test_index_persistence()
        
        print("=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)


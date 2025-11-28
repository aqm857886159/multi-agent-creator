"""
P3 集成测试 - 验证 Skills 集成和 Reducer 应用
"""

import sys
import os

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_skills_loading():
    """测试 Skills 加载"""
    print("\n=== 测试 1: Skills 加载 ===")
    
    from skills import get_skill_loader, load_relevant_skills, get_skill_context
    
    loader = get_skill_loader()
    skills = loader.load_all()
    
    assert len(skills) >= 3, f"应至少有 3 个 Skills，实际: {len(skills)}"
    print(f"✅ 加载了 {len(skills)} 个 Skills")
    
    # 检查核心 Skills
    assert 'bilibili_expert' in skills
    assert 'youtube_expert' in skills
    assert 'content_filter' in skills
    print("✅ 核心 Skills 存在")
    
    print("✅ 测试 1 通过!\n")


def test_skills_matching():
    """测试 Skills 匹配"""
    print("\n=== 测试 2: Skills 匹配 ===")
    
    from skills import load_relevant_skills
    
    # 测试 B站关键词
    bilibili_skills = load_relevant_skills("搜索 B站 视频")
    assert len(bilibili_skills) > 0
    assert bilibili_skills[0].name == 'bilibili_expert'
    print(f"✅ 'B站' 匹配到: {bilibili_skills[0].name}")
    
    # 测试 YouTube 关键词
    youtube_skills = load_relevant_skills("find YouTube tutorials")
    assert len(youtube_skills) > 0
    assert youtube_skills[0].name == 'youtube_expert'
    print(f"✅ 'YouTube' 匹配到: {youtube_skills[0].name}")
    
    # 测试筛选关键词
    filter_skills = load_relevant_skills("筛选高质量内容")
    assert len(filter_skills) > 0
    assert filter_skills[0].name == 'content_filter'
    print(f"✅ '筛选' 匹配到: {filter_skills[0].name}")
    
    # 测试无匹配
    no_match = load_relevant_skills("天气预报")
    assert len(no_match) == 0
    print("✅ 无关词汇无匹配")
    
    print("✅ 测试 2 通过!\n")


def test_skill_context_generation():
    """测试 Skill 上下文生成"""
    print("\n=== 测试 3: Skill 上下文生成 ===")
    
    from skills import get_skill_context
    
    context = get_skill_context("搜索 bilibili AI 教程", max_skills=1)
    
    assert '<relevant_skills>' in context
    assert '<skill name="bilibili_expert">' in context
    assert '</relevant_skills>' in context
    print("✅ 上下文格式正确")
    
    # 检查内容
    assert '综合排序' in context or 'comprehensive' in context
    print("✅ 上下文包含专业知识")
    
    print("✅ 测试 3 通过!\n")


def test_reducer_functions():
    """测试 Reducer 函数"""
    print("\n=== 测试 4: Reducer 函数 ===")
    
    from core.state_reducers import (
        append_reducer,
        merge_dict_reducer,
        dedupe_append_reducer,
        capped_append_reducer
    )
    
    # 测试 append_reducer
    result = append_reducer([1, 2], [3, 4])
    assert result == [1, 2, 3, 4]
    print("✅ append_reducer 正常")
    
    # 测试 merge_dict_reducer
    result = merge_dict_reducer({'a': 1}, {'b': 2, 'a': 3})
    assert result == {'a': 3, 'b': 2}
    print("✅ merge_dict_reducer 正常")
    
    # 测试 dedupe_append_reducer
    result = dedupe_append_reducer([1, 2, 3], [2, 3, 4, 5])
    assert result == [1, 2, 3, 4, 5]
    print("✅ dedupe_append_reducer 正常")
    
    # 测试 capped_append_reducer
    result = capped_append_reducer([1, 2, 3], [4, 5, 6], max_size=4)
    assert result == [3, 4, 5, 6]
    print("✅ capped_append_reducer 正常")
    
    print("✅ 测试 4 通过!\n")


def test_executor_reducer_helpers():
    """测试 Executor 中的 Reducer 辅助函数"""
    print("\n=== 测试 5: Executor Reducer 辅助函数 ===")
    
    import ast
    
    executor_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'nodes', 'executor.py'
    )
    
    with open(executor_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # 检查新函数
    assert '_dedupe_candidates' in code
    assert '_safe_extend_candidates' in code
    assert '_safe_append_error' in code
    assert '_safe_merge_progress' in code
    print("✅ Reducer 辅助函数已添加")
    
    # 检查导入
    assert 'from core.state_reducers import' in code
    print("✅ state_reducers 已导入")
    
    print("✅ 测试 5 通过!\n")


def test_planner_skills_integration():
    """测试 Planner 中的 Skills 集成"""
    print("\n=== 测试 6: Planner Skills 集成 ===")
    
    import ast
    
    planner_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'nodes', 'planner.py'
    )
    
    with open(planner_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # 检查 Skills 导入
    assert 'from skills import get_skill_context' in code
    print("✅ Skills 已在 _llm_generate_tasks 中导入")
    
    # 检查 Skills 使用
    assert 'skill_context = get_skill_context' in code
    print("✅ Skills 上下文已生成")
    
    print("✅ 测试 6 通过!\n")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("P3 集成测试")
    print("=" * 60)
    
    try:
        test_skills_loading()
        test_skills_matching()
        test_skill_context_generation()
        test_reducer_functions()
        test_executor_reducer_helpers()
        test_planner_skills_integration()
        
        print("=" * 60)
        print("🎉 所有 P3 集成测试通过!")
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


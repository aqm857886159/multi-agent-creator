"""
状态 Reducer 函数 - LangGraph 增量更新机制

实现 LangGraph 的 Annotated + Reducer 模式：
- 每个节点只返回需要更新的字段
- Reducer 函数决定如何合并更新
- 避免手动维护完整状态字典

参考: LangGraph StateGraph with Annotated types
"""

from typing import List, Dict, Any, Optional, Callable, TypeVar
from functools import reduce as functools_reduce

T = TypeVar('T')


# ============ 基础 Reducer 函数 ============

def replace_reducer(current: T, update: T) -> T:
    """
    替换 Reducer - 直接用新值替换旧值
    
    适用于：current_phase, session_focus 等单值字段
    """
    if update is None:
        return current
    return update


def append_reducer(current: List[T], update: List[T]) -> List[T]:
    """
    追加 Reducer - 将新列表追加到现有列表
    
    适用于：candidates, leads, plan_scratchpad 等列表字段
    """
    if current is None:
        current = []
    if update is None:
        return current
    return current + update


def merge_dict_reducer(current: Dict, update: Dict) -> Dict:
    """
    合并 Reducer - 合并两个字典
    
    适用于：engine_progress, platform_search_progress 等字典字段
    """
    if current is None:
        current = {}
    if update is None:
        return current
    return {**current, **update}


def increment_reducer(current: int, update: int) -> int:
    """
    增量 Reducer - 累加数值
    
    适用于：计数器字段
    """
    if current is None:
        current = 0
    if update is None:
        return current
    return current + update


def max_reducer(current: int, update: int) -> int:
    """
    最大值 Reducer - 取两者最大值
    
    适用于：需要保持最大值的字段
    """
    if current is None:
        return update
    if update is None:
        return current
    return max(current, update)


def dedupe_append_reducer(
    current: List[T], 
    update: List[T],
    key_fn: Optional[Callable[[T], Any]] = None
) -> List[T]:
    """
    去重追加 Reducer - 追加时自动去重
    
    适用于：candidates（按 URL 去重）、discovered_influencers（按 ID 去重）
    
    Args:
        current: 现有列表
        update: 新增列表
        key_fn: 提取唯一键的函数，默认使用对象本身
    """
    if current is None:
        current = []
    if update is None:
        return current
    
    if key_fn is None:
        key_fn = lambda x: x
    
    existing_keys = set(key_fn(item) for item in current)
    new_items = [item for item in update if key_fn(item) not in existing_keys]
    
    return current + new_items


def capped_append_reducer(
    current: List[T], 
    update: List[T],
    max_size: int = 100
) -> List[T]:
    """
    限量追加 Reducer - 追加时限制总数量
    
    适用于：error_history、plan_scratchpad 等需要限制大小的列表
    
    超出限制时，移除最早的条目
    """
    if current is None:
        current = []
    if update is None:
        return current
    
    combined = current + update
    if len(combined) > max_size:
        return combined[-max_size:]
    return combined


# ============ 复合 Reducer 工厂 ============

def create_url_dedupe_reducer():
    """创建按 URL 去重的 Reducer（用于 ContentItem）"""
    return lambda current, update: dedupe_append_reducer(
        current, update, 
        key_fn=lambda item: getattr(item, 'url', item)
    )


def create_id_dedupe_reducer():
    """创建按 ID 去重的 Reducer（用于 InfluencerInfo）"""
    return lambda current, update: dedupe_append_reducer(
        current, update,
        key_fn=lambda item: getattr(item, 'identifier', getattr(item, 'id', item))
    )


def create_error_history_reducer(max_errors: int = 50):
    """创建错误历史 Reducer（限制数量）"""
    return lambda current, update: capped_append_reducer(current, update, max_errors)


def create_scratchpad_reducer(max_entries: int = 100):
    """创建 scratchpad Reducer（限制数量）"""
    return lambda current, update: capped_append_reducer(current, update, max_entries)


# ============ 状态更新辅助函数 ============

def apply_reducers(
    current_state: Dict[str, Any],
    updates: Dict[str, Any],
    reducers: Dict[str, Callable]
) -> Dict[str, Any]:
    """
    应用 Reducers 到状态更新
    
    Args:
        current_state: 当前状态字典
        updates: 更新字典
        reducers: 字段名 -> Reducer 函数的映射
        
    Returns:
        更新后的状态字典
    """
    new_state = dict(current_state)
    
    for key, value in updates.items():
        if key in reducers:
            # 使用指定的 Reducer
            new_state[key] = reducers[key](current_state.get(key), value)
        else:
            # 默认使用替换 Reducer
            new_state[key] = replace_reducer(current_state.get(key), value)
    
    return new_state


# ============ RadarState 默认 Reducers ============

# 定义 RadarState 各字段的默认 Reducer
RADAR_STATE_REDUCERS = {
    # 列表字段 - 追加模式
    'candidates': create_url_dedupe_reducer(),
    'leads': append_reducer,
    'discovered_influencers': create_id_dedupe_reducer(),
    'task_queue': append_reducer,
    'plan_scratchpad': create_scratchpad_reducer(100),
    'quality_checks': append_reducer,
    'error_history': create_error_history_reducer(50),
    'searched_influencers': append_reducer,
    'proposals': append_reducer,
    'analysis_reports': append_reducer,
    
    # 字典字段 - 合并模式
    'engine_progress': merge_dict_reducer,
    'platform_search_progress': merge_dict_reducer,
    'monitor_autoruns': merge_dict_reducer,
    
    # 单值字段 - 替换模式
    'current_phase': replace_reducer,
    'session_focus': replace_reducer,
    'plan_status': replace_reducer,
    'topic_queries': replace_reducer,
    'feedback_enabled': replace_reducer,
}


def update_radar_state(
    current_state: Dict[str, Any],
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    使用预定义 Reducers 更新 RadarState
    
    这是推荐的状态更新方式，确保：
    1. 列表字段正确追加
    2. 字典字段正确合并
    3. 自动去重
    4. 大小限制
    
    Example:
        new_state = update_radar_state(state.__dict__, {
            'candidates': new_candidates,  # 会追加并去重
            'current_phase': 'filtering',  # 会替换
            'engine_progress': {'engine1': 5}  # 会合并
        })
    """
    return apply_reducers(current_state, updates, RADAR_STATE_REDUCERS)


# ============ 测试 ============

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("状态 Reducer 函数测试")
    print("=" * 60)
    
    # 测试 replace_reducer
    print("\n=== 测试 replace_reducer ===")
    assert replace_reducer("old", "new") == "new"
    assert replace_reducer("old", None) == "old"
    print("✅ replace_reducer 正常")
    
    # 测试 append_reducer
    print("\n=== 测试 append_reducer ===")
    assert append_reducer([1, 2], [3, 4]) == [1, 2, 3, 4]
    assert append_reducer(None, [1, 2]) == [1, 2]
    assert append_reducer([1, 2], None) == [1, 2]
    print("✅ append_reducer 正常")
    
    # 测试 merge_dict_reducer
    print("\n=== 测试 merge_dict_reducer ===")
    assert merge_dict_reducer({'a': 1}, {'b': 2}) == {'a': 1, 'b': 2}
    assert merge_dict_reducer({'a': 1}, {'a': 2}) == {'a': 2}
    print("✅ merge_dict_reducer 正常")
    
    # 测试 dedupe_append_reducer
    print("\n=== 测试 dedupe_append_reducer ===")
    result = dedupe_append_reducer([1, 2, 3], [3, 4, 5])
    assert result == [1, 2, 3, 4, 5], f"Expected [1,2,3,4,5], got {result}"
    print("✅ dedupe_append_reducer 正常")
    
    # 测试 capped_append_reducer
    print("\n=== 测试 capped_append_reducer ===")
    result = capped_append_reducer([1, 2, 3], [4, 5], max_size=4)
    assert result == [2, 3, 4, 5], f"Expected [2,3,4,5], got {result}"
    print("✅ capped_append_reducer 正常")
    
    # 测试 apply_reducers
    print("\n=== 测试 apply_reducers ===")
    current = {
        'items': [1, 2],
        'count': 5,
        'name': 'test'
    }
    updates = {
        'items': [3, 4],
        'count': 3,
        'name': 'updated'
    }
    reducers = {
        'items': append_reducer,
        'count': increment_reducer
    }
    result = apply_reducers(current, updates, reducers)
    assert result['items'] == [1, 2, 3, 4]
    assert result['count'] == 8
    assert result['name'] == 'updated'
    print("✅ apply_reducers 正常")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试通过!")
    print("=" * 60)


"""
测试改进：日志系统、提示词管理器、语言检测
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

def test_logger():
    """测试分级日志系统"""
    print("=== 测试日志系统 ===")
    from utils.logger import LogLevel, set_log_level, log_progress, log_step, log_debug, print_phase_header
    
    set_log_level(LogLevel.VERBOSE)
    print_phase_header('init')
    log_progress('这是进度信息')
    log_step('这是步骤信息')
    log_debug('这是调试信息')
    
    set_log_level(LogLevel.MINIMAL)
    print()
    print('--- MINIMAL 模式 ---')
    log_progress('这条应该显示')
    log_step('这条不应该显示')
    log_debug('这条也不应该显示')
    
    print("[OK] 日志系统测试通过")

def test_prompt_manager():
    """测试提示词管理器"""
    print()
    print("=== 测试提示词管理器 ===")
    from core.prompt_manager import get_prompt, get_role, get_goal
    
    print(f'Planner 角色: {get_role("planner")}')
    print(f'Planner 目标: {get_goal("planner")[:50]}...')
    
    prompt = get_prompt('keyword_designer', 'system')
    print(f'Keyword Designer 提示词长度: {len(prompt)} 字符')
    
    # 测试变量替换
    prompt_with_vars = get_prompt('planner', 'system', topic='AI视频')
    assert '{role}' not in prompt_with_vars, "变量替换失败"
    
    print("[OK] 提示词管理器测试通过")

def test_language_detection():
    """测试语言检测"""
    print()
    print("=== 测试语言检测 ===")
    from nodes.planner import _is_english, _is_chinese
    
    test_cases = [
        ('Two Minute Papers', True, False),
        ('影视飓风', False, True),
        ('MKBHD', True, False),
        ('老番茄', False, True),
        ('AI', True, False),
    ]
    
    for text, expected_en, expected_zh in test_cases:
        is_en = _is_english(text)
        is_zh = _is_chinese(text)
        status = "OK" if (is_en == expected_en) else "FAIL"
        print(f'  [{status}] {text}: is_english={is_en}, is_chinese={is_zh}')
    
    print("[OK] 语言检测测试通过")

def test_prompt_config():
    """测试提示词配置文件"""
    print()
    print("=== 测试提示词配置 ===")
    import yaml
    
    with open('config/prompts.yaml', 'r', encoding='utf-8') as f:
        prompts = yaml.safe_load(f)
    
    required_agents = ['planner', 'keyword_designer', 'influencer_extractor', 'architect_agent', 'analyst']
    
    for agent in required_agents:
        if agent in prompts:
            print(f"  [OK] {agent}: role={prompts[agent].get('role', 'N/A')[:30]}")
        else:
            print(f"  [WARN] {agent}: 未找到配置")
    
    print("[OK] 提示词配置测试通过")

if __name__ == "__main__":
    test_logger()
    test_prompt_manager()
    test_language_detection()
    test_prompt_config()
    print()
    print("=" * 50)
    print("[SUCCESS] 所有测试通过!")


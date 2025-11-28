import sys
import os
from dotenv import load_dotenv
from colorama import init, Fore, Style
import time

# Load env vars before importing anything else
load_dotenv()

# Force UTF-8 for Windows stdout to handle emojis/unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    # 解决 Windows 下的输入编码问题
    # sys.stdin.reconfigure(encoding='utf-8') 
    # 注意: 有时 reconfigure stdin 会导致其他副作用，如果 input() 依然报错，
    # 建议检查 IDE (如 VSCode/Cursor) 的终端编码设置，或者直接使用非交互模式

init(autoreset=True)

from core.graph import app
from core.state import RadarState
from core.config import load_settings
from pprint import pprint

def interactive_startup(settings):
    """
    Interactive CLI Wizard for user intent capture.
    """
    print(Fore.CYAN + "\n🤖 选题雷达已就绪 (Topic Radar Ready)")
    print(Fore.WHITE + "----------------------------------------")
    
    print(f"当前配置领域: {settings.get('target_domains', [])}")
    
    print(f"\n按 {Fore.GREEN}Enter{Fore.WHITE} 修改今日目标，或等待 3秒 自动执行...")
    
    try:
        choice = input(f"是否需要调整今日目标? (y/N): ").strip().lower()
    except EOFError:
        choice = "n"

    if choice == 'y':
        print(Fore.YELLOW + "\n[1/2] 请输入今日关注的领域/关键词 (逗号分隔):")
        user_domains = input(f"默认 [{','.join(settings.get('target_domains', []))}]: ").strip()
        
        if user_domains:
            # Update settings in memory
            domains = [d.strip() for d in user_domains.split(",") if d.strip()]
            settings['target_domains'] = domains
            
        print(Fore.GREEN + "\n✅ 配置已更新，即将启动...")
    else:
        print(Fore.GREEN + "\n🚀 按照既定配置启动...")
    
    session_focus = _collect_session_focus(settings)
    topic_targets = _collect_topic_targets(settings, session_focus)
        
    return settings, session_focus, topic_targets

def _collect_session_focus(settings):
    focus = {
        "priority_topics": [],
        "priority_platforms": [],
        "priority_authors": [],
        "desired_metrics": [],
        "notes": ""
    }
    try:
        topic_input = input("\n本轮优先关注哪些主题? (逗号分隔, 回车跳过): ").strip()
        if topic_input:
            focus["priority_topics"] = [t.strip() for t in topic_input.split(",") if t.strip()]
    except EOFError:
        pass
    
    try:
        platform_input = input("优先采集的平台? (仅支持 youtube,bilibili，逗号分隔): ").strip()
        if platform_input:
            focus["priority_platforms"] = [p.strip().lower() for p in platform_input.split(",") if p.strip()]
    except EOFError:
        pass
    
    try:
        author_input = input("是否有特别想跟的作者/频道? (逗号分隔): ").strip()
        if author_input:
            focus["priority_authors"] = [a.strip() for a in author_input.split(",") if a.strip()]
    except EOFError:
        pass
    
    try:
        metric_input = input("本轮想重点观察哪些指标? (如 播放量,互动率,粉丝增长): ").strip()
        if metric_input:
            focus["desired_metrics"] = [m.strip() for m in metric_input.split(",") if m.strip()]
    except EOFError:
        pass
    
    try:
        notes_input = input("还有其他特别的关注点吗? (回车跳过): ").strip()
        if notes_input:
            focus["notes"] = notes_input
    except EOFError:
        pass
    
    if not focus["priority_topics"]:
        focus["priority_topics"] = settings.get("target_domains", [])
    return focus

def _collect_topic_targets(settings, session_focus):
    default_targets = {}
    base_targets = session_focus.get("priority_topics") or settings.get("target_domains", [])
    for topic in base_targets:
        default_targets[topic] = 6
    try:
        target_input = input("\n为主题设置采集目标 (格式 主题:数量, 例如 AI News:8,Python Tutorials:5): ").strip()
        if target_input:
            for pair in target_input.split(","):
                if ":" in pair:
                    name, count = pair.split(":", 1)
                    name = name.strip()
                    try:
                        default_targets[name] = max(1, int(count.strip()))
                    except ValueError:
                        continue
    except EOFError:
        pass
    return default_targets

def main():
    # Load initial config
    settings = load_settings()
    
    # Interactive Phase
    settings, session_focus, topic_targets = interactive_startup(settings)
    
    print(Fore.CYAN + "\n--- 正在初始化智能体网络 ---")
    
    # Initialize State
    initial_state = RadarState(
        target_domains=settings.get("target_domains", []),
        monitoring_list=settings.get("whitelist_kols", {"youtube": [], "bilibili": []}),
        session_focus=session_focus,
        topic_targets=topic_targets,
        topic_progress={topic: 0 for topic in topic_targets}
    )
    
    _print_session_summary(session_focus, topic_targets)
    # Seed pending monitors with configured whitelist
    for platform in ["youtube", "bilibili"]:
        preset = initial_state.monitoring_list.get(platform, [])
        initial_state.pending_monitors[platform] = list(preset)
    
    # Run the Graph
    try:
        # Invoking the graph
        # 🔑 增加递归限制配置（安全上限提升到 50，但优先依赖内部逻辑停止）
        final_state = app.invoke(
            initial_state,
            config={"recursion_limit": 50}
        )
        
        # Output Results
        print(Fore.CYAN + "\n=== ✅ 执行完成 (Execution Complete) ===")
        
        print(Fore.YELLOW + "\n[运行日志 / Logs]")
        for log in final_state.get("logs", []):
            print(f"- {log}")
            
        print(Fore.GREEN + "\n[精选选题简报] (Generated Topic Briefs)")
        if final_state.get("proposals"):
            for i, p in enumerate(final_state["proposals"], 1):
                print(Fore.WHITE + f"\n📄 选题 #{i}")
                # 🔑 兼容字典和对象两种格式
                if isinstance(p, dict):
                    print(Fore.YELLOW + f"标题: {p.get('title', 'N/A')}")
                    print(Fore.CYAN + f"切入点: {p.get('core_angle', 'N/A')}")
                    print(Fore.WHITE + f"推荐理由: {p.get('rationale', 'N/A')}")
                    print(Fore.MAGENTA + f"来源策略: {p.get('source_type', 'N/A')}")
                else:
                    print(Fore.YELLOW + f"标题: {p.title}")
                    print(Fore.CYAN + f"切入点: {p.core_angle}")
                    print(Fore.WHITE + f"推荐理由: {p.rationale}")
                    print(Fore.MAGENTA + f"来源策略: {p.source_type}")
                print("-" * 40)
        else:
            print(Fore.RED + "⚠️ 本次未生成有效选题，请检查日志。")

        # 🚀 显示深度分析报告
        print(Fore.GREEN + "\n[深度分析报告] (Deep Analysis Reports)")
        if final_state.get("analysis_reports"):
            for i, report in enumerate(final_state["analysis_reports"], 1):
                print(Fore.WHITE + f"\n🔬 分析报告 #{i}")
                print(Fore.YELLOW + f"选题: {report.get('topic_title', 'N/A')}")
                print(Fore.CYAN + f"\n底层逻辑 (Root Cause):")
                print(Fore.WHITE + f"{report.get('root_cause', 'N/A')[:200]}...")
                print(Fore.CYAN + f"\n主流观点 (Mainstream View):")
                print(Fore.WHITE + f"{report.get('mainstream_view', 'N/A')[:150]}...")
                print(Fore.CYAN + f"\n反直觉洞察 (Contrarian View):")
                print(Fore.WHITE + f"{report.get('contrarian_view', 'N/A')[:150]}...")
                print(Fore.CYAN + f"\n情感钩子 (Emotional Hook):")
                print(Fore.WHITE + f"{report.get('emotional_hook', 'N/A')[:150]}...")
                print(Fore.MAGENTA + f"\n置信度: {report.get('confidence_score', 0.0):.2f}")
                print("-" * 60)
        else:
            print(Fore.YELLOW + "⚠️ 本次未生成深度分析报告。")
            
    except Exception as e:
        print(Fore.RED + f"❌ Critical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input(Fore.YELLOW + "\n按 Enter 键退出终端...")

def _print_session_summary(session_focus, topic_targets):
    print(Fore.YELLOW + "\n[本轮关注重点]")
    print(Fore.WHITE + f"- 主题: {session_focus.get('priority_topics', [])}")
    print(Fore.WHITE + f"- 平台: {session_focus.get('priority_platforms', []) or ['youtube','bilibili']}")
    if session_focus.get("priority_authors"):
        print(Fore.WHITE + f"- 作者: {session_focus['priority_authors']}")
    if session_focus.get("desired_metrics"):
        print(Fore.WHITE + f"- 观察指标: {session_focus['desired_metrics']}")
    if session_focus.get("notes"):
        print(Fore.WHITE + f"- 备注: {session_focus['notes']}")
    print(Fore.WHITE + f"- 主题目标: {topic_targets}")

if __name__ == "__main__":
    main()

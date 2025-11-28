"""
快速检查所有依赖是否已安装
"""
import sys

def check_dependency(package_name, import_name=None):
    """检查单个依赖"""
    if import_name is None:
        import_name = package_name

    try:
        __import__(import_name)
        print(f"✅ {package_name:30} 已安装")
        return True
    except ImportError:
        print(f"❌ {package_name:30} 未安装")
        return False

def check_command(command):
    """检查命令行工具是否可用"""
    import shutil
    if shutil.which(command):
        print(f"✅ {command:30} 可用")
        return True
    else:
        print(f"❌ {command:30} 不可用")
        return False

def main():
    print("="*60)
    print("🔍 检查项目依赖")
    print("="*60)

    dependencies = [
        # 核心依赖
        ("pydantic", "pydantic"),
        ("python-dotenv", "dotenv"),
        ("openai", "openai"),
        ("instructor", "instructor"),

        # LangChain
        ("langchain", "langchain"),
        ("langchain-openai", "langchain_openai"),

        # 爬虫工具
        ("scrapetube", "scrapetube"),
        ("bilibili-api-python", "bilibili_api"),
        ("feedparser", "feedparser"),
    ]

    print("\n📦 Python 包检查:")
    print("-" * 60)
    results = []
    for package, import_name in dependencies:
        results.append(check_dependency(package, import_name))

    print("\n🛠️ 命令行工具检查:")
    print("-" * 60)
    cmd_results = []
    cmd_results.append(check_command("yt-dlp"))
    cmd_results.append(check_command("python"))

    print("\n" + "="*60)
    print("📊 检查结果")
    print("="*60)

    total_packages = len(dependencies)
    passed_packages = sum(results)
    print(f"Python 包: {passed_packages}/{total_packages} 已安装")

    total_commands = len(cmd_results)
    passed_commands = sum(cmd_results)
    print(f"命令行工具: {passed_commands}/{total_commands} 可用")

    if passed_packages == total_packages and passed_commands == total_commands:
        print("\n🎉 所有依赖都已就绪！")
        print("\n下一步: 运行测试")
        print("  python test_tools.py")
    else:
        print("\n⚠️ 部分依赖缺失")
        print("\n解决方案:")
        print("  pip install -r requirements.txt")

        if not check_command("yt-dlp"):
            print("\n额外安装 yt-dlp:")
            print("  pip install yt-dlp")

if __name__ == "__main__":
    main()

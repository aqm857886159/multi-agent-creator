"""
Skill Loader - Skills 框架核心模块

实现 Claude Skills 本地化版本：
1. 从文件系统加载 SKILL.md 文件
2. 解析 YAML frontmatter 元数据
3. 根据关键词匹配相关 Skills
4. 生成注入到 LLM 的上下文

参考: https://claude.com/blog/skills-explained
"""

import os
import re
import sys
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path

# Windows 编码修复
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass


@dataclass
class Skill:
    """
    单个 Skill 的数据结构
    
    Attributes:
        name: Skill 唯一标识
        description: Skill 描述
        trigger_keywords: 触发关键词列表
        priority: 优先级（0-100，越高越优先）
        content: Skill 正文内容（Markdown）
        file_path: 源文件路径
    """
    name: str
    description: str
    trigger_keywords: List[str] = field(default_factory=list)
    priority: int = 50
    content: str = ""
    file_path: str = ""
    
    def matches(self, text: str) -> bool:
        """检查文本是否匹配此 Skill 的触发关键词"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.trigger_keywords)
    
    def get_context_block(self) -> str:
        """生成注入到 LLM 的上下文块"""
        return f"""
<skill name="{self.name}">
{self.content}
</skill>
"""


class SkillLoader:
    """
    Skills 加载器
    
    职责：
    1. 扫描 skills/ 目录
    2. 加载并解析 SKILL.md 文件
    3. 缓存已加载的 Skills
    """
    
    def __init__(self, skills_dir: Optional[str] = None):
        """
        初始化 SkillLoader
        
        Args:
            skills_dir: Skills 目录路径，默认为项目根目录下的 skills/
        """
        if skills_dir is None:
            # 默认使用项目根目录下的 skills/
            project_root = Path(__file__).parent.parent
            skills_dir = str(project_root / "skills")
        
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._loaded = False
    
    def load_all(self) -> Dict[str, Skill]:
        """
        加载所有 Skills
        
        Returns:
            Dict[str, Skill]: name -> Skill 的映射
        """
        if self._loaded:
            return self._skills
        
        skills_path = Path(self.skills_dir)
        if not skills_path.exists():
            print(f"⚠️ Skills 目录不存在: {self.skills_dir}")
            return {}
        
        # 遍历子目录
        for skill_dir in skills_path.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            
            try:
                skill = self._load_skill_file(str(skill_file))
                if skill:
                    self._skills[skill.name] = skill
                    print(f"   📚 Loaded skill: {skill.name}")
            except Exception as e:
                print(f"   ⚠️ Failed to load {skill_file}: {e}")
        
        self._loaded = True
        return self._skills
    
    def _load_skill_file(self, file_path: str) -> Optional[Skill]:
        """
        加载单个 SKILL.md 文件
        
        Args:
            file_path: SKILL.md 文件路径
            
        Returns:
            Skill 对象，解析失败返回 None
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析 YAML frontmatter
        frontmatter, body = self._parse_frontmatter(content)
        
        if not frontmatter:
            return None
        
        return Skill(
            name=frontmatter.get('name', Path(file_path).parent.name),
            description=frontmatter.get('description', ''),
            trigger_keywords=frontmatter.get('trigger_keywords', []),
            priority=frontmatter.get('priority', 50),
            content=body.strip(),
            file_path=file_path
        )
    
    def _parse_frontmatter(self, content: str) -> tuple:
        """
        解析 YAML frontmatter
        
        格式：
        ---
        key: value
        ---
        正文内容
        
        Returns:
            (frontmatter_dict, body_content)
        """
        # 匹配 frontmatter
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)
        
        if not match:
            return {}, content
        
        yaml_content = match.group(1)
        body = match.group(2)
        
        # 简单解析 YAML（不依赖 pyyaml）
        frontmatter = {}
        for line in yaml_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # 处理列表格式 ["a", "b"]
                if value.startswith('[') and value.endswith(']'):
                    # 简单解析列表
                    items = value[1:-1].split(',')
                    frontmatter[key] = [
                        item.strip().strip('"').strip("'") 
                        for item in items if item.strip()
                    ]
                # 处理数字
                elif value.isdigit():
                    frontmatter[key] = int(value)
                # 处理带引号的字符串
                elif value.startswith('"') and value.endswith('"'):
                    frontmatter[key] = value[1:-1]
                else:
                    frontmatter[key] = value
        
        return frontmatter, body
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定名称的 Skill"""
        self.load_all()
        return self._skills.get(name)
    
    def match_skills(self, text: str, max_skills: int = 3) -> List[Skill]:
        """
        根据文本匹配相关 Skills
        
        Args:
            text: 输入文本（用户查询、任务描述等）
            max_skills: 最多返回的 Skill 数量
            
        Returns:
            匹配的 Skills 列表，按优先级排序
        """
        self.load_all()
        
        matched = [
            skill for skill in self._skills.values()
            if skill.matches(text)
        ]
        
        # 按优先级排序
        matched.sort(key=lambda s: s.priority, reverse=True)
        
        return matched[:max_skills]
    
    def get_all_skills(self) -> List[Skill]:
        """获取所有已加载的 Skills"""
        self.load_all()
        return list(self._skills.values())


# ============ 便捷函数 ============

_global_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """获取全局 SkillLoader 实例"""
    global _global_loader
    if _global_loader is None:
        _global_loader = SkillLoader()
    return _global_loader


def load_relevant_skills(context: str, max_skills: int = 2) -> List[Skill]:
    """
    根据上下文加载相关 Skills
    
    Args:
        context: 上下文文本
        max_skills: 最多返回数量
        
    Returns:
        匹配的 Skills 列表
    """
    loader = get_skill_loader()
    return loader.match_skills(context, max_skills)


def get_skill_context(
    context: str, 
    max_skills: int = 2,
    include_header: bool = True
) -> str:
    """
    生成注入到 LLM 的 Skill 上下文
    
    Args:
        context: 上下文文本
        max_skills: 最多包含的 Skill 数量
        include_header: 是否包含说明头部
        
    Returns:
        格式化的 Skill 上下文字符串
    """
    skills = load_relevant_skills(context, max_skills)
    
    if not skills:
        return ""
    
    parts = []
    
    if include_header:
        parts.append("""
<relevant_skills>
以下是与当前任务相关的专业知识，请参考使用：
""")
    
    for skill in skills:
        parts.append(skill.get_context_block())
    
    if include_header:
        parts.append("</relevant_skills>")
    
    return "\n".join(parts)


# ============ 测试入口 ============

if __name__ == "__main__":
    print("=" * 60)
    print("Skill Loader 测试")
    print("=" * 60)
    
    loader = SkillLoader()
    skills = loader.load_all()
    
    print(f"\n加载了 {len(skills)} 个 Skills:")
    for name, skill in skills.items():
        print(f"  - {name}: {skill.description[:50]}...")
        print(f"    关键词: {skill.trigger_keywords}")
    
    # 测试匹配
    print("\n" + "=" * 60)
    print("测试关键词匹配")
    print("=" * 60)
    
    test_texts = [
        "搜索 B站 AI 视频",
        "找 YouTube 上的编程教程",
        "筛选高质量内容",
        "随便聊聊天气"
    ]
    
    for text in test_texts:
        matched = loader.match_skills(text)
        print(f"\n'{text}':")
        if matched:
            for s in matched:
                print(f"  ✅ {s.name} (priority={s.priority})")
        else:
            print("  ❌ 无匹配")
    
    # 测试上下文生成
    print("\n" + "=" * 60)
    print("测试上下文生成")
    print("=" * 60)
    
    context = get_skill_context("搜索 bilibili AI 教程")
    print(context[:500] + "..." if len(context) > 500 else context)


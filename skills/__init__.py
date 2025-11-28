"""
Skills 框架 - Claude Skills 本地化实现

基于 Claude Skills 架构设计，实现模块化、可复用的专业知识注入机制。

核心概念：
- Skill: 一个专业领域的知识包（Markdown 文件）
- SkillLoader: 加载和管理 Skills
- SkillMatcher: 根据上下文匹配合适的 Skills
"""

from .skill_loader import (
    Skill,
    SkillLoader,
    get_skill_loader,
    load_relevant_skills,
    get_skill_context
)

__all__ = [
    'Skill',
    'SkillLoader', 
    'get_skill_loader',
    'load_relevant_skills',
    'get_skill_context'
]


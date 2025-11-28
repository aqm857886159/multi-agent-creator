"""
🔑 P2方案: 分层关键词策略
当精准搜索失败时，自动降级到更简洁的关键词
"""

from typing import List, Dict, Any
import re


class LayeredKeywordGenerator:
    """
    分层关键词生成器

    策略:
    - Layer 1 (Precise): 精准匹配 - 品牌名/专有名词
    - Layer 2 (Functional): 功能描述 - 核心实体 + 动作词
    - Layer 3 (Generic): 泛化搜索 - 领域词
    """

    def generate_fallback_keywords(
        self,
        original_query: str,
        platform: str = "youtube"  # youtube | bilibili
    ) -> Dict[str, List[str]]:
        """
        为原始查询生成分层降级关键词

        参数:
            original_query: 原始搜索词 (如 "why Manus AI succeeded 2025")
            platform: 平台 (youtube | bilibili)

        返回:
            {
                "layer1_precise": ["Manus AI", "Manus"],
                "layer2_functional": ["Manus AI tutorial", "Manus使用教程"],
                "layer3_generic": ["AI automation tools", "AI代理工具"]
            }
        """
        # 提取核心实体
        core_entities = self._extract_entities(original_query)

        # 检测查询语言
        is_chinese = self._is_chinese(original_query)

        layers = {
            "layer1_precise": [],
            "layer2_functional": [],
            "layer3_generic": []
        }

        if not core_entities:
            # 无法提取实体，返回原始查询
            layers["layer1_precise"] = [original_query]
            return layers

        # Layer 1: 精准匹配
        # 提取专有名词（大写开头或混合大小写）
        proper_nouns = self._extract_proper_nouns(original_query)

        if proper_nouns:
            # 使用专有名词
            layers["layer1_precise"] = [
                proper_nouns[0],  # 单独品牌名
                f'"{proper_nouns[0]}"'  # 加引号强制精准匹配
            ]
        else:
            # 使用第一个核心实体
            layers["layer1_precise"] = [core_entities[0]]

        # Layer 2: 功能描述
        functional_keywords = self._generate_functional_keywords(
            core_entities,
            proper_nouns,
            platform,
            is_chinese
        )
        layers["layer2_functional"] = functional_keywords

        # Layer 3: 泛化搜索
        generic_keywords = self._generate_generic_keywords(
            original_query,
            core_entities,
            platform,
            is_chinese
        )
        layers["layer3_generic"] = generic_keywords

        return layers

    def _extract_entities(self, query: str) -> List[str]:
        """提取核心实体（去除停用词和动作词）"""
        stopwords = {
            '为什么', '怎么', '如何', '什么', '哪个', '的', '了', '是', '和', '为',
            '教程', '指南', '评测', '解析', '动态', '制作', '深度', '保姆级', '最新',
            'why', 'how', 'what', 'when', 'where', 'who', 'the', 'a', 'an',
            'is', 'are', 'was', 'were', 'do', 'does', 'did',
            'tutorial', 'guide', 'review', 'analysis', 'making', 'latest'
        }

        words = re.findall(r'[\w]+', query.lower())
        entities = [w for w in words if w not in stopwords and len(w) > 1]

        return entities

    def _extract_proper_nouns(self, query: str) -> List[str]:
        """提取专有名词（大写开头或混合大小写）"""
        words = re.findall(r'[\w]+', query)

        proper_nouns = []
        for word in words:
            # 检查是否首字母大写或包含大写字母
            if word[0].isupper() or any(c.isupper() for c in word[1:]):
                proper_nouns.append(word)

        return proper_nouns

    def _is_chinese(self, text: str) -> bool:
        """检测文本是否主要是中文"""
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        return len(chinese_chars) > len(text) * 0.3  # 中文字符占比 > 30%

    def _generate_functional_keywords(
        self,
        core_entities: List[str],
        proper_nouns: List[str],
        platform: str,
        is_chinese: bool
    ) -> List[str]:
        """生成功能性关键词（实体 + 动作词）"""
        functional = []

        # 确定主实体 - 优先用专有名词，否则用第一个非动作词的实体
        if proper_nouns:
            main_entity = proper_nouns[0]
        else:
            # 过滤掉明显的动作词/描述词
            filter_words = {'教程', '指南', '评测', '解析', '动态', '制作', 'tutorial', 'guide', 'review', 'making'}
            candidates = [e for e in core_entities if e not in filter_words]
            main_entity = candidates[0] if candidates else "AI"  # 默认用AI

        if platform == "youtube":
            if is_chinese:
                # 中文YouTube搜索（少见，但处理）
                functional = [
                    f"{main_entity} 教程",
                    f"{main_entity} 使用指南",
                    f"{main_entity} 评测"
                ]
            else:
                # 英文YouTube搜索
                functional = [
                    f"{main_entity} tutorial",
                    f"{main_entity} guide",
                    f"{main_entity} review",
                    f"how to use {main_entity}"
                ]

        elif platform == "bilibili":
            if is_chinese:
                # 中文B站搜索（主流）
                functional = [
                    f"{main_entity} 保姆级教程",
                    f"{main_entity} 使用教程",
                    f"{main_entity} 深度评测",
                    f"{main_entity} 实操演示"
                ]
            else:
                # 英文实体，B站用中文描述
                functional = [
                    f"{main_entity} 教程",
                    f"{main_entity} 使用指南",
                    f"{main_entity} 评测"
                ]

        return functional[:3]  # 最多3个

    def _generate_generic_keywords(
        self,
        original_query: str,
        core_entities: List[str],
        platform: str,
        is_chinese: bool
    ) -> List[str]:
        """生成泛化关键词（领域词）"""
        generic = []

        # 检测领域关键词
        domain_map = {
            # 英文
            'ai': 'AI automation tools',
            'manus': 'AI agent platforms',  # Manus是AI Agent工具
            'chatgpt': 'AI chatbot tools',
            'python': 'programming tutorials',
            'react': 'web development frameworks',

            # 中文
            '人工智能': 'AI工具',
            'ai工具': 'AI自动化',
            '编程': '编程教程',
            '前端': 'Web开发'
        }

        # 查找匹配的领域
        for entity in core_entities:
            if entity in domain_map:
                if is_chinese and platform == "bilibili":
                    # 中文泛化
                    generic.append(f"{domain_map[entity]} 最新")
                else:
                    # 英文泛化
                    generic.append(domain_map[entity])
                break

        # 如果没有匹配，生成通用泛化词
        if not generic:
            if is_chinese:
                # 根据核心实体猜测领域
                if any(word in core_entities for word in ['ai', '智能', 'agent']):
                    generic.append("AI工具推荐 最新")
                elif any(word in core_entities for word in ['编程', 'python', 'code']):
                    generic.append("编程教程 最新")
                else:
                    generic.append(f"{core_entities[0]} 相关内容")
            else:
                if any(word in core_entities for word in ['ai', 'artificial', 'intelligence']):
                    generic.append("AI tools 2025")
                elif any(word in core_entities for word in ['code', 'programming', 'python']):
                    generic.append("programming tutorials")
                else:
                    generic.append(f"{core_entities[0]} related")

        return generic[:2]  # 最多2个


# 全局单例
_generator = LayeredKeywordGenerator()


def generate_fallback_keywords(original_query: str, platform: str = "youtube") -> Dict[str, List[str]]:
    """
    便捷函数：生成分层降级关键词

    示例:
        layers = generate_fallback_keywords(
            original_query="why Manus AI succeeded 2025",
            platform="youtube"
        )

        # 结果:
        # {
        #     "layer1_precise": ["Manus"],
        #     "layer2_functional": ["Manus tutorial", "Manus guide"],
        #     "layer3_generic": ["AI agent platforms"]
        # }

        # 使用策略:
        # 1. 先试 layer1_precise[0]
        # 2. 如果失败，试 layer2_functional[0]
        # 3. 最后试 layer3_generic[0]
    """
    return _generator.generate_fallback_keywords(original_query, platform)


if __name__ == "__main__":
    # 测试用例1: Manus AI (英文)
    print("=== 测试用例1: Manus AI ===")
    result1 = generate_fallback_keywords("why Manus AI succeeded 2025", "youtube")
    for layer, keywords in result1.items():
        print(f"{layer}: {keywords}")
    print()

    # 测试用例2: B站中文查询
    print("=== 测试用例2: B站中文 ===")
    result2 = generate_fallback_keywords("Manus AI成功秘诀深度解析 最新", "bilibili")
    for layer, keywords in result2.items():
        print(f"{layer}: {keywords}")
    print()

    # 测试用例3: 通用AI查询
    print("=== 测试用例3: 通用AI ===")
    result3 = generate_fallback_keywords("AI视频制作教程", "bilibili")
    for layer, keywords in result3.items():
        print(f"{layer}: {keywords}")

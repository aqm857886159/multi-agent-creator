"""
🔑 P1方案: 搜索质量验证器
自动检测搜索结果相关性并提供降级建议
"""

from typing import Dict, Any, List, Tuple
import re
from difflib import SequenceMatcher


class SearchValidator:
    """搜索结果质量验证器"""

    def __init__(self, relevance_threshold: float = 0.3):
        """
        参数:
            relevance_threshold: 相关性阈值 (0-1)，低于此值触发警告
        """
        self.relevance_threshold = relevance_threshold

    def validate_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        result_limit: int = 10
    ) -> Dict[str, Any]:
        """
        验证搜索结果质量

        参数:
            query: 搜索关键词
            results: 搜索结果列表 (包含 title 字段)
            result_limit: 检查前N个结果

        返回:
            {
                "is_valid": bool,
                "relevance_score": float (0-1),
                "matched_count": int,
                "total_checked": int,
                "core_entities": List[str],
                "matched_keywords": List[str],
                "issues": List[str],
                "suggestions": List[str]
            }
        """
        if not results:
            return {
                "is_valid": False,
                "relevance_score": 0.0,
                "matched_count": 0,
                "total_checked": 0,
                "core_entities": [],
                "matched_keywords": [],
                "issues": ["搜索返回0个结果"],
                "suggestions": ["扩大搜索范围或调整关键词"]
            }

        # 提取核心实体
        core_entities = self._extract_core_entities(query)

        # 计算相关性
        relevance_score, matched_count, matched_keywords = self._calculate_relevance(
            core_entities,
            results[:result_limit]
        )

        # 判断是否通过
        is_valid = relevance_score >= self.relevance_threshold

        # 生成问题和建议
        issues = []
        suggestions = []

        if not is_valid:
            issues.append(f"仅{matched_count}/{min(result_limit, len(results))}结果包含核心词'{core_entities}'")
            issues.append(f"相关性{relevance_score:.1%} < 阈值{self.relevance_threshold:.0%}")

            # 生成降级建议
            suggestions.extend(self._generate_fallback_suggestions(query, core_entities, matched_keywords))

        return {
            "is_valid": is_valid,
            "relevance_score": relevance_score,
            "matched_count": matched_count,
            "total_checked": min(result_limit, len(results)),
            "core_entities": core_entities,
            "matched_keywords": matched_keywords,
            "issues": issues,
            "suggestions": suggestions
        }

    def _extract_core_entities(self, query: str) -> List[str]:
        """
        从查询中提取核心实体词

        示例:
            "AI公司manus为什么成功" → ["ai", "公司", "manus", "成功"]
            "why Manus AI succeeded" → ["manus", "ai", "succeeded"]
        """
        stopwords = {
            '为什么', '怎么', '如何', '什么', '哪个', '哪些', '的', '了', '是', '在', '有', '和', '与', '或', '吗',
            'why', 'how', 'what', 'when', 'where', 'who', 'which', 'the', 'a', 'an', 'is', 'are', 'was', 'were',
            'be', 'been', 'do', 'does', 'did', 'can', 'could', 'will', 'would', 'should'
        }

        # 分词（按空格和标点）
        words = re.findall(r'[\w]+', query.lower())

        # 过滤停用词和过短词
        core_entities = [w for w in words if w not in stopwords and len(w) > 1]

        return core_entities

    def _calculate_relevance(
        self,
        core_entities: List[str],
        results: List[Dict[str, Any]]
    ) -> Tuple[float, int, List[str]]:
        """
        计算搜索结果与核心实体的相关性

        返回:
            (平均相关性分数, 匹配到的结果数, 匹配到的关键词列表)
        """
        if not core_entities or not results:
            return 0.0, 0, []

        matched_count = 0
        matched_keywords = set()

        for result in results:
            # 提取标题
            title = result.get('title', '').lower()
            if not title:
                continue

            # 检查是否匹配任何核心实体
            has_match = False
            for entity in core_entities:
                # 精确匹配
                if entity in title:
                    has_match = True
                    matched_keywords.add(entity)
                    continue

                # 模糊匹配（处理拼写变体）
                for word in re.findall(r'[\w]+', title):
                    similarity = SequenceMatcher(None, entity, word).ratio()
                    if similarity > 0.85:  # 85%相似度
                        has_match = True
                        matched_keywords.add(entity)
                        break

            if has_match:
                matched_count += 1

        # 计算相关性分数
        relevance_score = matched_count / len(results) if results else 0.0

        return relevance_score, matched_count, list(matched_keywords)

    def _generate_fallback_suggestions(
        self,
        original_query: str,
        core_entities: List[str],
        matched_keywords: List[str]
    ) -> List[str]:
        """
        生成降级搜索建议

        策略:
        1. Layer 1: 只用品牌名/核心实体 (精准匹配)
        2. Layer 2: 核心实体 + 功能描述词
        3. Layer 3: 泛化到领域词
        """
        suggestions = []

        # Layer 1: 精准匹配 - 提取最核心的实体（通常是品牌名/产品名）
        if core_entities:
            # 找到最可能是专有名词的实体（首字母大写或混合大小写）
            original_words = re.findall(r'[\w]+', original_query)
            proper_nouns = [w for w in original_words if w[0].isupper() or any(c.isupper() for c in w[1:])]

            if proper_nouns:
                suggestions.append(f'尝试精准匹配: "{proper_nouns[0]}"')
            else:
                # 否则用第一个实体
                suggestions.append(f'简化为核心词: "{core_entities[0]}"')

        # Layer 2: 功能描述
        if matched_keywords:
            # 如果有匹配关键词，说明可能需要添加功能描述
            functional_words = ['tutorial', 'review', 'guide', '教程', '评测', '使用']
            suggestions.append(f'添加功能词: "{matched_keywords[0]} {functional_words[0]}"')
        elif core_entities:
            suggestions.append(f'添加功能词: "{core_entities[0]} tutorial" 或 "{core_entities[0]} 教程"')

        # Layer 3: 泛化建议
        # 检测领域词（AI, tech, business等）
        domain_keywords = {
            'ai': ['artificial intelligence', 'machine learning', 'AI工具'],
            'tech': ['technology', 'software', '科技'],
            'business': ['startup', 'company', '创业公司']
        }

        for domain, alternatives in domain_keywords.items():
            if domain in core_entities:
                suggestions.append(f'泛化搜索: "{alternatives[0]}"')
                break

        # 如果以上都没有，给出通用建议
        if not suggestions:
            suggestions.append("检查拼写是否正确")
            suggestions.append("该主题可能是新兴/小众话题，数据不足")

        return suggestions


# 全局单例
_validator = SearchValidator(relevance_threshold=0.3)


def validate_search_results(query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    便捷函数：验证搜索结果质量

    示例:
        result = validate_search_results(
            query="Manus AI成功秘诀",
            results=[{"title": "AI工具推荐"}, {"title": "Manus AI教程"}]
        )
        if not result["is_valid"]:
            print(f"搜索质量不佳: {result['issues']}")
            print(f"建议: {result['suggestions']}")
    """
    return _validator.validate_results(query, results)


if __name__ == "__main__":
    # 测试用例1: 高相关性
    print("=== 测试用例1: 高相关性 ===")
    result1 = validate_search_results(
        query="Manus AI tutorial",
        results=[
            {"title": "Manus AI Complete Tutorial"},
            {"title": "How to use Manus AI"},
            {"title": "Manus AI Review"}
        ]
    )
    print(f"结果: {result1['is_valid']}, 相关性: {result1['relevance_score']:.1%}")
    print(f"匹配: {result1['matched_count']}/{result1['total_checked']}")
    print()

    # 测试用例2: 低相关性（搜索漂移）
    print("=== 测试用例2: 低相关性（搜索漂移）===")
    result2 = validate_search_results(
        query="Manus AI成功秘诀",
        results=[
            {"title": "当AI得知自己是AI"},
            {"title": "亚马逊AI布局"},
            {"title": "5个AI生意"},
            {"title": "AI工具推荐"},
            {"title": "Manus AI教程"}  # 仅第5个相关
        ]
    )
    print(f"结果: {result2['is_valid']}, 相关性: {result2['relevance_score']:.1%}")
    print(f"匹配: {result2['matched_count']}/{result2['total_checked']}")
    print(f"问题: {result2['issues']}")
    print(f"建议: {result2['suggestions']}")
    print()

    # 测试用例3: 无结果
    print("=== 测试用例3: 无结果 ===")
    result3 = validate_search_results(
        query="XYZ123 超级新产品",
        results=[]
    )
    print(f"结果: {result3['is_valid']}")
    print(f"问题: {result3['issues']}")
    print(f"建议: {result3['suggestions']}")

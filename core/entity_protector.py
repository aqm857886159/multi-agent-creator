"""
🔑 P3方案: 实体保护机制
防止搜索引擎忽略核心专有名词
"""

from typing import List, Tuple
import re


class EntityProtector:
    """
    实体保护器

    功能:
    1. 识别查询中的专有名词（品牌名、产品名、人名）
    2. 生成保护性查询（使用引号强制精准匹配）
    3. 检测实体是否在结果中保留
    """

    def __init__(self):
        # 已知的专有名词库（可扩展）
        self.known_entities = {
            # AI 产品/公司
            'manus', 'chatgpt', 'claude', 'midjourney', 'stable diffusion',
            'openai', 'anthropic', 'google', 'amazon', 'microsoft',

            # 中文品牌
            '百度', '阿里', '腾讯', '字节', '华为',

            # 编程/技术
            'python', 'javascript', 'react', 'vue', 'nextjs',
            'tensorflow', 'pytorch'
        }

    def identify_entities(self, query: str) -> Tuple[List[str], List[str]]:
        """
        识别查询中的实体

        返回:
            (专有名词列表, 通用词列表)

        示例:
            query = "Manus AI tutorial"
            → (["Manus"], ["ai", "tutorial"])
        """
        words = re.findall(r'[\w]+', query)

        proper_nouns = []
        generic_words = []

        for word in words:
            word_lower = word.lower()

            # 方法1: 检查是否在已知实体库
            if word_lower in self.known_entities:
                proper_nouns.append(word)
                continue

            # 方法2: 检查大小写模式（首字母大写或混合大小写）
            if self._is_proper_noun_by_case(word):
                proper_nouns.append(word)
                continue

            # 方法3: 检查是否是单个大写字母组合（如 AI, ML, NLP）
            if word.isupper() and len(word) >= 2:
                proper_nouns.append(word)
                continue

            # 其他归为通用词
            generic_words.append(word_lower)

        return proper_nouns, generic_words

    def _is_proper_noun_by_case(self, word: str) -> bool:
        """
        通过大小写模式判断是否为专有名词

        规则:
        - 首字母大写 + 后面有小写 (如 Manus, Python)
        - 混合大小写 (如 ChatGPT, OpenAI)
        - 排除全大写缩写 (由上层处理)
        """
        if len(word) < 2:
            return False

        # 首字母大写
        if word[0].isupper():
            # 后面至少有一个小写字母
            if any(c.islower() for c in word[1:]):
                return True

            # 混合大小写 (如 ChatGPT)
            if any(c.isupper() for c in word[1:]):
                return True

        return False

    def generate_protected_query(self, query: str) -> str:
        """
        生成保护性查询（强制保留实体）

        策略:
        1. 识别专有名词
        2. 用双引号包裹专有名词，强制精准匹配
        3. 保留其他通用词

        示例:
            "Manus AI tutorial" → '"Manus" AI tutorial'
            "ChatGPT 使用指南" → '"ChatGPT" 使用指南'
        """
        proper_nouns, generic_words = self.identify_entities(query)

        if not proper_nouns:
            # 没有专有名词，返回原查询
            return query

        # 构建保护性查询
        protected_query = query

        for noun in proper_nouns:
            # 如果已经有引号，跳过
            if f'"{noun}"' in protected_query or f"'{noun}'" in protected_query:
                continue

            # 添加引号（使用正则替换，确保只替换完整单词）
            protected_query = re.sub(
                r'\b' + re.escape(noun) + r'\b',
                f'"{noun}"',
                protected_query,
                flags=re.IGNORECASE
            )

        return protected_query

    def check_entity_preservation(
        self,
        query: str,
        results: List[dict]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        检查搜索结果是否保留了核心实体

        参数:
            query: 原始查询
            results: 搜索结果列表（包含 title 字段）

        返回:
            (是否保留, 保留的实体列表, 丢失的实体列表)

        示例:
            query = "Manus AI tutorial"
            results = [
                {"title": "AI tools tutorial"},  # 丢失了Manus
                {"title": "Best AI platforms"}
            ]
            → (False, [], ["Manus"])
        """
        proper_nouns, _ = self.identify_entities(query)

        if not proper_nouns:
            # 没有专有名词，认为通过
            return True, [], []

        preserved = []
        lost = []

        # 检查每个专有名词是否在至少50%的结果中出现
        for noun in proper_nouns:
            found_count = 0

            for result in results[:10]:  # 只检查前10个结果
                title = result.get('title', '').lower()
                if noun.lower() in title:
                    found_count += 1

            # 如果至少50%的结果包含该实体，认为保留（至少2个结果）
            threshold = max(2, int(len(results[:10]) * 0.5))
            if found_count >= threshold:
                preserved.append(noun)
            else:
                lost.append(noun)

        # 如果有任何核心实体丢失，认为未通过
        is_preserved = len(lost) == 0

        return is_preserved, preserved, lost


# 全局单例
_protector = EntityProtector()


def protect_query(query: str) -> str:
    """
    便捷函数：生成保护性查询

    示例:
        protect_query("Manus AI tutorial")
        → '"Manus" AI tutorial'
    """
    return _protector.generate_protected_query(query)


def check_entity_loss(query: str, results: List[dict]) -> dict:
    """
    便捷函数：检查实体是否丢失

    返回:
        {
            "is_preserved": bool,
            "preserved_entities": List[str],
            "lost_entities": List[str],
            "warning": str (如果有丢失)
        }
    """
    is_preserved, preserved, lost = _protector.check_entity_preservation(query, results)

    result = {
        "is_preserved": is_preserved,
        "preserved_entities": preserved,
        "lost_entities": lost
    }

    if not is_preserved:
        result["warning"] = f"核心实体 '{', '.join(lost)}' 在搜索结果中丢失，建议使用保护性查询"

    return result


if __name__ == "__main__":
    # 测试用例1: 识别实体
    print("=== 测试用例1: 实体识别 ===")
    proper_nouns, generic = _protector.identify_entities("Manus AI tutorial 2025")
    print(f"专有名词: {proper_nouns}")
    print(f"通用词: {generic}")
    print()

    # 测试用例2: 生成保护性查询
    print("=== 测试用例2: 保护性查询 ===")
    protected = protect_query("Manus AI tutorial")
    print(f"原查询: Manus AI tutorial")
    print(f"保护性: {protected}")
    print()

    protected2 = protect_query("ChatGPT使用指南 最新")
    print(f"原查询: ChatGPT使用指南 最新")
    print(f"保护性: {protected2}")
    print()

    # 测试用例3: 检查实体丢失
    print("=== 测试用例3: 实体丢失检查 ===")
    results_good = [
        {"title": "Manus AI Complete Tutorial"},
        {"title": "How to use Manus AI"},
        {"title": "Manus AI Guide"}
    ]
    check_good = check_entity_loss("Manus AI tutorial", results_good)
    print(f"良好结果: {check_good}")
    print()

    results_bad = [
        {"title": "AI tools tutorial"},
        {"title": "Best AI platforms"},
        {"title": "Manus AI guide"}  # 仅1/3包含Manus
    ]

    # 调试：检查Manus的出现次数
    manus_count = sum(1 for r in results_bad if 'manus' in r['title'].lower())
    print(f"调试: Manus出现在 {manus_count}/3 结果中，阈值={max(2, int(3 * 0.5))}")

    check_bad = check_entity_loss("Manus AI tutorial", results_bad)
    print(f"糟糕结果: {check_bad}")

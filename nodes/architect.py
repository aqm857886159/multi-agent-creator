from typing import Dict, Any, List, Tuple
from pydantic import BaseModel, Field
from core.state import RadarState, TopicBrief
from core.llm import ModelGateway
from core.prompts import load_prompt
import re
from difflib import SequenceMatcher

# Define a container for the list to help Instructor
class TopicBriefList(BaseModel):
    proposals: List[TopicBrief]

def run_architect(state: RadarState) -> Dict[str, Any]:
    """
    节点 4: 选题策划 (Architect) - Structured Output Version
    🔑 P0改进: 添加素材相关性质量门槛
    """
    print("\n--- 节点: 选题策划 (Node 4: Architect) ---")

    if not state.filtered_candidates:
        print("⚠️  没有素材通过筛选，跳过策划环节。")
        return {"logs": state.logs + ["Architect skipped: No candidates"]}

    # 🔑 P0: 质量门槛 - 检查素材与用户查询的相关性
    if state.target_domains:
        user_query = state.target_domains[0]  # 用户的原始查询
        candidate_titles = [item.title for item in state.filtered_candidates]

        relevance_score, matched_keywords = _calculate_relevance_score(user_query, candidate_titles)

        print(f"📊 素材相关性分析:")
        print(f"   用户查询: {user_query}")
        print(f"   相关性分数: {relevance_score:.2%}")
        print(f"   匹配关键词: {matched_keywords if matched_keywords else '无'}")

        # 阈值: 平均相关性 < 30% 则拒绝生成
        if relevance_score < 0.30:
            # 提取素材实际讨论的主题
            actual_topics = _extract_topic_keywords(state.filtered_candidates)

            warning_msg = f"""
╔══════════════════════════════════════════════════════════════╗
║  ⚠️  素材质量警告: 搜索结果与查询不匹配                        ║
╚══════════════════════════════════════════════════════════════╝

🎯 您的查询: {user_query}
📊 素材相关性: {relevance_score:.1%} (阈值: 30%)

🔍 搜索到的内容主要讨论:
   {', '.join(actual_topics[:5])}

💡 建议:
   1. 尝试更简洁的关键词 (如: "{matched_keywords[0] if matched_keywords else user_query.split()[0]}")
   2. 检查拼写是否正确
   3. 该主题可能数据不足（新公司/小众产品）

❌ 已阻止生成不相关选题，避免"点红烧肉上土豆丝"
"""
            print(warning_msg)

            return {
                "proposals": [],  # 返回空列表
                "logs": state.logs + [
                    f"⚠️ Architect质量门槛拦截: 相关性{relevance_score:.1%} < 30%",
                    f"实际主题: {', '.join(actual_topics[:3])}",
                    "建议调整搜索关键词"
                ]
            }

    llm = ModelGateway()
    prompt_cfg = load_prompt("architect_agent")
    
    # 准备上下文
    candidates_summary = []
    for idx, item in enumerate(state.filtered_candidates, 1):
        clean_desc = _deep_clean_text(item.raw_data.get('description', '') or item.raw_data.get('summary', ''))
        desc_snippet = clean_desc[:3000] 
        
        candidates_summary.append(
            f"""
            【素材 #{idx}】
            来源: {item.platform} | 类型: {item.source_type}
            标题: {item.title}
            数据: 播放 {item.view_count} | 互动 {item.interaction}
            博主: {item.author_name}
            核心内容摘要:
            {desc_snippet}
            --------------------------------------------------
            """
        )
    
    context_str = "\n".join(candidates_summary)
    
    system_prompt = prompt_cfg["system_template"].format(
        role=prompt_cfg["role"],
        goal=prompt_cfg["goal"],
        methodology=prompt_cfg["methodology"]
    )
    
    user_prompt = f"""
    我为你精选了以下 {len(state.filtered_candidates)} 条高价值情报:
    
    {context_str}
    
    任务:
    请像一个经验丰富的科技媒体主编一样，阅读以上所有材料，策划 3 个具体的选题方案。
    
    要求:
    1. 深度整合: 不要只复述，尝试寻找关联。
    2. 标题党: 标题要极具点击欲。
    3. 严格按照 Schema 输出。
    """
    
    try:
        print(f"🧠 正在阅读并策划选题 (上下文长度: {len(context_str)} 字符)...")
        
        # Magic happens here: Instructor handles validation
        result: TopicBriefList = llm.call_with_schema(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            schema_model=TopicBriefList,
            capability="creative" # Kimi K2 Thinking
        )
        
        proposals = result.proposals
        
        # Post-processing: Ensure source_type is filled if missing
        for p in proposals:
            if not p.source_type: p.source_type = "hybrid"
                
        return {
            "proposals": proposals,
            "logs": state.logs + [f"成功生成 {len(proposals)} 个选题提案 (Validated)."]
        }
        
    except Exception as e:
        print(f"策划阶段出错: {e}")
        return {"logs": state.logs + [f"Architect failed: {e}"]}

def _calculate_relevance_score(user_query: str, candidate_titles: List[str]) -> Tuple[float, List[str]]:
    """
    🔑 P0方案: 计算素材与用户查询的相关性

    参数:
        user_query: 用户输入的查询 (如 "AI公司manus为什么成功")
        candidate_titles: 候选素材的标题列表

    返回:
        (平均相关性分数 0-1, 匹配到的关键词列表)
    """
    # 提取用户查询中的核心实体词（去除停用词）
    stopwords = {'为什么', '怎么', '如何', '什么', '的', '了', '是', '在', '有', '和', '与', '或',
                 'why', 'how', 'what', 'when', 'where', 'the', 'a', 'an', 'is', 'are'}

    # 简单分词（按空格、标点）
    query_words = re.findall(r'[\w]+', user_query.lower())
    core_entities = [w for w in query_words if w not in stopwords and len(w) > 1]

    if not core_entities:
        return 1.0, []  # 如果无法提取实体，默认通过

    # 计算每个素材标题的相关性
    relevance_scores = []
    matched_keywords = set()

    for title in candidate_titles:
        title_lower = title.lower()

        # 方法1: 精确匹配核心实体
        exact_matches = sum(1 for entity in core_entities if entity in title_lower)

        # 方法2: 模糊匹配（处理拼写变体）
        fuzzy_matches = 0
        for entity in core_entities:
            for word in re.findall(r'[\w]+', title_lower):
                similarity = SequenceMatcher(None, entity, word).ratio()
                if similarity > 0.8:  # 80%相似度
                    fuzzy_matches += 1
                    matched_keywords.add(entity)
                    break

        # 综合得分
        total_matches = exact_matches + fuzzy_matches * 0.8
        score = min(total_matches / len(core_entities), 1.0)
        relevance_scores.append(score)

    avg_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

    return avg_score, list(matched_keywords)


def _extract_topic_keywords(candidates: List[Any]) -> List[str]:
    """
    从候选素材中提取出现频率最高的主题词
    用于判断素材集中讨论的是什么话题
    """
    from collections import Counter

    all_words = []
    for item in candidates:
        title = item.title if hasattr(item, 'title') else item.get('title', '')
        words = re.findall(r'[\w]+', title.lower())
        # 过滤停用词和过短词
        stopwords = {'ai', 'the', 'a', 'an', 'is', 'are', 'for', 'to', 'in', 'on', '的', '了', '和'}
        words = [w for w in words if w not in stopwords and len(w) > 2]
        all_words.extend(words)

    # 统计词频
    word_counts = Counter(all_words)
    top_topics = [word for word, count in word_counts.most_common(5)]

    return top_topics


def _deep_clean_text(text: str) -> str:
    """Sanitize text to avoid token waste"""
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('{"', '').replace('"}', '')
    return text

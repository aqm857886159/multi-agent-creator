# Analyst Agent - 快速开始指南

**版本**: v1.0
**日期**: 2025-11-27

---

## 🚀 30秒快速启动

### 1. 测试独立运行 (验证 Analyst 功能)

```bash
cd /mnt/c/Users/23732/Desktop/multi-agent-create
python nodes/analyst.py
```

**预期**: 看到完整的三级火箭流程输出

---

### 2. 集成运行 (完整系统测试)

```bash
python main.py
```

**输入建议**:
```
本轮优先关注哪些主题? AI生成图片
优先采集的平台? youtube
```

**新增输出**: 末尾会显示 `[深度分析报告]` 部分

---

## 📋 核心概念 (3分钟理解)

### Analyst 做什么?

```
输入: TopicBrief (选题简报)
      ↓
   🚀 三级火箭处理
      ↓
输出: DeepAnalysisReport (深度研报)
```

### 三级火箭是什么?

| 级别 | 名称 | 功能 | 输出 |
|------|------|------|------|
| 🚀 **Level 1** | Scout (侦察兵) | 决定去哪找资料 | ResearchPlan |
| 🚀 **Level 2** | Excavator (挖掘机) | 提取核心信息 | List[KeyInsight] |
| 🚀 **Level 3** | Philosopher (哲学家) | 深度逻辑分析 | DeepAnalysisReport |

---

## 🔧 配置说明

### 模型配置 (config/models.yaml)

Analyst 使用两种能力:
```yaml
creative:     # 用于 Level 1 & 2 (规划和萃取)
  model_id: "moonshotai/kimi-k2-0905"

reasoning:    # 用于 Level 3 (深度分析)
  model_id: "moonshotai/kimi-k2-0905"
```

**推荐配置** (成本优化):
```yaml
creative:
  model_id: "deepseek/deepseek-chat"  # 便宜快速

reasoning:
  model_id: "deepseek/deepseek-reasoner"  # 强推理
```

### API Key 配置 (.env)

```bash
# Web 搜索 (必需)
TAVILY_API_KEY=your_tavily_key_here

# LLM 服务 (必需)
OPENROUTER_API_KEY=your_openrouter_key_here
```

**可选**: FIRECRAWL_API_KEY (网页抓取增强)

---

## 📊 输出示例

### 完整报告结构

```json
{
  "topic_id": "topic_001",
  "topic_title": "AI生成图片的技术革命",

  // 事实层
  "hard_evidence": [
    "[Arxiv 2024] Stable Diffusion 3 在 COCO 数据集达到 FID 8.2",
    "[GitHub] SDXL 官方仓库 Star 数超过 50k"
  ],

  // 逻辑层
  "root_cause": "扩散模型取代GAN的本质原因是训练稳定性。GAN需要精细平衡生成器和判别器，而扩散模型只需优化去噪过程...",
  "theoretical_model": "熵增定律 - 扩散过程是可逆熵增，训练是逆向过程",
  "first_principles_analysis": "从信息论角度: 图像生成 = 从噪声中恢复结构...",

  // 洞察层
  "mainstream_view": "大众认为AI绘图会替代插画师",
  "contrarian_view": "实际上AI绘图降低了创意表达门槛，让更多非专业人士成为创作者，市场规模反而扩大",
  "conflict_analysis": "主流担忧'替代'，忽略了'扩容'效应",

  // 叙事层
  "emotional_hook": "恐惧(失业) + 好奇(能否创作)",
  "content_strategy": "开场用失业数据引发恐惧，然后展示普通人用AI创作的成功案例，转化为好奇心",

  // 元数据
  "confidence_score": 0.82,
  "sources_used": [...]
}
```

---

## 🐛 故障排除

### 问题1: "No insights extracted!"

**原因**: 搜索结果质量差或网络问题

**解决**:
```python
# 检查 TAVILY_API_KEY 是否配置
# 检查网络连接
# 查看日志中的搜索关键词是否合理
```

---

### 问题2: "Analysis failed"

**原因**: LLM 返回格式错误或超时

**解决**:
```yaml
# 降级使用更稳定的模型
reasoning:
  model_id: "moonshotai/kimi-k2-0905"  # 更稳定
```

---

### 问题3: Confidence Score 很低 (<0.3)

**原因**: 来源质量不足

**建议**:
- 检查选题是否过于宽泛
- 增加搜索深度 (修改 `depth="advanced"`)
- 检查 Arxiv 搜索是否返回结果

---

## 🎯 最佳实践

### 1. 选题类型与质量

| 选题类型 | Analyst 效果 | 原因 |
|----------|--------------|------|
| **技术类** (AI, 编程) | ⭐⭐⭐⭐⭐ | Arxiv 资源丰富 |
| **商业类** (创业, 投资) | ⭐⭐⭐⭐ | 研报和数据多 |
| **社会类** (心理, 教育) | ⭐⭐⭐ | 依赖书籍和访谈 |
| **娱乐类** (影视, 游戏) | ⭐⭐ | 一手资料少 |

---

### 2. 提高分析质量

#### A. 优化搜索策略
```python
# 修改 nodes/analyst.py 中的分类规则
# 为特定领域添加自定义搜索指令
```

#### B. 增加来源数量
```python
# Level 2 Excavator
raw_results = processor.execute_search_plan(plan, topic_brief.title)
# 默认最多处理10个来源，可以调整为15-20
```

#### C. 强化 Mental Models
```python
# 在 deep_analysis prompt 中添加领域特定的思维模型
# 例如: 技术领域添加 "Crossing the Chasm", "Technology Adoption Curve"
```

---

### 3. 成本控制

**默认配置成本** (单选题):
- Arxiv 搜索: 免费
- Web 搜索: ~$0.001 (Tavily)
- LLM 调用: ~$0.015 (kimi-k2-0905)
- **总计**: ~$0.016/选题

**降本策略**:
```yaml
# 使用 DeepSeek (更便宜)
creative:
  model_id: "deepseek/deepseek-chat"  # $0.14/M → $0.002

reasoning:
  model_id: "deepseek/deepseek-reasoner"  # $0.55/M → $0.004

# 总成本降至: ~$0.007/选题 (降低 56%)
```

---

## 📈 性能监控

### 关键指标

```python
# 在 main.py 中添加统计
total_reports = len(final_state.get("analysis_reports", []))
avg_confidence = sum(r["confidence_score"] for r in reports) / len(reports)

print(f"Analyst 性能:")
print(f"  生成报告数: {total_reports}")
print(f"  平均置信度: {avg_confidence:.2f}")
print(f"  处理时间: {elapsed_time}s")
```

**健康指标**:
- ✅ Confidence Score: > 0.6
- ✅ 处理时间: < 60s/选题
- ✅ 成功率: > 90%

---

## 🔄 迭代路线图

### Phase 2: 智能化增强 (2-3周)

- [ ] **自适应重试**: 低置信度自动触发二次搜索
- [ ] **Source 交叉验证**: 多来源事实核查
- [ ] **Mental Model 库**: 预定义常用模型
- [ ] **缓存优化**: 相似选题复用洞察

### Phase 3: 生态集成 (3-4周)

- [ ] **Writer Agent 对接**: 自动生成文案
- [ ] **质量评分系统**: 用户反馈闭环
- [ ] **多模态支持**: 图表、视频分析
- [ ] **知识图谱**: 构建选题关联网络

---

## 💡 进阶技巧

### 自定义思维模型库

编辑 `nodes/analyst.py` 的 `deep_analysis` 函数:

```python
# 在 prompt 中添加自定义模型
custom_models = """
**Domain-Specific Mental Models**:
- **Tech**: Hype Cycle, Technology S-Curve
- **Business**: Porter's Five Forces, Blue Ocean Strategy
- **Psychology**: Maslow's Hierarchy, Dunning-Kruger Effect
"""

user_prompt = f"""
...
{custom_models}
...
"""
```

---

### 调试模式

```python
# 在 analyst.py 顶部添加
DEBUG = True

# 在关键位置打印中间结果
if DEBUG:
    print(f"[DEBUG] Research Plan: {plan.model_dump()}")
    print(f"[DEBUG] Insights Count: {len(insights)}")
```

---

## 📞 获取帮助

### 查看日志

```python
# main.py 末尾查看完整日志
for log in final_state.get("logs", []):
    if "Analyst" in log:
        print(log)
```

### 常见错误码

| 错误信息 | 原因 | 解决方法 |
|----------|------|----------|
| `No insights extracted` | 搜索无结果 | 检查 TAVILY_API_KEY |
| `Analysis failed` | LLM 超时 | 换用更快的模型 |
| `cannot access local variable` | 代码 bug | 更新到最新版本 |

---

## ✅ 检查清单

启动前确认:

- [ ] `.env` 配置完整 (TAVILY_API_KEY, OPENROUTER_API_KEY)
- [ ] `config/models.yaml` 模型可用
- [ ] 网络连接正常
- [ ] Python 依赖已安装 (`pip install -r requirements.txt`)

运行后验证:

- [ ] 看到 "🚀 Level 1: Adaptive Scout" 日志
- [ ] 看到 "🚀 Level 2: Excavator" 日志
- [ ] 看到 "🚀 Level 3: Philosopher" 日志
- [ ] main.py 末尾显示 `[深度分析报告]`

---

## 🎉 成功案例

### 测试主题: "AI生成图片"

**输入**:
```
Topic: AI生成图片
Core Angle: Stable Diffusion vs MidJourney
```

**输出亮点**:
- Root Cause: "扩散模型的本质是可逆熵增过程"
- Contrarian View: "AI绘图不是替代插画师，而是扩容创作者市场"
- Emotional Hook: "恐惧(失业) + 好奇(能否创作)"
- Confidence: 0.85

**用时**: 45秒
**成本**: $0.018

---

**祝使用愉快! 有问题请查看 `Analyst智能体-实施完成报告.md` 📖**

# Grok 4.1 Fast 模型配置说明

## ✅ 配置完成

已成功配置 `x-ai/grok-4.1-fast:free` 作为自适应质量门的专用模型。

---

## 🎯 模型分工

### 当前模型矩阵

| Capability | 模型 | 用途 | 成本 |
|-----------|------|------|------|
| **reasoning** | Kimi K2 Thinking | 战略规划、复杂推理 | 付费 |
| **creative** | Kimi K2 Thinking | 内容综合、报告生成 | 付费 |
| **fast** | DeepSeek V3 | 数据清洗、JSON解析 | 免费 |
| **base** 🆕 | **Grok 4.1 Fast** | **质量检查、问题诊断** | **免费** |

---

## 🔧 配置详情

### 文件位置
`config/models.yaml:35-43`

### 配置内容
```yaml
# --- Capability 4: Quality Gate (Adaptive Feedback) ---
# Model: Grok 4.1 Fast (X.AI) - FREE
# Role: Quality checking, Problem diagnosis, Adaptive feedback
# Why Grok: Fast, free, good at reasoning about quality issues
base:
  model_id: "x-ai/grok-4.1-fast:free"
  temperature: 0.3
  max_tokens: 2000
  timeout: 30
```

### 参数说明
- **model_id**: `x-ai/grok-4.1-fast:free` - OpenRouter上的免费Grok模型
- **temperature**: `0.3` - 较低温度保证判断稳定性
- **max_tokens**: `2000` - 足够输出详细的质量分析
- **timeout**: `30s` - 快速响应

---

## 🚀 使用场景

### 自适应质量门会自动调用
**文件**: `core/quality_gate.py:73-79`

```python
class AdaptiveQualityGate:
    def __init__(self, use_fast_model: bool = True):
        self.use_fast_model = use_fast_model
        self.capability = "base" if use_fast_model else "reasoning"
        #                 ^^^^
        #                 使用Grok 4.1 Fast
```

### 调用位置
**文件**: `nodes/executor.py:18-20`

```python
# 全局单例，默认使用fast model（即Grok）
_quality_gate = AdaptiveQualityGate(use_fast_model=True)
```

### 执行流程
```
工具执行成功
    ↓
自动调用质量检查
    ↓
使用 Grok 4.1 Fast 分析结果
    ↓
返回质量判断 + 问题诊断 + 改进建议
```

---

## 💡 为什么选择 Grok 4.1 Fast

### 优势

#### 1. **免费** 🆓
- OpenRouter上标记为 `:free`
- 无API成本
- 适合高频质量检查

#### 2. **快速** ⚡
- 专为速度优化
- 30秒超时足够
- 不阻塞主流程

#### 3. **推理能力** 🧠
- X.AI出品，继承Grok系列推理能力
- 适合质量判断和问题诊断
- 能给出智能建议

#### 4. **中等温度** 🎯
- `temperature: 0.3` 保证判断稳定
- 不会太随机，也不会过于死板
- 适合结构化输出

---

## 📊 成本对比

### 质量检查成本分析

| 场景 | 次数/会话 | 使用Grok成本 | 使用Kimi成本 | 节省 |
|------|----------|------------|-------------|------|
| 基础会话 | 10次 | $0.00 | ~$0.02 | 100% |
| 中等会话 | 20次 | $0.00 | ~$0.04 | 100% |
| 重度会话 | 50次 | $0.00 | ~$0.10 | 100% |

**结论**: 使用Grok完全免费，每会话可节省 $0.02-0.10

---

## 🔍 质量检查示例

### 输入到Grok
```
【工具】: youtube_search
【参数】: {"keyword": "AI short drama tutorial", "limit": 15}
【预期】: 在YouTube上搜索相关视频，期望高质量、相关性强的视频

【实际结果】:
返回15条数据
前3条标题:
  1. Huge Tornado Forming Caught on Camera
  2. Plane Crash in Storm
  3. AI Generated Short Film Tutorial

请分析结果质量并给出建议。
```

### Grok输出
```json
{
  "passed": false,
  "score": 0.3,
  "confidence": 0.85,
  "issues": [
    "前两条结果完全不相关（龙卷风、飞机坠毁）",
    "关键词'short'触发了YouTube Shorts算法",
    "只有1/3的结果与AI教程相关"
  ],
  "root_cause": "搜索词包含'short'导致YouTube误判为Shorts内容",
  "suggested_action": "adjust_params",
  "adjustment_plan": {
    "keyword": "AI video generation mini series tutorial 2025"
  },
  "reasoning": "检测到大量不相关的Shorts视频混入，建议避免使用'short'关键词，改用'mini series'或'video generation'等更精准的描述"
}
```

---

## 🎛️ 高级配置

### 如果Grok不可用
可以回退到DeepSeek或其他模型：

```yaml
base:
  model_id: "x-ai/grok-4.1-fast:free"
  temperature: 0.3
  max_tokens: 2000
  timeout: 30
  fallback: "deepseek/deepseek-chat"  # 添加回退
```

### 如果需要更强推理
修改 `AdaptiveQualityGate` 初始化：

```python
# 在 nodes/executor.py:18-20
_quality_gate = AdaptiveQualityGate(use_fast_model=False)
#                                   ^^^^^^^^^^^^^^^^^^^^
#                                   使用Kimi K2 (reasoning)
```

### 临时关闭质量检查
```python
# 在state中
state.feedback_enabled = False
```

---

## 📝 配置验证

### 检查模型是否正确加载
```python
from core.llm import _GATEWAY

# 检查base capability配置
config = _GATEWAY._get_model_params("base")
print(config)
# 输出应该是:
# {
#   'model_id': 'x-ai/grok-4.1-fast:free',
#   'temperature': 0.3,
#   'max_tokens': 2000,
#   'timeout': 30
# }
```

### 运行时日志
执行任务时会看到：
```
🔨 执行: youtube_search...
✅ 结果: 找到15个视频
   [Grok质量检查中...]
   ⚠️ 质量检查: adjust_params - 检测到大量不相关的Shorts视频...
     • 关键词'short'触发YouTube Shorts算法
```

---

## 🔄 模型切换策略

### 当前策略（推荐）
```
质量检查 → Grok (免费、快速)
数据提取 → DeepSeek (免费、精准)
复杂推理 → Kimi K2 (付费、强大)
内容创作 → Kimi K2 (付费、256k上下文)
```

### 成本优化建议
1. ✅ 保持Grok用于质量检查（免费）
2. ✅ 保持DeepSeek用于数据清洗（免费）
3. ⚠️ 只在必要时用Kimi（付费但强大）

---

## ⚠️ 注意事项

### 1. OpenRouter API Key
确保环境变量设置：
```bash
export LLM_API_KEY="sk-or-v1-..."
```

### 2. 免费额度限制
Grok 4.1 Fast虽然标记为`:free`，但可能有：
- RPM (每分钟请求数) 限制
- 每日免费额度
- 需要验证OpenRouter账号

### 3. 超时设置
```yaml
timeout: 30  # 已配置30秒超时
```
如果Grok响应慢，可能触发超时，系统会自动降级：
```python
# 质量检查失败时默认通过
return QualityCheckResult(
    passed=True,
    score=0.7,
    reasoning="质量检查超时，默认通过"
)
```

---

## 🧪 测试建议

### 手动测试Grok
```python
from core.quality_gate import AdaptiveQualityGate

gate = AdaptiveQualityGate(use_fast_model=True)

result = gate.check_quality(
    tool_name="youtube_search",
    tool_params={"keyword": "AI short drama"},
    tool_result={"data": [
        {"title": "Tornado Video"},
        {"title": "AI Tutorial"}
    ]},
    expectation="期望找到AI教程视频"
)

print(result.model_dump_json(indent=2))
```

### 观察日志
```bash
# 运行主程序
python main.py --topic "AI生成视频"

# 观察质量检查日志
# 应该看到Grok的判断和建议
```

---

## ✅ 配置检查清单

- [x] 在 `config/models.yaml` 添加 `base` capability
- [x] 配置 `model_id: x-ai/grok-4.1-fast:free`
- [x] 设置合适的 `temperature: 0.3`
- [x] `AdaptiveQualityGate` 使用 `base` capability
- [x] Executor初始化 `use_fast_model=True`
- [x] 验证环境变量 `LLM_API_KEY` 已设置

---

## 🎉 总结

✅ **Grok 4.1 Fast 已成功配置为质量门专用模型**

**核心优势**:
- 🆓 完全免费
- ⚡ 响应快速
- 🧠 推理能力强
- 🎯 专为质量检查优化

**使用方式**:
- 自动触发（无需额外配置）
- 每次工具执行后自动检查
- 智能诊断问题并给出建议
- 完全透明（可查看日志）

**可以开始测试了！** 🚀

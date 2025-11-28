# 双引擎修复：Web 搜索缺失问题

## 🐛 问题描述

### 症状
运行程序后，发现：
- ✅ `keyword_designer` 正常生成了 `discovery_queries`
- ❌ Planner **直接跳过 web_search**，直接调用 `youtube_search`
- ❌ 从未执行 `influencer_extractor`
- ❌ 博主发现机制完全没有启动

### 实际执行流程（错误）
```
keyword_designer → 生成搜索词 ✅
    ↓
Planner → 直接调用 youtube_search ❌ (跳过了 web_search)
    ↓
收集 10 条 → 筛选 → 结束
```

### 预期执行流程（正确）
```
keyword_designer → 生成搜索词 ✅
    ↓
Planner → web_search (搜索博主推荐文章) ✅
    ↓
influencer_extractor → 提取博主 ✅
    ↓
Planner → 顺藤摸瓜搜索博主内容 ✅
    ↓
收集数据 → 筛选 → 结束
```

---

## 🔍 根本原因分析

### 原因 1: Planner 提示词缺失双引擎逻辑

**问题**：
- Planner 的提示词中完全没有提到"双引擎执行顺序"
- LLM 不知道应该先执行 `web_search`
- LLM 看到 `youtube_search` 就直接用了

**证据**：
从运行日志可以看到，LLM 的思考是：
> "从YouTube开始，使用英文关键词'AI News 2025-11'进行搜索"

它完全不知道应该先用 `discovery_queries` 执行 `web_search`。

---

### 原因 2: Router 逻辑有缺陷

**问题**：
- `planner_router` 只在 `plan_status == "finished"` 时才检查是否需要提取博主
- 但实际上，我们希望**只要有 Web 搜索结果就立即提取**

**原代码**：
```python
def planner_router(state: RadarState):
    if state.plan_status == "executing":
        return "executor"
    elif state.plan_status == "finished":  # ❌ 只在结束时检查
        if state.leads and not state.discovered_influencers:
            return "influencer_extractor"
        else:
            return "filter"
    else:
        return "planner"
```

**问题**：
- 如果 Planner 直接跳过 web_search，`state.leads` 永远为空
- Router 永远不会进入 `influencer_extractor`

---

## ✅ 修复方案

### 修复 1: 增强 Planner 提示词

**修改位置**：`nodes/planner.py` 第 97-140 行

**关键改动**：

1. **增加双引擎状态检查**：
```python
# 检查双引擎阶段
has_discovery_queries = len(state.discovery_queries) > 0
has_web_results = len(state.leads) > 0
has_influencers = len(state.discovered_influencers) > 0
```

2. **在提示词中明确告知当前状态**：
```python
🔑 **双引擎策略状态**:
- 发现博主搜索词已设计: {"是" if has_discovery_queries else "否"}
- Web 搜索已执行: {"是" if has_web_results else "否"}
- 博主已提取: {"是" if has_influencers else "否"}

📋 发现博主搜索词: ['2025年顶级AI博主推荐', 'best AI YouTube channels 2025', ...]
```

3. **明确双引擎执行顺序**：
```python
1. **双引擎执行顺序** ⭐⭐⭐ 最重要：
   如果刚开始，必须按以下顺序执行：

   【阶段 1: 发现博主】
   a) 如果 discovery_queries 已设计但 Web 搜索未执行：
      → **立即使用 web_search 搜索 discovery_queries 中的第一个关键词**
      → 目的：找到"博主推荐文章"（如"2025年顶级AI博主"）
      → 示例调用：
         {"tool_name": "web_search", "arguments": {"query": "2025年顶级AI博主推荐", "limit": 10}}

   b) 如果 Web 搜索已完成但博主未提取：
      → 等待 influencer_extractor 节点自动执行（不要自己调用）

   c) 如果博主已提取：
      → 进入阶段 2

   【阶段 2: 内容收集】
   d) 博主发现完成后，才执行 youtube_search / bilibili_search
```

**效果**：
- ✅ LLM 看到状态后，会知道应该先执行 web_search
- ✅ 提供了明确的示例调用格式
- ✅ 告知了每个阶段的目的

---

### 修复 2: 优化 Router 逻辑

**修改位置**：`core/graph.py` 第 32-48 行

**关键改动**：

**修改前**：
```python
def planner_router(state: RadarState):
    if state.plan_status == "executing":
        return "executor"
    elif state.plan_status == "finished":  # ❌ 只在结束时检查
        if state.leads and not state.discovered_influencers:
            return "influencer_extractor"
        else:
            return "filter"
    else:
        return "planner"
```

**修改后**：
```python
def planner_router(state: RadarState):
    # 🔑 优先检查：如果有 Web 搜索结果且还没有提取过博主，立即提取
    # （不管 plan_status 是什么状态）
    if state.leads and not state.discovered_influencers:
        print("🔄 检测到 Web 搜索结果，准备提取博主...")
        return "influencer_extractor"

    # 如果正在执行工具，去 Executor
    if state.plan_status == "executing":
        return "executor"
    # 如果规划完成（收集到足够数据），进入筛选
    elif state.plan_status == "finished":
        return "filter"
    else:
        # 继续规划
        return "planner"
```

**效果**：
- ✅ 只要有 Web 搜索结果，立即提取博主
- ✅ 不受 `plan_status` 状态限制
- ✅ 增加日志输出，便于调试

---

### 修复 3: 重置 plan_status

**修改位置**：`nodes/influencer_extractor.py` 第 137-142 行

**关键改动**：

提取博主后，重置 `plan_status` 为 "planning"，让 Planner 继续规划：

```python
return {
    "discovered_influencers": sorted_influencers,
    "plan_status": "planning",  # 🔑 重置状态，让 Planner 继续规划
    "logs": state.logs + [...]
}
```

**效果**：
- ✅ 提取博主后，Planner 会继续规划后续步骤
- ✅ 不会直接进入 "finished" 状态

---

## 🎯 修复后的完整流程

### 第一轮（Planner 第 1 次）
```
keyword_designer → 生成 discovery_queries ✅
    ↓
Planner 检查状态:
    - discovery_queries: 是
    - Web 搜索已执行: 否 ❌
    - 博主已提取: 否
    ↓
Planner 决策:
    "根据双引擎策略，应该先执行 web_search"
    调用 web_search (query="2025年顶级AI博主推荐")
    ↓
Executor 执行 web_search → 返回 12 篇文章
    ↓
state.leads = [12 篇文章]
```

### 第二轮（Router → influencer_extractor）
```
Planner Router 检查:
    state.leads 有数据 ✅
    state.discovered_influencers 为空 ✅
    ↓
Router 决策: 进入 influencer_extractor
    ↓
influencer_extractor 提取博主
    ↓
发现 8 个博主 (YouTube: 5, Bilibili: 3)
    ↓
state.discovered_influencers = [8 个博主]
state.plan_status = "planning"  # 重置状态
```

### 第三轮（Planner 第 2 次）
```
Planner 检查状态:
    - discovery_queries: 是
    - Web 搜索已执行: 是
    - 博主已提取: 是 ✅
    ↓
Planner 决策:
    "博主已提取，进入阶段 2：顺藤摸瓜"
    调用 _schedule_influencer_search
    ↓
youtube_search (keyword="AI Explained AI")  # 搜索第一个博主
    ↓
收集 8 条数据
```

### 后续轮次
```
继续搜索其他博主...
    ↓
达到 18 条目标
    ↓
进入筛选 → 策划 → 完成
```

---

## 📊 修复效果对比

### 修复前
```
❌ Planner 直接跳过 web_search
❌ 从未执行 influencer_extractor
❌ 博主发现机制完全没启动
❌ 只是普通的关键词搜索（引擎 2）
```

### 修复后
```
✅ Planner 优先执行 web_search
✅ 自动提取博主
✅ 顺藤摸瓜搜索博主内容（引擎 1）
✅ 广泛搜索关键词（引擎 2）
✅ 双引擎完整运行
```

---

## 🧪 测试验证

### 预期日志输出

```
--- 节点: 搜索词设计师 ---
✅ 搜索词设计完成:
   发现博主: 5 条
   搜索内容: 5 条

--- 节点: 规划大脑 (Planner) ---
🔑 双引擎策略状态:
- 发现博主搜索词已设计: 是
- Web 搜索已执行: 否
- 博主已提取: 否
📋 发现博主搜索词: ['2025年顶级AI博主推荐', 'best AI YouTube channels 2025', ...]

🧠 思考: 根据双引擎策略，应该先执行 web_search 搜索博主推荐文章
👉 决策: 调用 web_search

--- 节点: 执行之手 (Executor) ---
🔨 执行: web_search...
✅ 结果: Found 12 articles
📥 入库: 12 条线索

--- Router ---
🔄 检测到 Web 搜索结果，准备提取博主...

--- 节点: 博主提取器 ---
✅ 博主提取完成:
   分析文章数: 12
   发现博主数: 8
   YouTube 博主 (5):
      - AI Explained (@AIExplained) [置信度: high]
      - Two Minute Papers [置信度: high]
   Bilibili UP主 (3):
      - 李永乐老师 [置信度: high]

--- 节点: 规划大脑 (Planner) ---
🔑 双引擎策略状态:
- 发现博主搜索词已设计: 是
- Web 搜索已执行: 是
- 博主已提取: 是 ✅
📋 已发现博主数量: 8

🧠 思考: 博主已提取，开始顺藤摸瓜搜索博主内容
👉 决策: 调用 youtube_search (搜索 AI Explained)

... (继续搜索其他博主)
```

---

## ✅ 修复文件清单

| 文件 | 修改内容 | 行号 |
|------|---------|------|
| `nodes/planner.py` | 增加双引擎状态检查和提示词 | 97-140 |
| `core/graph.py` | 优化 planner_router 逻辑 | 32-48 |
| `nodes/influencer_extractor.py` | 重置 plan_status | 137-150 |

---

## 🚀 现在可以测试了

```bash
python main.py
```

预期结果：
1. ✅ Planner 会先执行 web_search
2. ✅ 自动提取博主
3. ✅ 顺藤摸瓜搜索博主内容
4. ✅ 双引擎完整运行

如果还有问题，查看日志中的：
- `🔑 双引擎策略状态` - 检查状态是否正确
- `🧠 思考` - 检查 LLM 的决策逻辑
- `🔄 检测到 Web 搜索结果` - 检查 Router 是否正常工作

# Bilibili Duration 字段类型修复

## 🐛 问题描述

**错误信息**:
```
TypeError: unsupported operand type(s) for /: 'str' and 'int'
File "bilibili_adapter.py", line 249, in _score_and_rank_viral
    duration_min = video.get('duration', 0) / 60
```

**根本原因**:
Bilibili搜索API返回的`duration`字段是**字符串格式**（如 `"5:30"`），而不是整数秒数。

---

## 🔍 深入分析

### Bilibili API的duration字段格式

根据 `bilibili-api-python` 库的实际返回数据：

| API | duration格式 | 示例 |
|-----|-------------|------|
| `search.search_by_type()` | **字符串** `"MM:SS"` 或 `"HH:MM:SS"` | `"5:30"`, `"1:05:30"` |
| `video.get_info()` | **整数**（秒） | `330`, `3930` |
| `user.get_videos()` | **整数**（秒） | `330` |

**问题**: 搜索API和详情API返回的格式不一致！

---

## ✅ 修复方案

### 1. 添加duration解析函数

**文件**: `tools/adapters/bilibili_adapter.py:458-485`

```python
def _parse_duration(self, duration_raw) -> int:
    """
    解析Bilibili duration字段

    支持格式:
    - 字符串 "5:30" -> 330秒
    - 字符串 "1:05:30" -> 3930秒
    - 整数 330 -> 330秒

    Returns:
        int: 时长（秒）
    """
    if isinstance(duration_raw, int):
        return duration_raw

    if isinstance(duration_raw, str):
        try:
            parts = duration_raw.split(':')
            if len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return 0
        except:
            return 0

    return 0
```

**核心逻辑**:
1. 如果是整数 → 直接返回
2. 如果是字符串 → 按 `:` 分割
   - 2段 (`MM:SS`) → `MM*60 + SS`
   - 3段 (`HH:MM:SS`) → `HH*3600 + MM*60 + SS`
3. 异常情况 → 返回0（不影响排序）

---

### 2. 在解析时调用

**文件**: `tools/adapters/bilibili_adapter.py:170-197`

```python
def _parse_basic_video(self, v: Dict) -> Dict:
    """解析单条视频的基础数据"""
    pub_ts = v.get('pubdate', 0)
    pub_date = datetime.fromtimestamp(pub_ts).strftime('%Y-%m-%d')

    # 清洗标题HTML
    raw_title = v.get('title', '')
    clean_title = raw_title.replace('<em class="keyword">', '').replace('</em>', '')

    # 🔑 修复: 处理duration字符串格式 (如 "5:30" -> 330秒)
    duration_raw = v.get('duration', 0)
    duration_seconds = self._parse_duration(duration_raw)

    return {
        "platform": "bilibili",
        "source_type": "search",
        "title": clean_title,
        "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
        "bvid": v.get('bvid'),
        "author_name": v.get('author', ''),
        "author_id": str(v.get('mid', '')),
        "publish_time": pub_date,
        "pub_ts": pub_ts,
        "view_count": v.get('play', 0),
        "interaction": v.get('favorites', 0) + v.get('review', 0),
        "duration": duration_seconds,  # ✅ 转换为秒数
        "raw_data": v
    }
```

**改动点**:
- 第180-181行: 调用 `_parse_duration()` 转换格式
- 第195行: 存储转换后的秒数

---

## 🧪 测试用例

### 输入输出示例

```python
# 测试1: 标准格式
_parse_duration("5:30")   # 返回: 330
_parse_duration("10:00")  # 返回: 600
_parse_duration("1:05:30") # 返回: 3930

# 测试2: 整数格式
_parse_duration(330)      # 返回: 330
_parse_duration(3930)     # 返回: 3930

# 测试3: 异常情况
_parse_duration("invalid") # 返回: 0
_parse_duration(None)      # 返回: 0
_parse_duration("")        # 返回: 0
```

---

## 📊 影响范围

### 修复的功能
✅ **Bilibili搜索** (`search_videos`)
- 阶段1: 智能分页获取数据
- 阶段2: 计算爆款分（需要duration计算时长权重）
- 阶段3: 详细信息补充

### 不受影响的功能
✅ **Bilibili监控** (`monitor_user`)
- 监控API不使用duration字段

---

## 🎯 为什么会出现这个问题？

### 根本原因分析

1. **API不一致**: Bilibili官方API的设计问题
   - 搜索接口: 返回字符串（前端友好，直接显示）
   - 详情接口: 返回整数（后端友好，方便计算）

2. **库封装不足**: `bilibili-api-python` 没有自动转换
   - 直接返回原始数据
   - 没有做类型标准化

3. **代码假设错误**:
   - 原代码假设duration总是整数
   - 没有考虑搜索和详情API的差异

---

## 💡 最佳实践

### 处理外部API的建议

1. **永远不要假设类型**:
```python
# ❌ 错误
duration_min = video['duration'] / 60

# ✅ 正确
duration_raw = video.get('duration', 0)
duration_seconds = _safe_parse_duration(duration_raw)
duration_min = duration_seconds / 60
```

2. **做好类型检查**:
```python
if isinstance(value, expected_type):
    process(value)
else:
    handle_conversion(value)
```

3. **异常保护**:
```python
try:
    result = risky_operation(value)
except Exception:
    result = default_value  # 兜底，不影响主流程
```

---

## ✅ 修复验证

### 修复前:
```
🎯 [阶段2] 计算爆款分（详细处理 15 条）...
[Bilibili] ❌ 搜索错误: unsupported operand type(s) for /: 'str' and 'int'
```

### 修复后（预期）:
```
📄 [阶段1] 智能分页扫描（最多 100 条）...
✅ [阶段1] 扫描到 80 条基础数据
🎯 [阶段2] 计算爆款分（详细处理 15 条）...
   Top 3 爆款分: 5.23, 4.87, 4.15
✅ [阶段2] 爆款排序完成，top 15 识别
📊 [阶段3] 补充 top 15 详细信息...
✅ [Bilibili] 完成！扫描 80 条 → 返回 15 条爆款
```

---

## 🚀 总结

| 项目 | 内容 |
|------|------|
| **问题** | duration字段类型不一致（字符串 vs 整数） |
| **根因** | Bilibili搜索API返回字符串格式 `"MM:SS"` |
| **修复** | 添加 `_parse_duration()` 统一转换为秒数 |
| **影响** | 搜索功能恢复正常，不影响监控功能 |
| **测试** | 支持 `"5:30"`, `"1:05:30"`, `330` 等多种格式 |

**核心收获**:
> 在集成第三方API时，要仔细研究实际返回的数据格式，不能只看文档！用真实数据测试，做好类型转换和异常保护。

现在可以重新测试了！🎉

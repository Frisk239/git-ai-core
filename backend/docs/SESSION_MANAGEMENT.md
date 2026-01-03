# 会话管理系统实现文档

## 概述

参考 Cline 的设计理念,实现了一套完整的会话管理系统。核心思想:**任务 = 会话**,每个任务独立存储,支持恢复、搜索、收藏和删除。

## 架构设计

### 核心概念

1. **Task = Session**: 每个任务 ID 就是一个会话 ID
2. **独立存储**: 每个任务/会话独立存储在 `.ai/tasks/{task_id}/` 目录
3. **任务历史**: 维护所有任务的元数据列表在 `.ai/history/task_history.json`

### 文件结构

```
{workspace_path}/
  .ai/
    tasks/                          # 所有任务目录
      {task_id_1}/
        api_conversation_history.json  # API 对话历史
        ui_messages.json               # UI 消息历史
        task_metadata.json             # 任务元数据
      {task_id_2}/
        ...
    history/
      task_history.json              # 任务历史列表
```

## 核心组件

### 1. HistoryItem 数据模型

**文件**: `app/core/context/task_history.py`

```python
@dataclass
class HistoryItem:
    id: str                           # 任务 ID
    task: str                         # 任务描述
    ts: float                         # 创建时间
    last_updated: float               # 最后更新时间
    tokens_in: int                    # 输入 tokens
    tokens_out: int                   # 输出 tokens
    total_cost: float                 # 总成本
    size: int                         # 任务大小
    is_favorited: bool                # 是否收藏
    api_provider: Optional[str]       # AI 提供商
    api_model: Optional[str]          # AI 模型
    repository_path: Optional[str]    # 仓库路径
```

### 2. TaskHistoryManager

**文件**: `app/core/context/task_history.py`

**职责**:
- 管理任务历史列表 (`.ai/history/task_history.json`)
- 添加/更新任务元数据
- 搜索和过滤任务
- 切换收藏状态
- 删除任务

**主要方法**:
- `load_history()`: 加载任务历史
- `save_history()`: 保存任务历史
- `add_or_update_task()`: 添加或更新任务
- `search_tasks()`: 搜索和过滤任务
- `toggle_favorite()`: 切换收藏状态
- `delete_task()`: 删除任务
- `get_stats()`: 获取统计信息

### 3. ConversationHistoryManager

**文件**: `app/core/context/conversation_history.py`

**修改点**:
- 从全局历史改为任务级别存储
- 每个任务独立存储在 `.ai/tasks/{task_id}/` 目录
- 支持删除任务目录

**主要方法**:
- `save_history()`: 保存对话历史
- `load_history()`: 加载对话历史
- `delete_history_files()`: 删除任务目录
- `to_api_messages()`: 转换为 API 消息格式

### 4. API 端点

**文件**: `app/api/routes/sessions.py`

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/sessions/list` | GET | 获取任务列表 |
| `/api/sessions/load/{task_id}` | GET | 加载任务详情 |
| `/api/sessions/toggle-favorite/{task_id}` | POST | 切换收藏状态 |
| `/api/sessions/delete/{task_id}` | POST | 删除任务 |

#### API 参数说明

**GET /api/sessions/list**
```
repository_path: str      # Git 仓库路径 (必需)
search_query: str         # 搜索关键词 (可选)
favorites_only: bool      # 只显示收藏 (默认: False)
sort_by: str              # 排序方式: newest|oldest|cost (默认: newest)
limit: int                # 限制数量 (默认: 100)
```

**响应示例**:
```json
{
  "tasks": [
    {
      "id": "task_001",
      "task": "分析 backend 目录",
      "ts": 1234567890.0,
      "last_updated": 1234567890.0,
      "tokens_in": 100,
      "tokens_out": 200,
      "total_cost": 0.001,
      "is_favorited": false,
      "api_provider": "anthropic",
      "api_model": "claude-3-5-sonnet-20241022"
    }
  ],
  "total_count": 1,
  "total_tokens": 300,
  "total_cost": 0.001
}
```

## 集成到 TaskEngine

**文件**: `app/core/task/engine.py`

**集成点**:

1. **初始化阶段**:
```python
# 初始化任务历史管理器
self.task_history_manager = TaskHistoryManager(
    workspace_path=repository_path
)
await self.task_history_manager.load_history()
```

2. **任务执行阶段**:
```python
# 添加或更新任务到历史列表
task_description = user_input[:100] + "..." if len(user_input) > 100 else user_input
history_item = self.task_history_manager.add_or_update_task(
    task_id=task_id,
    task_description=task_description,
    api_provider=ai_config.get("ai_provider"),
    api_model=ai_config.get("ai_model"),
    repository_path=repository_path,
)
```

3. **任务完成阶段**:
```python
# 更新并保存任务历史统计
history_item = self.task_history_manager.get_task(task_id)
if history_item and self.history_manager:
    stats = self.history_manager.get_stats()
    history_item.tokens_in = stats['total_tokens'] // 2
    history_item.tokens_out = stats['total_tokens'] - history_item.tokens_in
    history_item.size = stats.get('task_dir_size', 0)
await self.task_history_manager.save_history()
```

## 测试

### 单元测试

**文件**: `tests/test_session_management.py`

测试覆盖:
1. 任务生命周期管理
2. 搜索和过滤功能
3. 会话恢复功能
4. 删除和收藏功能
5. 统计功能

运行测试:
```bash
python tests/test_session_management.py
```

### API 测试

**文件**: `tests/test_session_api.py`

测试覆盖:
1. 获取任务列表 API
2. 搜索和过滤 API
3. 加载任务详情 API
4. 切换收藏状态 API
5. 删除任务 API
6. 错误处理

运行测试:
```bash
python tests/test_session_api.py
```

## 使用示例

### 1. 创建新任务

```python
from app.core.context.task_history import TaskHistoryManager
from app.core.context.conversation_history import ConversationHistoryManager

# 初始化管理器
task_manager = TaskHistoryManager(workspace_path="/path/to/repo")
conv_manager = ConversationHistoryManager(
    task_id="task_001",
    workspace_path="/path/to/repo"
)

# 添加到历史
history_item = task_manager.add_or_update_task(
    task_id="task_001",
    task_description="分析代码结构",
    api_provider="anthropic",
    api_model="claude-3-5-sonnet-20241022",
    repository_path="/path/to/repo",
)

# 添加对话
conv_manager.append_message(role="user", content="分析代码结构")
await conv_manager.save_history()
await task_manager.save_history()
```

### 2. 恢复会话

```python
# 加载任务历史
task_manager = TaskHistoryManager(workspace_path="/path/to/repo")
await task_manager.load_history()

# 获取任务
task = task_manager.get_task("task_001")

# 加载对话历史
conv_manager = ConversationHistoryManager(
    task_id="task_001",
    workspace_path="/path/to/repo"
)
await conv_manager.load_history()

# 获取历史消息
messages = conv_manager.to_api_messages()
```

### 3. 搜索任务

```python
task_manager = TaskHistoryManager(workspace_path="/path/to/repo")
await task_manager.load_history()

# 搜索包含 "API" 的任务
results = task_manager.search_tasks(
    query="API",
    favorites_only=False,
    sort_by="newest",
    limit=10,
)

for item in results:
    print(f"{item.id}: {item.task}")
```

## 与 Cline 的对比

### 相似点

1. **Task = Session 概念**: 每个 task_id 就是 session_id
2. **独立存储**: 每个任务独立目录存储
3. **元数据跟踪**: HistoryItem 存储任务元数据和统计
4. **任务历史列表**: 维护所有任务的历史列表

### 差异点

1. **存储格式**: JSON 文件 vs SQLite (Cline 使用 VS Code 的 globalStorage)
2. **目录结构**: `.ai/tasks/{task_id}/` vs `{globalStorage}/tasks/{taskId}/`
3. **API 设计**: RESTful API vs gRPC (Cline 扩展和 webview 通信)

## 下一步

### 前端集成 (待实现)

1. **会话列表页面**:
   - 显示所有任务/会话
   - 支持搜索和过滤
   - 显示任务元数据 (Token 数、成本等)

2. **会话恢复功能**:
   - 点击任务恢复会话
   - 加载历史消息
   - 继续对话

3. **UI 交互**:
   - 收藏/取消收藏
   - 删除任务
   - 排序选项

### 可能的增强功能

1. **会话分组**: 将相关任务组织成会话组
2. **标签系统**: 为任务添加标签
3. **导出功能**: 导出会话历史为 Markdown/JSON
4. **统计图表**: Token 使用、成本趋势可视化

## 总结

本次实现完成了一个完整的会话管理系统,核心特性:

✅ **任务级别存储**: 每个任务独立存储,便于管理和恢复
✅ **任务历史跟踪**: 自动记录所有任务的元数据和统计
✅ **搜索和过滤**: 支持按关键词、收藏状态、排序方式过滤
✅ **完整 API**: 提供增删改查所有操作
✅ **测试覆盖**: 单元测试和 API 测试全覆盖
✅ **Cline 设计**: 参考并遵循 Cline 的设计理念

系统已准备好进行前端集成,为用户提供完整的会话管理体验。

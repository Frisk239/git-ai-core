# Git AI Core 开发计划

## 当前状态

### ✅ 已完成功能

#### 1. 核心工具系统
- [x] ToolCoordinator 工具协调器
- [x] 10个核心工具实现：
  - read_file - 读取文件内容
  - list_files - 列出目录文件
  - git_diff - 查看 Git 差异
  - git_log - 查看提交历史
  - git_status - 查看 Git 状态
  - git_branch - 查看分支信息
  - search_files - 搜索文件内容
  - write_to_file - 写入文件
  - replace_in_file - 替换文件内容
  - list_code_definitions - 列出代码定义

#### 2. 任务执行引擎
- [x] TaskEngine 递归任务循环
- [x] OpenAI Tools API 集成（支持 DeepSeek, OpenAI, Moonshot）
- [x] 流式 SSE 响应支持
- [x] 工具调用状态跟踪（pending → success/error）
- [x] 错误处理和重试机制
- [x] **迭代限制已取消**（max_iterations: 999）

#### 3. 前端集成
- [x] SmartChatPanel 组件
- [x] 实时工具调用显示
- [x] 工具执行状态可视化
- [x] SSE 事件处理

#### 4. 后端 API
- [x] `/api/chat/smart-chat-v2` 端点
- [x] Server-Sent Events 流式响应
- [x] AI 配置实时读取
- [x] 任务执行事件广播

---

## 🚧 下一阶段开发计划

### 📋 优先级 P0（核心功能）

#### 1. 上下文压缩机制（Context Compression）

**参考**: Cline 的上下文管理策略

**目标**: 当对话历史过长时，自动压缩上下文以避免超出模型 token 限制

**实现方案**:

##### 1.1 Token 计数模块
```python
# backend/app/core/context/token_counter.py
class TokenCounter:
    """估算消息的 token 数量"""

    def count_messages(self, messages: List[Dict]) -> int:
        """估算消息列表的总 token 数"""
        # 粗略估算：英文约 4 chars/token，中文约 2 chars/token
        # 更精确方案：使用 tiktoken 库

    def count_tool_result(self, result: Dict) -> int:
        """估算工具结果的 token 数量"""
```

##### 1.2 上下文压缩策略
```python
# backend/app/core/context/compression_strategy.py
class CompressionStrategy:
    """上下文压缩策略"""

    SHOULD_COMPRESS_THRESHOLD = 0.8  # 当使用量超过 80% 时压缩
    MUST_COMPRESS_THRESHOLD = 0.95   # 当使用量超过 95% 时强制压缩

    def should_compress(self, current_tokens: int, max_tokens: int) -> bool:
        """判断是否需要压缩"""

    async def compress_conversation_history(
        self,
        messages: List[Dict],
        max_tokens: int
    ) -> List[Dict]:
        """
        压缩对话历史

        策略：
        1. 保留系统提示词（始终保留）
        2. 保留最近 N 条消息（例如最近 5 轮）
        3. 早期消息只保留摘要（使用 AI 总结）
        4. 压缩过长的工具结果（只保留关键信息）
        """
```

##### 1.3 智能摘要生成
```python
# backend/app/core/context/summary_generator.py
class SummaryGenerator:
    """生成对话摘要"""

    async def summarize_messages(
        self,
        messages: List[Dict],
        ai_config: Dict
    ) -> str:
        """使用 AI 总结对话内容"""

    async def summarize_tool_result(
        self,
        tool_name: str,
        result: Dict,
        ai_config: Dict
    ) -> str:
        """总结工具执行结果"""
```

##### 1.4 集成到 TaskEngine
```python
# backend/app/core/task/engine.py
class TaskEngine:
    async def _build_messages(
        self,
        user_content: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """构建消息列表（带上下文压缩）"""

        # 检查是否需要压缩
        if self.compression_strategy.should_compress(...):
            self.conversation_history = \
                await self.compression_strategy.compress_conversation_history(...)
```

**关键文件**:
- `backend/app/core/context/__init__.py`
- `backend/app/core/context/token_counter.py`
- `backend/app/core/context/compression_strategy.py`
- `backend/app/core/context/summary_generator.py`

**测试场景**:
1. 长对话测试（20+ 轮工具调用）
2. 大文件读取测试（读取多个大文件）
3. Token 计数准确性测试
4. 压缩后任务连续性测试

---

#### 2. 对话历史持久化

**目标**: 保存和恢复用户的对话历史

**实现方案**:

##### 2.1 数据库模型扩展
```python
# backend/app/models/chat_models.py
class Conversation(Base):
    # 已存在...
    repository_path: str  # 新增：关联的仓库路径

class Message(Base):
    # 已存在...
    tool_calls: Optional[str]  # 新增：JSON 格式的工具调用记录
```

##### 2.2 会话管理 API
```python
# backend/app/api/routes/chat.py
@router.post("/smart-chat-v2")
async def smart_chat_v2(request: SmartChatRequest):
    # 如果提供 conversation_id，加载历史
    if request.conversation_id:
        conversation = db.query(Conversation)\
            .filter(Conversation.id == request.conversation_id).first()
        # 加载历史消息到 TaskEngine
```

**关键文件**:
- `backend/app/models/chat_models.py`
- `backend/app/api/routes/chat.py`
- `frontend/src/renderer/components/pages/SmartChatPanel.tsx`

---

### 📋 优先级 P1（重要功能）

#### 3. 多文件编辑支持

**目标**: 支持一次编辑多个文件

**实现方案**:
- 新工具 `batch_edit_files`: 批量编辑多个文件
- 工具参数：`List[FileEdit]`，每个包含 `path`, `search`, `replace`
- 原子性操作：要么全部成功，要么全部回滚

**关键文件**:
- `backend/app/core/tools/batch_edit.py`

---

#### 4. 命令执行工具

**目标**: 允许 AI 执行 shell 命令

**实现方案**:
```python
# backend/app/core/tools/command_executor.py
class CommandExecutorTool(Tool):
    """执行 shell 命令"""

    async def execute(self, context: ToolContext) -> ToolResult:
        # 安全检查：只允许特定命令白名单
        # 超时控制：默认 30 秒
        # 资源限制：内存、CPU
```

**安全措施**:
- 命令白名单（ls, cd, grep, find, cat, 等）
- 沙箱环境（可选）
- 超时控制
- 禁止危险命令（rm, sudo, chmod, 等）

---

#### 5. 代码理解增强

**目标**: 更深入的代码分析能力

**实现方案**:
- 新工具 `analyze_code_dependencies`: 分析代码依赖关系
- 新工具 `find_code_patterns`: 查找代码模式
- 集成 AST 解析（Python, JavaScript/TypeScript）
- 调用图生成

**关键文件**:
- `backend/app/core/tools/code_analyzer.py`

---

### 📋 优先级 P2（增强功能）

#### 6. 实时协作支持

**目标**: 多用户同时访问同一项目

**实现方案**:
- WebSocket 连接管理
- 广播工具执行进度
- 房间隔离（按仓库路径）

---

#### 7. 插件系统

**目标**: 允许用户自定义工具

**实现方案**:
- 插件 API 设计
- 动态工具加载
- 插件配置管理

---

#### 8. 性能优化

**目标**: 提升响应速度

**优化方向**:
- 工具结果缓存
- 并行工具执行
- 增量文件读取
- AI 响应流式输出（已实现 SSE，可优化）

---

## 🔍 技术债务与改进

### 当前问题

1. **Token 计数不精确**: 目前没有准确计算 token，可能导致上下文溢出
2. **工具结果过长**: 大文件读取可能产生超长结果
3. **错误恢复不足**: 某些错误场景下无法自动恢复
4. **测试覆盖不足**: 需要更多单元测试和集成测试

### 改进建议

1. 集成 `tiktoken` 库进行精确 token 计数
2. 实现工具结果自动截断和摘要
3. 增强错误处理和重试逻辑
4. 添加 E2E 测试

---

## 📊 开发里程碑

### Phase 1: 核心稳定 ✅ (已完成)
- 基础工具系统
- 任务执行引擎
- 前后端集成

### Phase 2: 上下文管理 🚧 (进行中)
- [ ] Token 计数模块
- [ ] 上下文压缩策略
- [ ] 智能摘要生成
- [ ] 对话历史持久化

### Phase 3: 功能增强 📅 (计划中)
- [ ] 多文件编辑
- [ ] 命令执行工具
- [ ] 代码理解增强

### Phase 4: 高级特性 🔮 (未来)
- [ ] 实时协作
- [ ] 插件系统
- [ ] 性能优化

---

## 📝 参考资料

- [Cline 项目架构](https://github.com/allude-aiclinicle/cline)
- [OpenAI Tools API 文档](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use 文档](https://docs.anthropic.com/claude/docs/tool-use)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [React SSE 集成](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

---

## 🤝 贡献指南

欢迎贡献！请查看 [CONTRIBUTING.md](./CONTRIBUTING.md) 了解详情。

**当前优先任务**:
1. 实现 Token 计数模块
2. 实现上下文压缩策略
3. 添加对话历史持久化
4. 编写单元测试

---

*最后更新: 2025-12-30*

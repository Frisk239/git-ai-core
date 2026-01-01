# Git AI Core 智能对话系统全面增强计划

基于对 Cline 项目的深入分析，本文档详细说明了如何增强我们的智能对话系统。

## 📊 现状分析

### 当前工具系统 vs Cline 对比

| 功能 | Git AI Core (当前) | Cline | 优先级 | 差距评估 |
|------|-------------------|-------|--------|----------|
| **核心工具数量** | 9个 | 20+ | 🔴 高 | 严重不足 |
| **文件搜索** | 基础正则搜索 | 递归、正则、去重 | 🟡 中 | 功能较弱 |
| **上下文管理** | 无 | 多策略压缩 + 去重 | 🔴 高 | 完全缺失 |
| **文件处理** | 简单读取 | 二进制支持、去重 | 🟡 中 | 功能有限 |
| **对话历史** | 无管理 | 滚动窗口、智能截断 | 🔴 高 | 完全缺失 |
| **工具执行** | 基础执行 | 审批流程、重试、超时 | 🟢 低 | 基本可用 |
| **系统提示词** | 固定模板 | 模块化、多变体 | 🟡 中 | 需要改进 |

### 当前已实现的工具

✅ **已实现工具** (9个):
1. `read_file` - 文件读取
2. `list_files` - 文件列表
3. `write_to_file` - 写入文件
4. `replace_in_file` - 替换文件内容
5. `search_files` - 搜索文件内容
6. `git_diff` - Git diff
7. `git_log` - Git log
8. `git_status` - Git status
9. `git_branch` - Git branch
10. `list_code_definitions` - 列出代码定义
11. `use_mcp_tool` - 调用MCP工具
12. `access_mcp_resource` - 访问MCP资源
13. `list_mcp_servers` - 列出MCP服务器

⚠️ **缺失的核心工具** (参考Cline):
1. ❌ `execute_command` - 执行shell命令 (重要!)
2. ❌ `ask_followup_question` - 向用户提问
3. ❌ `attempt_completion` - 任务完成确认
4. ❌ `apply_patch` - 应用补丁
5. ❌ `list_code_definition_names` - 列出代码定义 (与已有功能重复)
6. ❌ `web_search` - 网络搜索
7. ❌ `web_fetch` - 获取网页内容
8. ❌ `browser_action` - 浏览器自动化

## 🚀 分阶段增强计划

### 阶段 1: 紧急修复 ✅ (已完成)

**问题**: 文件搜索路径验证过于严格，AI 传入 `path="/"` 时报错

**修复内容**:
- ✅ 修复 `search_files` 工具的路径验证逻辑
- ✅ 修复 `list_files` 工具的路径验证逻辑
- ✅ 支持 `"/"`, `"."`, `""` 等多种表示根目录的方式

**代码变更**:
```python
# 标准化路径输入
if not search_path or search_path in ["/", ".", "./"]:
    full_search_path = repo_path
else:
    normalized_path = search_path.lstrip("/").lstrip("./")
    full_search_path = os.path.join(repo_path, normalized_path)
```

### 阶段 2: 添加缺失的核心工具 (高优先级)

#### 2.1 添加 `execute_command` 工具 🔴

**重要性**: ⭐⭐⭐⭐⭐ (最高)

**功能**: 允许AI执行shell命令来安装依赖、运行测试、构建项目等

**实现要点**:
- 沙箱执行环境
- 超时控制
- 输出流式传输
- 错误处理
- 命令白名单/黑名单

**文件**: `backend/app/core/tools/handlers/command_handler.py`

#### 2.2 添加 `ask_followup_question` 工具 🔴

**重要性**: ⭐⭐⭐⭐⭐

**功能**: AI可以主动向用户提问以获取更多信息

**实现要点**:
- 阻塞式等待用户响应
- 支持多种问题类型 (选择、确认、输入)
- 问题历史记录

**文件**: `backend/app/core/tools/handlers/interaction_handler.py`

#### 2.3 添加 `attempt_completion` 工具 🔴

**重要性**: ⭐⭐⭐⭐

**功能**: AI完成任务后总结并确认结果

**实现要点**:
- 任务总结格式化
- 用户确认机制
- 完成历史记录

**文件**: `backend/app/core/tools/handlers/task_handler.py`

#### 2.4 添加 `web_search` 和 `web_fetch` 工具 🟡

**重要性**: ⭐⭐⭐

**功能**: 允许AI搜索网络和获取网页内容

**实现要点**:
- 集成搜索API (Google/Bing/DuckDuckGo)
- HTML内容提取
- 去除广告和无关内容
- Markdown转换

**文件**:
- `backend/app/core/tools/handlers/web_search_handler.py`
- `backend/app/core/tools/handlers/web_fetch_handler.py`

### 阶段 3: 实现上下文管理系统 (高优先级)

#### 3.1 上下文压缩机制 🔴

**重要性**: ⭐⭐⭐⭐⭐

**参考**: Cline 的 `ContextManager.ts`

**实现策略**:

1. **文件读取去重**:
   - 跟踪已读取的文件
   - 重复读取时返回 `[Previous file content shown above]`
   - 保留最新读取结果

2. **工具调用结果优化**:
   - 保留最新的 `tool_result`
   - 压缩中间结果
   - 保留关键错误信息

3. **对话历史截断**:
   - 保留首尾消息
   - 滚动窗口机制
   - Token计数触发

**文件**: `backend/app/core/context_manager.py`

**核心接口**:
```python
class ContextManager:
    def should_compact_context(self, messages: List[Message]) -> bool:
        """检查是否需要压缩上下文"""
        pass

    def compact_context(self, messages: List[Message]) -> List[Message]:
        """压缩上下文"""
        pass

    def optimize_tool_results(self, tool_results: List[ToolResult]) -> List[ToolResult]:
        """优化工具调用结果"""
        pass

    def deduplicate_file_reads(self, messages: List[Message]) -> List[Message]:
        """去重文件读取"""
        pass
```

#### 3.2 对话历史管理 🔴

**重要性**: ⭐⭐⭐⭐⭐

**实现要点**:

1. **消息历史存储**:
   - SQLite持久化存储
   - 会话ID管理
   - 时间戳记录

2. **滚动窗口**:
   - 保留最近N条消息
   - 保留关键系统消息
   - Token限制

3. **智能截断**:
   - 保留首尾对话
   - 移除中间冗余内容
   - 保留工具调用配对

**文件**: `backend/app/core/conversation_history.py`

### 阶段 4: 优化文件处理能力 (中优先级)

#### 4.1 大文件分块处理 🟡

**重要性**: ⭐⭐⭐

**参考**: Cline 的文件读取限制策略

**实现要点**:
- 检测文件大小
- 超过阈值时分块读取
- 保留文件开头和结尾
- 中间部分使用摘要

**配置**:
```python
MAX_FILE_SIZE = 100_000  # 100KB
CHUNK_SIZE = 10_000      # 10KB
```

#### 4.2 二进制文件处理 🟡

**重要性**: ⭐⭐⭐

**实现要点**:
- 自动检测二进制文件
- PDF文本提取
- DOCX文本提取
- 图片元数据提取

**依赖**:
- `PyPDF2` - PDF处理
- `python-docx` - DOCX处理
- `Pillow` - 图片元数据

#### 4.3 文件缓存机制 🟡

**重要性**: ⭐⭐⭐

**实现要点**:
- LRU缓存策略
- 文件修改时间检测
- 缓存失效策略
- 内存使用限制

**文件**: `backend/app/core/file_cache.py`

### 阶段 5: 改进系统提示词构建 (中优先级)

#### 5.1 模块化提示词架构 🟡

**重要性**: ⭐⭐⭐

**参考**: Cline 的 `src/core/prompts/system-prompt/` 架构

**目录结构**:
```
backend/app/core/prompts/
├── components/          # 提示词组件
│   ├── __init__.py
│   ├── agent_role.py    # AI角色定义
│   ├── rules.py         # 使用规则
│   ├── capabilities.py  # 能力描述
│   ├── tool_use/        # 工具使用指南
│   │   ├── __init__.py
│   │   ├── file_tools.py
│   │   ├── search_tools.py
│   │   └── mcp_tools.py
│   └── best_practices.py # 最佳实践
├── variants/            # 模型特定变体
│   ├── __init__.py
│   ├── generic.py       # 通用模型
│   ├── claude.py        # Claude特定
│   ├── gpt.py           # GPT特定
│   └── glm.py           # GLM特定
├── registry.py          # 注册表
└── builder.py           # 构建器
```

**核心接口**:
```python
class PromptBuilder:
    def build_system_prompt(
        self,
        model_family: str,
        available_tools: List[ToolSpec],
        project_context: Dict
    ) -> str:
        """构建系统提示词"""
        pass

    def get_components(self, variant: str) -> List[PromptComponent]:
        """获取提示词组件"""
        pass
```

#### 5.2 动态工具说明 🟡

**重要性**: ⭐⭐⭐

**实现要点**:
- 根据可用工具动态生成工具说明
- MCP服务器信息动态包含
- 工具使用示例动态生成

### 阶段 6: 工具执行增强 (低优先级)

#### 6.1 工具执行审批流程 🟢

**重要性**: ⭐⭐

**参考**: Cline 的审批机制

**实现要点**:
- 危险操作需要用户确认
- 自动审批白名单
- 审批历史记录

**危险操作类型**:
- 删除文件
- 执行命令
- 覆写文件
- 网络访问

#### 6.2 工具超时和重试 🟢

**重要性**: ⭐⭐

**实现要点**:
- 每个工具设置默认超时
- 超时后自动重试
- 指数退避策略
- 重试次数限制

#### 6.3 工具结果格式化 🟢

**重要性**: ⭐⭐

**实现要点**:
- 统一的结果格式
- 错误信息标准化
- 成功/失败标识
- 元数据包含

## 📝 实施时间表

### Week 1-2: 阶段1-2 (紧急修复 + 核心工具)
- ✅ Day 1: 修复路径验证问题
- Day 2-3: 实现 `execute_command` 工具
- Day 4-5: 实现 `ask_followup_question` 和 `attempt_completion`
- Day 6-7: 实现 `web_search` 和 `web_fetch`
- Day 8-10: 测试和优化新工具

### Week 3-4: 阶段3 (上下文管理)
- Day 11-14: 实现上下文压缩机制
- Day 15-18: 实现对话历史管理
- Day 19-21: 测试和优化

### Week 5: 阶段4 (文件处理优化)
- Day 22-24: 实现大文件分块处理
- Day 25-26: 实现二进制文件处理
- Day 27-28: 实现文件缓存

### Week 6: 阶段5-6 (提示词和工具增强)
- Day 29-31: 重构系统提示词架构
- Day 32-35: 实现工具审批流程
- Day 36-42: 全面测试和文档编写

## 🎯 成功指标

### 功能完整性
- ✅ 支持Cline拥有的80%核心工具
- ✅ 上下文窗口压缩率达到60%
- ✅ 文件搜索准确率达到95%

### 性能指标
- ✅ 工具平均响应时间 < 2秒
- ✅ 上下文压缩时间 < 500ms
- ✅ 缓存命中率 > 70%

### 用户体验
- ✅ 工具使用错误率 < 5%
- ✅ 对话连贯性评分 > 8/10
- ✅ 任务完成率 > 90%

## 📚 参考资料

### Cline 项目关键文件
1. **工具系统**: `src/core/task/tools/`
2. **上下文管理**: `src/core/context/`
3. **系统提示词**: `src/core/prompts/system-prompt/`
4. **MCP集成**: `src/core/mcp/`

### 设计模式
1. **Handler模式**: 工具处理器统一接口
2. **Coordinator模式**: 工具协调和执行
3. **Builder模式**: 提示词构建
4. **Strategy模式**: 压缩策略选择

## 🔄 持续改进

### 后续优化方向
1. **符号索引**: 实现代码定义的符号级别索引
2. **语义搜索**: 基于embedding的代码语义搜索
3. **多模态**: 支持图片、视频等多模态内容
4. **分布式**: 支持多机器并行处理大型项目
5. **流式响应**: 实现流式token输出

---

**文档版本**: v1.0
**最后更新**: 2025-01-01
**维护者**: Git AI Core Team

# 智能对话 V2 集成指南

## 概述

新的智能对话系统集成了工具调用功能,支持 AI 自主调用工具来完成任务。

## 后端集成

### 1. 新 API 端点

**路径**: `/api/chat/smart-chat-v2`

**方法**: POST

**请求体**:
```typescript
{
  message: string,
  repository_path: string,
  conversation_id?: number
}
```

**响应**: Server-Sent Events (SSE) 流式响应

### 2. 事件类型

```typescript
// API 请求开始
{
  type: "api_request_started",
  iteration: number,
  message_count: number
}

// AI 响应
{
  type: "api_response",
  content: string,
  iteration: number
}

// 检测到工具调用
{
  type: "tool_calls_detected",
  tool_calls: Array<{
    name: string,
    parameters: any
  }>,
  iteration: number
}

// 工具执行开始
{
  type: "tool_execution_started",
  tool_name: string,
  iteration: number
}

// 工具执行完成
{
  type: "tool_execution_completed",
  tool_name: string,
  result: {
    success: boolean,
    data?: any,
    error?: string
  },
  iteration: number
}

// 任务完成
{
  type: "completion",
  content: string,
  iteration: number
}

// 错误
{
  type: "error",
  message: string,
  iteration?: number
}
```

## 前端集成

### 1. API 服务

已添加 `smartChatV2` 方法到 `src/renderer/services/api.ts`:

```typescript
async smartChatV2(
  message: string,
  projectPath: string,
  onEvent?: (event: any) => void
): Promise<void>
```

### 2. SmartChatPanel 更新

需要更新 `sendMessage` 函数:

```typescript
const sendMessage = async () => {
  if (!inputMessage.trim() || isLoading || !isInitialized) return;

  const userMessage: Message = {
    id: `user-${Date.now()}`,
    role: "user",
    content: inputMessage,
    timestamp: new Date(),
  };

  setMessages((prev) => [...prev, userMessage]);
  setInputMessage("");
  setIsLoading(true);

  // 创建一个临时的助手消息用于显示进度
  const tempAssistantId = `assistant-${Date.now()}`;
  const assistantMessage: Message = {
    id: tempAssistantId,
    role: "assistant",
    content: "",
    timestamp: new Date(),
    toolCalls: [],
  };

  setMessages((prev) => [...prev, assistantMessage]);

  try {
    await api.smartChatV2(inputMessage, projectPath, (event) => {
      // 处理不同类型的事件
      switch (event.type) {
        case "api_request_started":
          console.log(`[迭代 ${event.iteration}] API 请求开始`);
          break;

        case "api_response":
          // 更新助手消息内容
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === tempAssistantId
                ? { ...msg, content: event.content || "" }
                : msg
            )
          );
          break;

        case "tool_calls_detected":
          // 显示工具调用
          const toolCalls: ToolCall[] = event.tool_calls.map(
            (call: any, index: number) => ({
              id: `tool-${Date.now()}-${index}`,
              toolName: call.name,
              arguments: call.parameters,
              status: "pending" as const,
            })
          );

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === tempAssistantId
                ? { ...msg, toolCalls: [...(msg.toolCalls || []), ...toolCalls] }
                : msg
            )
          );
          break;

        case "tool_execution_started":
          // 更新工具状态为执行中
          setMessages((prev) =>
            prev.map((msg) => ({
              ...msg,
              toolCalls: msg.toolCalls?.map((tc) =>
                tc.toolName === event.tool_name
                  ? { ...tc, status: "pending" }
                  : tc
              ),
            }))
          );
          break;

        case "tool_execution_completed":
          // 更新工具状态和结果
          setMessages((prev) =>
            prev.map((msg) => ({
              ...msg,
              toolCalls: msg.toolCalls?.map((tc) =>
                tc.toolName === event.tool_name
                  ? {
                      ...tc,
                      status: event.result.success ? "success" : "error",
                      result: event.result,
                    }
                  : tc
              ),
            }))
          );
          break;

        case "completion":
          // 任务完成，显示最终答案
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === tempAssistantId
                ? { ...msg, content: event.content }
                : msg
            )
          );
          break;

        case "error":
          toast.error(`错误: ${event.message}`);
          break;
      }
    });

    setIsLoading(false);
  } catch (error) {
    console.error("发送消息失败:", error);
    toast.error("发送消息失败");

    const errorMessage: Message = {
      id: `error-${Date.now()}`,
      role: "system",
      content: "❌ 发送消息失败，请检查网络连接",
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, errorMessage]);
    setIsLoading(false);
  }
};
```

## 关键特性

1. **实时进度显示**: 可以看到 AI 正在调用哪些工具
2. **工具状态跟踪**: 显示每个工具的执行状态(处理中/成功/失败)
3. **流式响应**: 逐步返回结果,不需要等待整个任务完成
4. **多轮对话**: AI 可以根据工具结果决定下一步操作

## 使用示例

### 示例 1: 查看项目结构

**用户输入**: "请帮我分析这个项目的结构"

**AI 会自动调用**:
1. `git_status` - 查看 Git 状态
2. `list_files` - 列出根目录文件
3. `read_file` - 读取 README 或配置文件
4. 最终给出项目结构分析

### 示例 2: 代码分析

**用户输入**: "分析 backend/app/core 目录的代码"

**AI 会自动调用**:
1. `list_files` - 列出目录文件
2. `list_code_definitions` - 分析代码定义
3. `read_file` - 读取关键文件
4. 给出代码分析报告

## 测试

启动后端和前端后,在智能对话面板中输入问题,应该能看到:

1. ✅ 工具调用的实时显示
2. ✅ 工具执行状态的变化(处理中 → 成功/失败)
3. ✅ AI 的最终回复
4. ✅ 多轮对话的能力

## 注意事项

1. **AI 配置**: 确保 AI 配置正确(API Key, Base URL 等)
2. **网络连接**: SSE 需要保持连接,确保网络稳定
3. **错误处理**: 已实现基本的错误处理和提示
4. **性能**: 对于复杂任务,可能需要较长时间,请耐心等待

## 下一步改进

- [ ] 添加对话历史持久化
- [ ] 支持中断和重试
- [ ] 添加更多工具(执行命令、浏览器操作等)
- [ ] 优化工具调用结果的显示格式
- [ ] 添加对话导出功能

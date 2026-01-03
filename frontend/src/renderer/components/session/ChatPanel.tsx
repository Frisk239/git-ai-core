/**
 * 新的聊天面板组件
 *
 * 完全重写 SmartChatPanel,集成会话管理功能
 * 参考 Cline 的设计模式
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-hot-toast';
import {
  PaperAirplaneIcon,
  ArrowPathIcon,
  ClockIcon,
  SparklesIcon,
  PlusIcon,
} from '@heroicons/react/24/outline';
import { api } from '../../services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { TaskHistoryView } from './TaskHistoryView';
import { TaskDetail } from '../../../types/session';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  tool_calls?: ToolCall[];
}

interface ToolCall {
  id: string;
  tool_name: string;
  parameters: any;
  result?: any;
  status: 'pending' | 'success' | 'error';
  reason?: string;
}

interface ChatPanelProps {
  projectPath: string;
  fileTree?: any;
  onFilePreview?: (filePath: string, content: string) => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  projectPath,
  fileTree,
  onFilePreview,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 新建对话
  const handleNewChat = () => {
    setMessages([]);
    setCurrentTaskId(null);
    toast.success('已创建新对话');
  };

  // 加载历史任务
  const handleLoadTask = async (taskId: string) => {
    try {
      const taskDetail: TaskDetail = await api.loadTask(taskId, projectPath);

      // 🔥 转换消息格式，包括工具调用
      const loadedMessages: Message[] = taskDetail.messages.map((msg: any, index: number) => {
        // 转换工具调用格式
        const toolCalls: ToolCall[] = (msg.tool_calls || []).map((tc: any) => ({
          id: tc.id || `loaded-tool-${index}`,
          tool_name: tc.name,
          parameters: tc.parameters,
          result: tc.result,
          status: tc.result?.success ? 'success' : tc.result?.success === false ? 'error' : 'pending',
        }));

        return {
          id: `loaded-${index}`,
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp || Date.now()),
          tool_calls: toolCalls,
        };
      });

      setMessages(loadedMessages);
      setCurrentTaskId(taskId);
      setShowHistory(false);

      toast.success('任务已加载');
    } catch (error) {
      console.error('加载任务失败:', error);
      toast.error('加载任务失败');
    }
  };

  // 发送消息
  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageToSend = inputMessage;
    setInputMessage('');
    setIsLoading(true);

    try {
      await api.smartChatV2(
        messageToSend,
        projectPath,
        currentTaskId ?? undefined,  // 传递当前任务 ID 以支持记忆功能
        (event: any) => {
          // 处理任务开始事件(保存 task_id)
          if (event.type === 'task_started') {
            setCurrentTaskId(event.task_id);
            console.log(`任务 ${event.is_new_task ? '创建' : '继续'}: ${event.task_id}`);
            return;
          }

          switch (event.type) {
          case 'api_response':
            // 🔥 关键修改：每次 API 响应都创建新的独立消息块（参考 Cline）
            if (event.content) {
              const assistantMessage: Message = {
                id: `assistant-${Date.now()}`,
                role: 'assistant',
                content: event.content,
                timestamp: new Date(),
                tool_calls: [],
              };
              setMessages((prev) => [...prev, assistantMessage]);
            }
            break;

          case 'tool_calls_detected':
            // 🔥 每个工具调用也创建独立的消息块
            const tool_calls: ToolCall[] = event.tool_calls.map(
              (call: any, index: number) => ({
                id: `tool-${Date.now()}-${index}`,
                tool_name: call.name,
                parameters: call.parameters,
                status: 'pending' as const,
              })
            );

            // 为每个工具调用创建独立消息（参考 Cline）
            tool_calls.forEach((tool_call) => {
              const toolMessage: Message = {
                id: `tool-msg-${tool_call.id}`,
                role: 'assistant',
                content: '',  // 工具调用消息没有文本内容
                timestamp: new Date(),
                tool_calls: [tool_call],
              };
              setMessages((prev) => [...prev, toolMessage]);
            });
            break;

          case 'tool_execution_completed':
            // 🔥 更新对应工具调用消息的状态
            setMessages((prev) =>
              prev.map((msg) => {
                // 检查这个消息是否包含该工具调用
                const targetToolCall = msg.tool_calls?.find(
                  tc => tc.tool_name === event.tool_name
                );

                if (targetToolCall) {
                  // 更新工具调用状态
                  return {
                    ...msg,
                    tool_calls: msg.tool_calls?.map((tc) =>
                      tc.tool_name === event.tool_name
                        ? {
                            ...tc,
                            status: event.result.success ? 'success' : 'error',
                            result: event.result,
                          }
                        : tc
                    ),
                  };
                }
                return msg;
              })
            );
            break;

          case 'completion':
            // ✅ completion 事件只标记任务结束，不再显示内容（内容已经在 api_response 中显示过了）
            setIsLoading(false);
            break;

          case 'error':
            toast.error(`错误: ${event.message}`);
            setIsLoading(false);
            break;
        }
        }
      );
    } catch (error) {
      console.error('发送消息失败:', error);
      toast.error('发送消息失败');
      setIsLoading(false);
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // 自动调整文本框高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputMessage]);

  // 生成工具调用描述（参考 Cline）
  const getToolDescription = (tool_call: ToolCall): string => {
    const toolName = tool_call.tool_name;
    const params = tool_call.parameters;

    switch (toolName) {
      case 'read_file':
        return `读取文件: ${params.file_path || ''}`;
      case 'write_to_file':
        return `写入文件: ${params.file_path || ''}`;
      case 'modify_file':
        return `修改文件: ${params.file_path || ''}`;
      case 'list_directory':
        const recursive = params.recursive ? ' (递归)' : '';
        return `列出目录: ${params.path || ''}${recursive}`;
      case 'search_files':
        return `搜索文件: ${params.path || ''} (模式: ${params.pattern || ''})`;
      case 'list_code_definitions':
        return `列出代码定义: ${params.file_path || ''}`;
      case 'git_status':
        return '查看 Git 状态';
      case 'git_diff':
        return `查看 Git 差异: ${params.file_path || ''}`;
      case 'git_log':
        return '查看 Git 提交历史';
      case 'attempt_completion':
        return '完成任务';
      default:
        return `${toolName}`;
    }
  };

  // 渲染工具调用（参考 Cline 的多消息块显示）
  const renderToolCalls = (tool_calls: ToolCall[]) => {
    return (
      <div className="mt-3 space-y-2">
        {tool_calls.map((tool_call) => {
          const toolDesc = getToolDescription(tool_call);
          const isSuccess = tool_call.status === 'success';
          const isError = tool_call.status === 'error';
          const isPending = tool_call.status === 'pending';

          return (
            <div
              key={tool_call.id}
              className="border-l-4 ${
                isSuccess ? 'border-green-500' : isError ? 'border-red-500' : 'border-blue-500'
              } bg-gray-50 rounded-r-lg p-3"
            >
              {/* 工具名称和状态 */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-700">
                    {toolDesc}
                  </span>
                  {isSuccess && (
                    <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full font-medium">
                      ✓ 成功
                    </span>
                  )}
                  {isError && (
                    <span className="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full font-medium">
                      ✗ 失败
                    </span>
                  )}
                  {isPending && (
                    <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full flex items-center">
                      <ArrowPathIcon className="w-3 h-3 animate-spin mr-1" />
                      处理中
                    </span>
                  )}
                </div>
              </div>

              {/* 工具结果 */}
              {tool_call.result && isSuccess && (
                <div className="mt-2 text-sm text-gray-600">
                  {tool_call.result.data && typeof tool_call.result.data === 'string' && (
                    <div className="bg-white rounded p-2 max-h-40 overflow-y-auto border border-gray-200">
                      <pre className="text-xs whitespace-pre-wrap font-mono">
                        {tool_call.result.data.length > 500
                          ? tool_call.result.data.substring(0, 500) + '\n...(内容过长，已截断)'
                          : tool_call.result.data
                        }
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* 错误信息 */}
              {tool_call.result && isError && (
                <div className="mt-2 text-sm text-red-600">
                  {tool_call.result.error || '执行失败'}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center space-x-2">
          <SparklesIcon className="w-5 h-5 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-800">AI 助手</h3>
          {currentTaskId && (
            <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
              会话中
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {/* 历史记录按钮 */}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center space-x-1 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
            title="查看历史会话"
          >
            <ClockIcon className="w-4 h-4" />
            <span>历史</span>
          </button>
          {/* 新建对话按钮 */}
          <button
            onClick={handleNewChat}
            className="flex items-center space-x-1 px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 transition-colors"
            title="新建对话"
          >
            <PlusIcon className="w-4 h-4" />
            <span>新建</span>
          </button>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 overflow-hidden">
        {showHistory ? (
          /* 历史记录视图 */
          <TaskHistoryView
            repositoryPath={projectPath}
            onLoadTask={handleLoadTask}
            onClose={() => setShowHistory(false)}
          />
        ) : (
          /* 聊天视图 */
          <div className="flex flex-col h-full">
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-600">
                  <SparklesIcon className="w-16 h-16 text-blue-400 mx-auto mb-6" />
                  <h3 className="text-xl font-semibold text-gray-800 mb-4">
                    开始与 AI 对话
                  </h3>
                  <p className="text-center max-w-md mb-6">
                    我可以帮助您分析代码、回答技术问题、生成代码片段等。
                  </p>
                  <div className="grid grid-cols-1 gap-3 text-sm w-full max-w-md">
                    <button
                      onClick={() => setInputMessage('分析这个项目的架构')}
                      className="px-4 py-3 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors text-left"
                    >
                      分析这个项目的架构
                    </button>
                    <button
                      onClick={() => setInputMessage('解释某个文件的功能')}
                      className="px-4 py-3 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors text-left"
                    >
                      解释某个文件的功能
                    </button>
                    <button
                      onClick={() => setInputMessage('帮我写一些代码')}
                      className="px-4 py-3 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors text-left"
                    >
                      帮我写一些代码
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((message) => {
                    // 🔥 跳过空消息（工具调用消息 content 为空，但有 tool_calls）
                    const hasContent = message.content && message.content.trim().length > 0;
                    const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;

                    // 如果既没有内容也没有工具调用，不渲染
                    if (!hasContent && !hasToolCalls) {
                      return null;
                    }

                    return (
                      <div
                        key={message.id}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-3xl ${
                            message.role === 'user'
                              ? 'bg-blue-600 text-white'
                              : 'bg-white border border-gray-200'
                          } rounded-lg p-4`}
                        >
                          {message.role === 'system' ? (
                            <div className="prose prose-sm max-w-none">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {message.content}
                              </ReactMarkdown>
                            </div>
                          ) : (
                            <>
                              {/* 文本内容 */}
                              {hasContent && (
                                <div className="prose prose-sm max-w-none">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {message.content}
                                  </ReactMarkdown>
                                </div>
                              )}

                              {/* 工具调用 */}
                              {hasToolCalls && renderToolCalls(message.tool_calls!)}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-white border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center space-x-2">
                          <ArrowPathIcon className="w-5 h-5 text-blue-600 animate-spin" />
                          <span className="text-sm text-gray-600">AI 正在思考...</span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* 输入区域 */}
            <div className="border-t border-gray-200 p-4 bg-white">
              <div className="flex items-end space-x-3">
                <div className="flex-1">
                  <textarea
                    ref={textareaRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="输入您的问题... (Enter 发送, Shift+Enter 换行)"
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    rows={1}
                    disabled={isLoading}
                  />
                </div>
                <button
                  onClick={sendMessage}
                  disabled={!inputMessage.trim() || isLoading}
                  className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <ArrowPathIcon className="w-5 h-5 animate-spin" />
                  ) : (
                    <PaperAirplaneIcon className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

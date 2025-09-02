import React, { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import {
  PaperAirplaneIcon,
  ArrowPathIcon,
  PlusIcon,
  TrashIcon,
  CogIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../../services/api";

interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

interface Message {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  token_count?: number;
  model_used?: string;
  provider_used?: string;
}

interface AIConfig {
  ai_provider: string;
  ai_model: string;
  ai_api_key: string;
  ai_base_url?: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
}

export const AIChat: React.FC = () => {
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [aiConfig, setAiConfig] = useState<AIConfig | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const queryClient = useQueryClient();

  // 获取AI配置
  const { data: configData } = useQuery({
    queryKey: ['ai-chat-config'],
    queryFn: () => api.getChatAIConfig(),
  });

  // 获取会话列表
  const { data: conversations = [], refetch: refetchConversations } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => api.getConversations(),
  });

  // 获取当前会话的消息
  const { refetch: refetchMessages } = useQuery({
    queryKey: ['messages', selectedConversation?.id],
    queryFn: async () => {
      if (!selectedConversation) return [];
      const messages = await api.getMessages(selectedConversation.id);
      setMessages(messages);
      return messages;
    },
    enabled: !!selectedConversation,
  });

  // 创建新会话的mutation
  const createConversationMutation = useMutation({
    mutationFn: (title?: string) => api.createConversation(title),
    onSuccess: (newConversation) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      setSelectedConversation(newConversation);
      setMessages([]);
      toast.success("新会话已创建");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "创建会话失败");
    }
  });

  // 删除会话的mutation
  const deleteConversationMutation = useMutation({
    mutationFn: (conversationId: number) => api.deleteConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      if (selectedConversation) {
        setSelectedConversation(null);
        setMessages([]);
      }
      toast.success("会话已删除");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "删除会话失败");
    }
  });

  // 发送消息的mutation
  const chatMutation = useMutation({
    mutationFn: ({ conversationId, message }: { conversationId: number | null; message: string }) =>
      api.chatWithAIConfig(conversationId, message),
    onSuccess: (response) => {
      // 刷新消息列表
      refetchMessages();
      refetchConversations();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "发送消息失败");
    }
  });

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (configData) {
      setAiConfig(configData);
    }
  }, [configData]);

  // 自动调整文本区域高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputMessage]);

  // 创建新会话
  const createNewConversation = () => {
    createConversationMutation.mutate(undefined);
  };

  // 删除当前会话
  const deleteCurrentConversation = () => {
    if (!selectedConversation) return;
    if (window.confirm("确定要删除这个会话吗？此操作不可撤销。")) {
      deleteConversationMutation.mutate(selectedConversation.id);
    }
  };

  // 发送消息
  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const messageToSend = inputMessage.trim();
    setInputMessage("");
    setIsLoading(true);

    try {
      await chatMutation.mutateAsync({
        conversationId: selectedConversation?.id || null,
        message: messageToSend
      });
    } catch (error) {
      console.error("发送消息失败:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // 渲染消息内容
  const renderMessageContent = (message: Message) => {
    return (
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message.content}
        </ReactMarkdown>
      </div>
    );
  };

  // 渲染配置状态
  const renderConfigStatus = () => {
    if (!aiConfig) return null;

    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CogIcon className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-800">
              当前配置: {aiConfig.ai_provider} - {aiConfig.ai_model}
            </span>
          </div>
          <div className="text-xs text-blue-600">
            Temperature: {aiConfig.temperature} | Max Tokens: {aiConfig.max_tokens}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full bg-gray-50">
      {/* 会话侧边栏 */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">会话</h2>
            <button
              onClick={createNewConversation}
              disabled={createConversationMutation.isPending}
              className="p-2 text-blue-600 hover:bg-blue-50 rounded-md"
              title="新建会话"
            >
              <PlusIcon className="w-5 h-5" />
            </button>
          </div>
          
          {renderConfigStatus()}
        </div>

        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <p>暂无会话</p>
              <p className="text-sm mt-1">点击 + 按钮创建新会话</p>
            </div>
          ) : (
            <div className="space-y-1 p-2">
              {conversations.map((conversation: Conversation) => (
                <div
                  key={conversation.id}
                  className={`p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedConversation?.id === conversation.id
                      ? "bg-blue-100 border border-blue-300"
                      : "hover:bg-gray-100"
                  }`}
                  onClick={() => setSelectedConversation(conversation)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {conversation.title}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(conversation.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                    {selectedConversation?.id === conversation.id && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteCurrentConversation();
                        }}
                        className="p-1 text-red-600 hover:bg-red-50 rounded-md"
                        title="删除会话"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 聊天主区域 */}
      <div className="flex-1 flex flex-col">
        {!selectedConversation ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <SparklesIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                欢迎使用AI聊天
              </h3>
              <p className="text-gray-600 mb-6">
                选择一个会话或创建新会话来开始聊天
              </p>
              <button
                onClick={createNewConversation}
                disabled={createConversationMutation.isPending}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {createConversationMutation.isPending ? "创建中..." : "新建会话"}
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* 消息区域 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center py-12">
                  <SparklesIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">开始与AI对话吧！</p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-3xl rounded-lg p-4 ${
                        message.role === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-white border border-gray-200"
                      }`}
                    >
                      <div className="flex items-center mb-2">
                        <span className="text-sm font-semibold">
                          {message.role === "user" ? "您" : "AI助手"}
                        </span>
                        <span
                          className={`text-xs ml-3 ${
                            message.role === "user" ? "text-blue-100" : "text-gray-400"
                          }`}
                        >
                          {new Date(message.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      {renderMessageContent(message)}
                    </div>
                  </div>
                ))
              )}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-lg p-4 max-w-3xl">
                    <div className="flex items-center space-x-3">
                      <ArrowPathIcon className="w-5 h-5 text-blue-600 animate-spin" />
                      <span className="text-sm text-gray-700">AI正在思考...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* 输入区域 */}
            <div className="border-t border-gray-200 p-4 bg-white">
              <div className="flex items-end space-x-3">
                <div className="flex-1 relative">
                  <textarea
                    ref={textareaRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="输入您的问题..."
                    disabled={isLoading}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
                    rows={1}
                    style={{ minHeight: "52px" }}
                  />
                </div>

                <button
                  onClick={sendMessage}
                  disabled={!inputMessage.trim() || isLoading}
                  className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <ArrowPathIcon className="w-5 h-5 animate-spin" />
                  ) : (
                    <PaperAirplaneIcon className="w-5 h-5" />
                  )}
                </button>
              </div>

              <div className="mt-2 text-xs text-gray-500 text-center">
                按 Enter 发送，Shift + Enter 换行
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

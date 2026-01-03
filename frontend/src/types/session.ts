/**
 * 会话/任务相关类型定义
 *
 * 参考 Cline 的 HistoryItem 结构
 */

/**
 * 任务信息
 */
export interface TaskInfo {
  id: string;                    // 任务 ID
  task: string;                  // 任务描述
  ts: number;                    // 创建时间 (timestamp)
  last_updated: number;          // 最后更新时间
  tokens_in: number;             // 输入 tokens
  tokens_out: number;            // 输出 tokens
  cache_writes: number;          // 缓存写入次数
  cache_reads: number;           // 缓存读取次数
  total_cost: number;            // 总成本
  size: number;                  // 任务大小 (bytes)
  is_favorited: boolean;         // 是否收藏
  api_provider: string | null;   // AI 提供商
  api_model: string | null;      // AI 模型
  repository_path: string | null; // 仓库路径
}

/**
 * 任务列表响应
 */
export interface TaskListResponse {
  tasks: TaskInfo[];
  total_count: number;
  total_tokens: number;
  total_cost: number;
}

/**
 * 任务删除响应
 */
export interface TaskDeleteResponse {
  success: boolean;
  message: string;
}

/**
 * 任务收藏切换响应
 */
export interface TaskToggleFavoriteResponse {
  success: boolean;
  is_favorited: boolean;
  message: string;
}

/**
 * 任务详情(用于恢复)
 */
export interface TaskDetail {
  task_id: string;
  task: string;
  created_at: number;
  last_updated: number;
  api_provider: string | null;
  api_model: string | null;
  messages: any[];              // API 消息列表
  message_count: number;
}

/**
 * 排序选项
 */
export type SortOption = 'newest' | 'oldest' | 'cost';

/**
 * API 请求参数
 */
export interface ListTasksParams {
  repository_path: string;
  search_query?: string;
  favorites_only?: boolean;
  sort_by?: SortOption;
  limit?: number;
}

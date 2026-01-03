/**
 * 任务历史卡片组件
 *
 * 参考 Cline 的 HistoryView 任务卡片设计
 */

import React from 'react';
import {
  StarIcon,
  TrashIcon,
  ClockIcon,
  CpuChipIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import { TaskInfo } from '../../../types/session';

interface TaskCardProps {
  task: TaskInfo;
  onLoad: (taskId: string) => void;
  onToggleFavorite: (taskId: string) => void;
  onDelete: (taskId: string) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  onLoad,
  onToggleFavorite,
  onDelete,
}) => {
  // 格式化时间
  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;

    return date.toLocaleDateString('zh-CN');
  };

  // 格式化文件大小
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // 格式化成本
  const formatCost = (cost: number) => {
    if (cost < 0.01) return '< $0.01';
    return `$${cost.toFixed(4)}`;
  };

  // 格式化 Token 数量
  const formatTokens = (tokens: number) => {
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
    if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
    return tokens.toString();
  };

  const totalTokens = task.tokens_in + task.tokens_out;

  return (
    <div
      className="group relative bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md hover:border-blue-300 transition-all duration-200 cursor-pointer"
      onClick={() => onLoad(task.id)}
    >
      {/* 顶部信息行 */}
      <div className="flex items-start justify-between mb-2">
        {/* 任务描述 */}
        <div className="flex-1 pr-20">
          <p className="text-sm font-medium text-gray-900 line-clamp-2">
            {task.task}
          </p>
        </div>

        {/* 收藏按钮 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleFavorite(task.id);
          }}
          className="absolute top-3 right-12 p-1 text-gray-400 hover:text-yellow-500 transition-colors"
          title={task.is_favorited ? '取消收藏' : '收藏'}
        >
          {task.is_favorited ? (
            <StarIconSolid className="w-5 h-5 text-yellow-500" />
          ) : (
            <StarIcon className="w-5 h-5" />
          )}
        </button>

        {/* 删除按钮 - 悬停显示 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(task.id);
          }}
          className="absolute top-3 right-3 p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
          title={`删除 (${formatSize(task.size)})`}
        >
          <TrashIcon className="w-5 h-5" />
        </button>
      </div>

      {/* 底部元数据行 */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        {/* 左侧:时间、Token、成本 */}
        <div className="flex items-center space-x-3">
          {/* 时间 */}
          <div className="flex items-center space-x-1" title="创建时间">
            <ClockIcon className="w-3.5 h-3.5" />
            <span>{formatTime(task.ts)}</span>
          </div>

          {/* Token 数量 */}
          {totalTokens > 0 && (
            <div className="flex items-center space-x-1" title="Token 使用量">
              <CpuChipIcon className="w-3.5 h-3.5" />
              <span>{formatTokens(totalTokens)}</span>
            </div>
          )}

          {/* 成本 */}
          {task.total_cost > 0 && (
            <div className="flex items-center space-x-1" title="成本">
              <CurrencyDollarIcon className="w-3.5 h-3.5" />
              <span>{formatCost(task.total_cost)}</span>
            </div>
          )}
        </div>

        {/* 右侧: API 模型 */}
        {task.api_model && (
          <div className="text-xs text-gray-400">
            {task.api_model}
          </div>
        )}
      </div>
    </div>
  );
};

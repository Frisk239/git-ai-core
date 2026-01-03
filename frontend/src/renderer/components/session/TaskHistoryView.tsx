/**
 * 任务历史视图组件
 *
 * 参考 Cline 的 HistoryView 设计
 * 包含搜索、过滤、排序和任务列表
 */

import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  FunnelIcon,
  ArrowsUpDownIcon,
  StarIcon,
} from '@heroicons/react/24/outline';
import { TaskInfo, SortOption } from '../../../types/session';
import { api } from '../../services/api';
import { TaskCard } from './TaskCard';

interface TaskHistoryViewProps {
  repositoryPath: string;
  onLoadTask: (taskId: string) => void;
  onClose?: () => void;
}

export const TaskHistoryView: React.FC<TaskHistoryViewProps> = ({
  repositoryPath,
  onLoadTask,
  onClose,
}) => {
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [filteredTasks, setFilteredTasks] = useState<TaskInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [sortBy, setSortBy] = useState<SortOption>('newest');

  // 加载任务列表
  const loadTasks = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await api.getTaskList({
        repository_path: repositoryPath,
        sort_by: sortBy,
        favorites_only: favoritesOnly,
        search_query: searchQuery || undefined,
        limit: 100,
      });
      setTasks(response.tasks);
      setFilteredTasks(response.tasks);
    } catch (error) {
      console.error('加载任务列表失败:', error);
      toast.error('加载任务列表失败');
    } finally {
      setIsLoading(false);
    }
  }, [repositoryPath, sortBy, favoritesOnly, searchQuery]);

  // 初始加载
  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // 处理搜索输入(使用防抖)
  useEffect(() => {
    const timer = setTimeout(() => {
      loadTasks();
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, loadTasks]);

  // 处理收藏切换
  const handleToggleFavorite = async (taskId: string) => {
    try {
      await api.toggleTaskFavorite(taskId, repositoryPath);

      // 乐观更新
      setTasks((prev) =>
        prev.map((task) =>
          task.id === taskId
            ? { ...task, is_favorited: !task.is_favorited }
            : task
        )
      );
      setFilteredTasks((prev) =>
        prev.map((task) =>
          task.id === taskId
            ? { ...task, is_favorited: !task.is_favorited }
            : task
        )
      );

      toast.success('收藏状态已更新');
    } catch (error) {
      console.error('切换收藏失败:', error);
      toast.error('切换收藏失败');
      // 重新加载以恢复状态
      loadTasks();
    }
  };

  // 处理删除任务
  const handleDeleteTask = async (taskId: string) => {
    if (!confirm('确定要删除这个任务吗?此操作不可撤销。')) {
      return;
    }

    try {
      await api.deleteTask(taskId, repositoryPath);

      // 从列表中移除
      setTasks((prev) => prev.filter((task) => task.id !== taskId));
      setFilteredTasks((prev) => prev.filter((task) => task.id !== taskId));

      toast.success('任务已删除');
    } catch (error) {
      console.error('删除任务失败:', error);
      toast.error('删除任务失败');
    }
  };

  // 清除搜索
  const handleClearSearch = () => {
    setSearchQuery('');
  };

  // 切换收藏过滤
  const handleToggleFavoritesFilter = () => {
    setFavoritesOnly(!favoritesOnly);
  };

  // 排序选项标签
  const sortOptions: { value: SortOption; label: string }[] = [
    { value: 'newest', label: '最新' },
    { value: 'oldest', label: '最旧' },
    { value: 'cost', label: '成本' },
  ];

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <div className="flex items-center space-x-2">
          <h2 className="text-xl font-semibold text-gray-900">任务历史</h2>
          {tasks.length > 0 && (
            <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">
              {filteredTasks.length} / {tasks.length}
            </span>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* 搜索和过滤栏 */}
      <div className="px-6 py-4 border-b border-gray-200 bg-white space-y-3">
        {/* 搜索框 */}
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索任务..."
            className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          {searchQuery && (
            <button
              onClick={handleClearSearch}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* 过滤和排序选项 */}
        <div className="flex items-center justify-between">
          {/* 过滤选项 */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleToggleFavoritesFilter}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                favoritesOnly
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <StarIcon className="w-4 h-4" />
              <span>收藏</span>
            </button>
          </div>

          {/* 排序选项 */}
          <div className="flex items-center space-x-2">
            <ArrowsUpDownIcon className="w-4 h-4 text-gray-400" />
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
              {sortOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setSortBy(option.value)}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    sortBy === option.value
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 任务列表 */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-sm text-gray-600">加载中...</p>
            </div>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            {searchQuery || favoritesOnly ? (
              <>
                <FunnelIcon className="w-16 h-16 text-gray-300 mb-4" />
                <p className="text-lg font-medium">没有找到匹配的任务</p>
                <p className="text-sm mt-1">尝试调整搜索条件或过滤器</p>
              </>
            ) : (
              <>
                <MagnifyingGlassIcon className="w-16 h-16 text-gray-300 mb-4" />
                <p className="text-lg font-medium">还没有任务历史</p>
                <p className="text-sm mt-1">开始与 AI 对话后,任务会自动保存在这里</p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onLoad={onLoadTask}
                onToggleFavorite={handleToggleFavorite}
                onDelete={handleDeleteTask}
              />
            ))}
          </div>
        )}
      </div>

      {/* 底部统计信息 */}
      {tasks.length > 0 && !isLoading && (
        <div className="px-6 py-3 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>
              显示 {filteredTasks.length} 个任务
              {favoritesOnly && ' (仅收藏)'}
              {searchQuery && ` (搜索: "${searchQuery}")`}
            </span>
            <span>按 {sortOptions.find((o) => o.value === sortBy)?.label} 排序</span>
          </div>
        </div>
      )}
    </div>
  );
};

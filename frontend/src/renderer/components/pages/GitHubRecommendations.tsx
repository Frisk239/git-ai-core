import React, { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import { Link } from "react-router-dom";
import {
  StarIcon,
  CodeBracketIcon,
  CalendarIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  XMarkIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { api } from "../../services/api";
import {
  usePersistedState,
  clearPersistedState,
  GITHUB_STORAGE_KEYS,
  saveSearchResults,
  getSearchResults,
  SearchResultData,
} from "../../hooks/usePersistedState";
import { formatNumber } from "../../utils/formatNumber";

interface Repository {
  id: number;
  name: string;
  full_name: string;
  owner: {
    login: string;
    avatar_url: string;
  };
  html_url: string;
  description: string;
  stargazers_count: number;
  forks_count: number;
  watchers_count: number;
  language: string;
  updated_at: string;
  readme?: string;
}

export const GitHubRecommendations: React.FC = () => {
  const [searchQuery, setSearchQuery] = usePersistedState(
    GITHUB_STORAGE_KEYS.SEARCH_QUERY,
    ""
  );
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [clonePath, setClonePath] = useState("");
  const [showFilters, setShowFilters] = usePersistedState(
    GITHUB_STORAGE_KEYS.SHOW_FILTERS,
    false
  );
  const [filters, setFilters] = usePersistedState(GITHUB_STORAGE_KEYS.FILTERS, {
    language: "",
    sort: "", // 排序方式：''（默认）, 'stars-asc', 'stars-desc'
    updatedAfter: "",
  });
  const [savedSearchResults, setSavedSearchResults] =
    useState<SearchResultData | null>(null);

  // 组件挂载时检查保存的搜索结果
  useEffect(() => {
    const savedResults = getSearchResults(GITHUB_STORAGE_KEYS.SEARCH_RESULTS);
    if (savedResults) {
      setSavedSearchResults(savedResults);
      toast.success("已恢复之前的搜索结果");
    }
  }, []);

  // 获取热门项目
  const { data: trendingData, isLoading: isLoadingTrending } = useQuery({
    queryKey: ["github-trending"],
    queryFn: () => api.getGitHubTrending(),
    enabled: true,
  });

  // 基础搜索项目
  const searchMutation = useMutation({
    mutationFn: (query: string) => api.searchGitHubRepos(query),
    onSuccess: (data) => {
      toast.success(`找到 ${data.repositories.length} 个项目`);
      // 保存搜索结果
      saveSearchResults(GITHUB_STORAGE_KEYS.SEARCH_RESULTS, {
        repositories: data.repositories,
        searchType: "basic",
        timestamp: Date.now(),
        query: searchQuery,
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "搜索失败");
    },
  });

  // 增强搜索项目
  const enhancedSearchMutation = useMutation({
    mutationFn: () =>
      api.enhancedSearchGitHubRepos(
        searchQuery,
        filters.language,
        filters.updatedAfter,
        filters.sort
      ),
    onSuccess: (data) => {
      toast.success(`找到 ${data.repositories.length} 个项目`);
      // 记录用户搜索行为
      data.repositories.forEach((repo: Repository) => {
        api.recordGitHubAction(repo.full_name, "search", searchQuery);
      });
      // 保存搜索结果
      saveSearchResults(GITHUB_STORAGE_KEYS.SEARCH_RESULTS, {
        repositories: data.repositories,
        searchType: "enhanced",
        timestamp: Date.now(),
        query: searchQuery,
        filters: filters,
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "搜索失败");
    },
  });

  // 获取个性化推荐
  const recommendationMutation = useMutation({
    mutationFn: () => api.getGitHubRecommendations("default", 10),
    onSuccess: (data) => {
      toast.success(`为您推荐了 ${data.repositories.length} 个项目`);
      // 保存推荐结果
      saveSearchResults(GITHUB_STORAGE_KEYS.SEARCH_RESULTS, {
        repositories: data.repositories,
        searchType: "recommendation",
        timestamp: Date.now(),
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "推荐失败");
    },
  });

  // 获取项目详情
  const detailMutation = useMutation({
    mutationFn: ({ owner, repo }: { owner: string; repo: string }) =>
      api.getGitHubRepoDetails(owner, repo),
    onSuccess: (data) => {
      setSelectedRepo(data);
      setShowDetailModal(true);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "获取详情失败");
    },
  });

  // 克隆项目
  const cloneMutation = useMutation({
    mutationFn: ({ url, path }: { url: string; path?: string }) =>
      api.cloneRepository(url, path),
    onSuccess: () => {
      toast.success("项目克隆成功！");
      setShowCloneModal(false);
      setClonePath("");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "克隆失败");
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      toast.error("请输入搜索关键词");
      return;
    }

    if (
      showFilters &&
      (filters.language || filters.sort || filters.updatedAfter)
    ) {
      // 使用增强搜索
      enhancedSearchMutation.mutate();
    } else {
      // 使用基础搜索
      searchMutation.mutate(searchQuery.trim());
    }
  };

  const handleEnhancedSearch = () => {
    if (!searchQuery.trim()) {
      toast.error("请输入搜索关键词");
      return;
    }
    enhancedSearchMutation.mutate();
  };

  const handleFilterChange = (key: keyof typeof filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      language: "",
      sort: "",
      updatedAfter: "",
    });
  };

  const hasActiveFilters =
    filters.language || filters.sort || filters.updatedAfter;

  const handleViewDetails = (repo: Repository) => {
    const [owner, repoName] = repo.full_name.split("/");
    detailMutation.mutate({ owner, repo: repoName });
  };

  const handleClone = (repo: Repository) => {
    setSelectedRepo(repo);
    setShowCloneModal(true);
  };

  const handleConfirmClone = () => {
    if (!selectedRepo) return;

    cloneMutation.mutate({
      url: selectedRepo.html_url + ".git",
      path: clonePath || undefined,
    });
  };

  // 清除所有保存的状态
  const clearAllSavedState = () => {
    clearPersistedState(GITHUB_STORAGE_KEYS.SEARCH_QUERY);
    clearPersistedState(GITHUB_STORAGE_KEYS.FILTERS);
    clearPersistedState(GITHUB_STORAGE_KEYS.SHOW_FILTERS);
    clearPersistedState(GITHUB_STORAGE_KEYS.SEARCH_RESULTS);

    setSearchQuery("");
    setFilters({
      language: "",
      sort: "",
      updatedAfter: "",
    });
    setShowFilters(false);
    setSavedSearchResults(null);

    toast.success("已清除所有保存的搜索状态");
  };

  const repositories =
    recommendationMutation.data?.repositories ||
    enhancedSearchMutation.data?.repositories ||
    searchMutation.data?.repositories ||
    savedSearchResults?.repositories ||
    trendingData?.repositories ||
    [];

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString("zh-CN");
  };

  // 常用编程语言选项
  const programmingLanguages = [
    "JavaScript",
    "TypeScript",
    "Python",
    "Java",
    "C++",
    "C#",
    "PHP",
    "Ruby",
    "Go",
    "Rust",
    "Swift",
    "Kotlin",
    "Dart",
    "Scala",
    "HTML",
    "CSS",
    "Shell",
    "Vue",
    "React",
    "Angular",
    "Svelte",
    "R",
    "Lua",
    "Perl",
    "Haskell",
  ];

  return (
    <div className="p-6">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">GitHub项目推荐</h1>
          <p className="mt-2 text-gray-600">发现热门的GitHub项目</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={clearAllSavedState}
            className="px-6 py-3 bg-gray-500 text-white rounded-lg hover:bg-gray-600 flex items-center gap-2"
            title="清除所有保存的搜索和筛选状态"
          >
            <TrashIcon className="h-4 w-4" />
            清除状态
          </button>
          <button
            onClick={() => recommendationMutation.mutate()}
            disabled={recommendationMutation.isPending}
            className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
          >
            {recommendationMutation.isPending ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                推送中...
              </>
            ) : (
              <>
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
                智能推送
              </>
            )}
          </button>
        </div>
      </div>

      {/* 搜索框 */}
      <div className="mb-8">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索GitHub项目..."
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={
              searchMutation.isPending || enhancedSearchMutation.isPending
            }
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {searchMutation.isPending || enhancedSearchMutation.isPending
              ? "搜索中..."
              : "搜索"}
          </button>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={`px-4 py-3 rounded-lg flex items-center gap-2 ${
              showFilters || hasActiveFilters
                ? "bg-blue-100 text-blue-700 border border-blue-300"
                : "bg-gray-100 text-gray-700 border border-gray-300"
            } hover:bg-blue-50`}
          >
            <FunnelIcon className="h-5 w-5" />
            筛选
            {hasActiveFilters && (
              <span className="bg-blue-600 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                !
              </span>
            )}
          </button>
        </form>

        {/* 筛选面板 */}
        {showFilters && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-gray-700">高级筛选</h3>
              <button
                onClick={() => setShowFilters(false)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* 编程语言筛选 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  编程语言
                </label>
                <select
                  value={filters.language}
                  onChange={(e) =>
                    handleFilterChange("language", e.target.value)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="">所有语言</option>
                  {programmingLanguages.map((lang) => (
                    <option key={lang} value={lang}>
                      {lang}
                    </option>
                  ))}
                </select>
              </div>

              {/* 排序方式 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  排序方式
                </label>
                <select
                  value={filters.sort}
                  onChange={(e) => handleFilterChange("sort", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="">默认排序</option>
                  <option value="stars-asc">星标数升序</option>
                  <option value="stars-desc">星标数降序</option>
                </select>
              </div>

              {/* 占位符，保持布局 */}
              <div></div>

              {/* 更新时间筛选 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  更新时间
                </label>
                <select
                  value={filters.updatedAfter}
                  onChange={(e) =>
                    handleFilterChange("updatedAfter", e.target.value)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="">全部时间</option>
                  <option value="7d">最近7天</option>
                  <option value="30d">最近30天</option>
                  <option value="90d">最近90天</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={clearFilters}
                disabled={!hasActiveFilters}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                清除筛选
              </button>
              <button
                onClick={handleEnhancedSearch}
                disabled={
                  enhancedSearchMutation.isPending || !searchQuery.trim()
                }
                className="px-4 py-2 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {enhancedSearchMutation.isPending ? "搜索中..." : "应用筛选"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 项目列表 */}
      {isLoadingTrending && !searchMutation.data ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-500">加载热门项目中...</p>
        </div>
      ) : repositories.length === 0 ? (
        <div className="text-center py-12">
          <CodeBracketIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">暂无项目</p>
          <p className="text-sm text-gray-400 mt-1">
            尝试搜索或等待热门项目加载
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {repositories.map((repo: Repository) => (
            <div
              key={repo.id}
              className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow"
            >
              <div className="p-6">
                {/* 项目头信息 */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900 truncate">
                      {repo.name}
                    </h3>
                    <p className="text-sm text-gray-600 truncate">
                      {repo.owner.login}
                    </p>
                  </div>
                  <img
                    src={repo.owner.avatar_url}
                    alt={repo.owner.login}
                    className="w-10 h-10 rounded-full ml-3"
                  />
                </div>

                {/* 项目描述 */}
                {repo.description && (
                  <p className="text-sm text-gray-600 mb-4 line-clamp-3">
                    {repo.description}
                  </p>
                )}

                {/* 项目统计 */}
                <div className="flex items-center justify-between text-sm text-gray-500 mb-4">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center">
                      <StarIcon className="h-4 w-4 mr-1" />
                      <span>{formatNumber(repo.stargazers_count)}</span>
                    </div>
                    <div className="flex items-center">
                      <span className="text-xs mr-1">🍴</span>
                      <span>{formatNumber(repo.forks_count)}</span>
                    </div>
                    <div className="flex items-center">
                      <span className="text-xs mr-1">👁️</span>
                      <span>{formatNumber(repo.watchers_count)}</span>
                    </div>
                  </div>
                  {repo.language && (
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                      {repo.language}
                    </span>
                  )}
                </div>

                {/* 更新时间 */}
                <div className="flex items-center text-xs text-gray-400 mb-4">
                  <CalendarIcon className="h-3 w-3 mr-1" />
                  更新于 {formatDate(repo.updated_at)}
                </div>

                {/* 操作按钮 */}
                <div className="flex space-x-2">
                  <button
                    onClick={() => handleViewDetails(repo)}
                    className="flex-1 px-3 py-2 bg-gray-100 text-gray-700 text-sm rounded-md hover:bg-gray-200"
                  >
                    查看详情
                  </button>
                  <button
                    onClick={() => handleClone(repo)}
                    className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                  >
                    克隆
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 项目详情模态框 */}
      {showDetailModal && selectedRepo && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                {selectedRepo.full_name}
              </h2>
              <button
                onClick={() => setShowDetailModal(false)}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  项目信息
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Stars:</span>
                    <span className="font-medium">
                      {formatNumber(selectedRepo.stargazers_count)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Forks:</span>
                    <span className="font-medium">
                      {formatNumber(selectedRepo.forks_count)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Watchers:</span>
                    <span className="font-medium">
                      {formatNumber(selectedRepo.watchers_count)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>语言:</span>
                    <span className="font-medium">
                      {selectedRepo.language || "未知"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="md:col-span-2">
                <h3 className="text-sm font-medium text-gray-700 mb-2">描述</h3>
                <p className="text-gray-600">
                  {selectedRepo.description || "无描述"}
                </p>
              </div>
            </div>

            {selectedRepo.readme && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  README
                </h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <pre className="text-sm text-gray-800 whitespace-pre-wrap">
                    {selectedRepo.readme}
                  </pre>
                </div>
              </div>
            )}

            <div className="flex space-x-3 mt-6">
              <a
                href={selectedRepo.html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                在GitHub上查看
              </a>
              <button
                onClick={() => handleClone(selectedRepo)}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                克隆项目
              </button>
              <button
                onClick={() => setShowDetailModal(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 克隆模态框 */}
      {showCloneModal && selectedRepo && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-semibold mb-4">克隆项目</h2>

            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-2">项目URL:</p>
              <p className="text-sm font-mono bg-gray-100 p-2 rounded">
                {selectedRepo.html_url}.git
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                本地路径（可选）
              </label>
              <input
                type="text"
                value={clonePath}
                onChange={(e) => setClonePath(e.target.value)}
                placeholder="/path/to/clone"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex space-x-3">
              <button
                onClick={handleConfirmClone}
                disabled={cloneMutation.isPending}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {cloneMutation.isPending ? "克隆中..." : "克隆"}
              </button>
              <button
                onClick={() => setShowCloneModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

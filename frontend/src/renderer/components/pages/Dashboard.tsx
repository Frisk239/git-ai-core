import React from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  FolderIcon,
  CodeBracketIcon,
  ClockIcon,
  StarIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import { Link } from "react-router-dom";
import { toast } from "react-hot-toast";
import { api } from "../../services/api";
import { formatNumber } from "../../utils/formatNumber";

interface Project {
  name: string;
  path: string;
  current_branch: string;
  commits_count: number;
  last_commit?: {
    date: string;
  };
}

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
}

export const Dashboard: React.FC = () => {
  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => api.getProjects(),
  });

  // 获取个性化推荐
  const recommendationMutation = useMutation({
    mutationFn: () => api.getGitHubRecommendations("default", 6),
    onSuccess: (data) => {
      toast.success(`为您推荐了 ${data.repositories.length} 个项目`);
    },
    onError: (error: any) => {
      console.error("推荐失败:", error);
    },
  });

  const { data: recommendations = [], isLoading: isLoadingRecommendations } =
    useQuery({
      queryKey: ["github-recommendations"],
      queryFn: () => api.getGitHubRecommendations("default", 6),
      enabled: true,
    });

  const recentProjects = projects.slice(0, 5);
  const recommendedRepos = recommendations?.repositories?.slice(0, 3) || [];

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-gray-600">
          Welcome to Git AI Core - Your AI-powered Git assistant
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <FolderIcon className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">
                Total Projects
              </p>
              <p className="text-2xl font-bold text-gray-900">
                {projects.length}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-lg">
              <CodeBracketIcon className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">
                Active Repositories
              </p>
              <p className="text-2xl font-bold text-gray-900">
                {projects.length}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="p-2 bg-purple-100 rounded-lg">
              <ClockIcon className="h-6 w-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Last Updated</p>
              <p className="text-2xl font-bold text-gray-900">Now</p>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Projects
          </h2>
        </div>

        {isLoading ? (
          <div className="p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-gray-500">Loading projects...</p>
          </div>
        ) : recentProjects.length === 0 ? (
          <div className="p-6 text-center">
            <FolderIcon className="h-12 w-12 text-gray-400 mx-auto" />
            <p className="mt-2 text-gray-500">No projects found</p>
            <p className="text-sm text-gray-400 mt-1">
              Clone a repository to get started
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {recentProjects.map((project: Project) => (
              <Link
                key={project.path}
                to={`/projects/${encodeURIComponent(project.path)}`}
                className="px-6 py-4 hover:bg-gray-50 block cursor-pointer transition-colors duration-200"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-medium text-gray-900 hover:text-blue-600 transition-colors duration-200">
                      {project.name}
                    </h3>
                    <p className="text-sm text-gray-500">{project.path}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Branch: {project.current_branch} • {project.commits_count}{" "}
                      commits
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500">
                      Last commit:{" "}
                      {project.last_commit?.date
                        ? new Date(
                            project.last_commit.date
                          ).toLocaleDateString()
                        : "N/A"}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* 猜你喜欢推荐模块 */}
      <div className="bg-white rounded-lg shadow mt-8">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center">
            <SparklesIcon className="h-5 w-5 text-purple-600 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">猜你喜欢</h2>
            <span className="ml-2 text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded-full">
              AI推荐
            </span>
          </div>
          <Link
            to="/github-recommendations"
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
          >
            查看更多
            <svg
              className="w-4 h-4 ml-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </Link>
        </div>

        {isLoadingRecommendations ? (
          <div className="p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto"></div>
            <p className="mt-2 text-gray-500">正在为您推荐项目...</p>
          </div>
        ) : recommendedRepos.length === 0 ? (
          <div className="p-6 text-center">
            <SparklesIcon className="h-12 w-12 text-gray-400 mx-auto" />
            <p className="mt-2 text-gray-500">暂无推荐项目</p>
            <button
              onClick={() => recommendationMutation.mutate()}
              className="mt-3 text-sm text-purple-600 hover:text-purple-800"
            >
              重新获取推荐
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {recommendedRepos.map((repo: Repository) => (
              <div key={repo.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center">
                      <img
                        src={repo.owner.avatar_url}
                        alt={repo.owner.login}
                        className="w-8 h-8 rounded-full mr-3"
                      />
                      <div>
                        <h3 className="text-sm font-medium text-gray-900 hover:text-blue-600 cursor-pointer">
                          {repo.full_name}
                        </h3>
                        <p className="text-xs text-gray-500 mt-1">
                          {repo.description}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center mt-2 text-xs text-gray-500">
                      <div className="flex items-center mr-4">
                        <StarIcon className="h-3 w-3 mr-1" />
                        <span>{formatNumber(repo.stargazers_count)}</span>
                      </div>
                      <div className="flex items-center mr-4">
                        <CodeBracketIcon className="h-3 w-3 mr-1" />
                        <span>{formatNumber(repo.forks_count)}</span>
                      </div>
                      {repo.language && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {repo.language}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="ml-4 flex flex-col items-end">
                    <a
                      href={repo.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:text-blue-800 mb-2"
                    >
                      查看项目
                    </a>
                    <p className="text-xs text-gray-400">
                      更新于 {new Date(repo.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

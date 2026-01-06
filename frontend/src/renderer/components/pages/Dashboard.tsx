import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  FolderIcon,
  CodeBracketIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";
import { Link } from "react-router-dom";

interface Project {
  name: string;
  path: string;
  current_branch: string;
  commits_count: number;
  last_commit?: {
    date: string;
  };
}

export const Dashboard: React.FC = () => {
  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: async () => {
      const response = await fetch("http://localhost:8000/api/projects");
      if (!response.ok) {
        throw new Error("Failed to fetch projects");
      }
      return response.json();
    },
  });

  const recentProjects = projects.slice(0, 5);

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
    </div>
  );
};

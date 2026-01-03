import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import {
  FolderIcon,
  DocumentTextIcon,
  TrashIcon,
  ArrowPathIcon,
  ChatBubbleLeftRightIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CodeBracketIcon,
  UserIcon,
  MagnifyingGlassIcon,
} from "@heroicons/react/24/outline";
import { api } from "../../services/api";
import { FileViewer } from "./FileViewer";
import { ChatPanel } from "../session/ChatPanel";

interface Project {
  info: {
    name: string;
    path: string;
    current_branch: string;
    commits_count: number;
    remote_url?: string;
  };
  recent_commits?: Array<{
    hash: string;
    message: string;
    author: string;
    date: string;
  }>;
  branches?: Array<{
    name: string;
    is_active: boolean;
  }>;
  file_tree?: {
    type: "file" | "directory";
    name: string;
    children?: any[];
    size?: number;
    extension?: string;
  };
}

interface FileTreeNode {
  type: "file" | "directory";
  name: string;
  children?: FileTreeNode[];
  size?: number;
  extension?: string;
}

export const ProjectDetail: React.FC = () => {
  const { path } = useParams<{ path: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  // 添加展开文件夹状态
  const [expandedFolders, setExpandedFolders] = useState<
    Record<string, boolean>
  >({});

  // 更新项目状态
  const [isUpdating, setIsUpdating] = useState(false);
  const [previewFile, setPreviewFile] = useState<{
    path: string;
    content: string;
  } | null>(null);

  const decodedPath = decodeURIComponent(path || "");

  const { data: project, isLoading } = useQuery<Project>({
    queryKey: ["project", decodedPath],
    queryFn: () => api.getProjectOverview(decodedPath),
    enabled: !!decodedPath,
  });

  // 初始化时展开一级文件夹
  useEffect(() => {
    if (
      project?.file_tree &&
      project.file_tree.type === "directory" &&
      project.file_tree.children
    ) {
      const initialExpanded: Record<string, boolean> = {};
      project.file_tree.children.forEach((child) => {
        if (child.type === "directory") {
          initialExpanded[child.name] = true;
        }
      });
      setExpandedFolders(initialExpanded);
    }
  }, [project?.file_tree]);

  const handleDeleteProject = async () => {
    setIsDeleting(true);
    try {
      const result = await api.deleteProject(decodedPath);

      if (result.success) {
        toast.success(result.message || "项目删除成功");

        queryClient.removeQueries({ queryKey: ["project", decodedPath] });

        navigate("/projects");
      } else {
        if (result.manual_action_needed) {
          toast.error(result.error || "删除失败，需要手动操作");
          alert(
            `删除失败详情：\n${result.details}\n\n请手动删除文件夹：${decodedPath}`
          );
        } else {
          toast.error(result.error || "删除项目失败");
        }
      }
    } catch (error: any) {
      console.error("删除项目错误:", error);
      const errorMessage =
        error.response?.data?.detail || error.message || "删除项目失败";
      toast.error(`删除失败: ${errorMessage}`);
    } finally {
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const handleFileClick = async (filePath: string) => {
    setIsLoadingFile(true);
    try {
      // 清理文件路径：移除项目根目录前缀
      const cleanFilePath = filePath.replace(/^[^\/]+\//, "");

      console.log("原始文件路径:", filePath);
      console.log("清理后文件路径:", cleanFilePath);

      const result = await api.getFileContent(decodedPath, cleanFilePath);
      setFileContent(result.content);
      setSelectedFile(cleanFilePath);
    } catch (error) {
      console.error("文件读取错误:", error);
      toast.error("无法读取文件内容");
    } finally {
      setIsLoadingFile(false);
    }
  };

  // 添加处理文件夹点击的函数
  const handleFolderClick = (folderPath: string) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [folderPath]: !prev[folderPath],
    }));
  };

  // 更新仓库
  const handleUpdateRepository = async () => {
    setIsUpdating(true);
    try {
      const result = await api.pullUpdates(decodedPath);

      if (result.success) {
        toast.success("仓库更新成功");

        // 更新成功后自动刷新页面数据
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ["project", decodedPath] });
        }, 1000);
      } else {
        toast.error(result.error || "仓库更新失败");
      }
    } catch (error) {
      console.error("更新仓库失败:", error);
      toast.error("更新仓库失败");
    } finally {
      setIsUpdating(false);
    }
  };

  // 处理文件预览
  const handleFilePreview = (filePath: string, content: string) => {
    setPreviewFile({ path: filePath, content });
  };

  // 文件搜索状态
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<string[]>([]);

  // 搜索文件
  const searchFiles = (
    node: FileTreeNode,
    term: string,
    currentPath = ""
  ): string[] => {
    if (!term.trim()) return [];

    const results: string[] = [];
    const fullPath = currentPath ? `${currentPath}/${node.name}` : node.name;

    // 检查当前节点是否匹配
    if (node.name.toLowerCase().includes(term.toLowerCase())) {
      results.push(fullPath);
    }

    // 递归搜索子节点
    if (node.type === "directory" && node.children) {
      for (const child of node.children) {
        results.push(...searchFiles(child, term, fullPath));
      }
    }

    return results;
  };

  // 处理搜索输入变化
  const handleSearchChange = (term: string) => {
    setSearchTerm(term);
    if (project?.file_tree) {
      const results = searchFiles(project.file_tree, term);
      setSearchResults(results);
    }
  };

  // 关闭文件预览
  const handleClosePreview = () => {
    setPreviewFile(null);
  };

  // 优化后的文件树渲染函数
  const renderFileTree = (node: FileTreeNode, level = 0, currentPath = "") => {
    const indent = level * 16;
    const fullPath = currentPath ? `${currentPath}/${node.name}` : node.name;
    const isExpanded = expandedFolders[fullPath] === true;

    if (node.type === "file") {
      return (
        <div
          key={fullPath}
          className={`flex items-center py-2 px-3 rounded cursor-pointer transition-colors ${
            selectedFile === fullPath
              ? "bg-blue-100 border-l-4 border-blue-500"
              : "hover:bg-gray-100"
          }`}
          style={{ paddingLeft: indent + 8 }}
          onClick={() => handleFileClick(fullPath)}
        >
          <DocumentTextIcon className="h-4 w-4 mr-2 text-blue-600" />
          <span className="text-sm text-gray-800 truncate">{node.name}</span>
        </div>
      );
    }

    return (
      <div key={fullPath}>
        <div
          className={`flex items-center py-2 px-3 rounded cursor-pointer transition-colors ${
            isExpanded ? "bg-gray-100" : "hover:bg-gray-100"
          }`}
          style={{ paddingLeft: indent + 8 }}
          onClick={() => handleFolderClick(fullPath)}
        >
          {isExpanded ? (
            <ChevronDownIcon className="h-4 w-4 mr-2 text-gray-600" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 mr-2 text-gray-600" />
          )}
          <FolderIcon className="h-4 w-4 mr-2 text-yellow-600" />
          <span className="text-sm text-gray-800 truncate">{node.name}</span>
        </div>
        {isExpanded && (
          <div className="ml-2 border-l border-gray-200 pl-2">
            {node.children?.map((child) =>
              renderFileTree(child, level + 1, fullPath)
            )}
          </div>
        )}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-6">
        <div className="text-center py-12">
          <p className="text-gray-500">项目未找到</p>
        </div>
      </div>
    );
  }

  if (selectedFile && fileContent) {
    return (
      <div className="p-6">
        <FileViewer
          fileName={selectedFile.split("/").pop() || ""}
          fileContent={fileContent}
          filePath={selectedFile}
          projectRoot={decodedPath}
          onClose={() => {
            setSelectedFile(null);
            setFileContent(null);
          }}
        />
      </div>
    );
  }

  // 文件预览模式
  if (previewFile) {
    return (
      <div className="p-6">
        <div className="mb-4">
          <button
            onClick={handleClosePreview}
            className="text-blue-600 hover:text-blue-800 text-sm"
          >
            ← 返回智能对话
          </button>
        </div>
        <FileViewer
          fileName={previewFile.path.split("/").pop() || ""}
          fileContent={previewFile.content}
          filePath={previewFile.path}
          projectRoot={decodedPath}
          onClose={handleClosePreview}
        />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-8 bg-white rounded-xl shadow border border-gray-100 overflow-hidden">
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center mb-4 lg:mb-0">
              <div className="w-12 h-12 bg-white bg-opacity-20 rounded-full flex items-center justify-center mr-4">
                <FolderIcon className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">
                  {project.info?.name}
                </h1>
                <p className="text-blue-100 text-sm">{project.info?.path}</p>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleUpdateRepository}
                disabled={isUpdating}
                className="flex items-center px-4 py-2 bg-white text-blue-600 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow hover:shadow-lg border border-blue-200"
              >
                {isUpdating ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
                    更新中...
                  </>
                ) : (
                  <>
                    <ArrowPathIcon className="h-4 w-4 mr-2" />
                    更新仓库
                  </>
                )}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isDeleting}
                className="flex items-center px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow hover:shadow-lg border border-red-400"
              >
                {isDeleting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    删除中...
                  </>
                ) : (
                  <>
                    <TrashIcon className="h-4 w-4 mr-2" />
                    删除项目
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
              <div className="flex items-center mb-2">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center mr-2">
                  <FolderIcon className="h-4 w-4 text-white" />
                </div>
                <p className="text-sm font-medium text-blue-800">仓库名称</p>
              </div>
              <p className="text-lg font-bold text-blue-900 truncate">
                {project.info?.name}
              </p>
            </div>

            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
              <div className="flex items-center mb-2">
                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center mr-2">
                  <CodeBracketIcon className="h-4 w-4 text-white" />
                </div>
                <p className="text-sm font-medium text-green-800">当前分支</p>
              </div>
              <p className="text-lg font-bold text-green-900">
                {project.info?.current_branch}
              </p>
            </div>

            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
              <div className="flex items-center mb-2">
                <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center mr-2">
                  <CodeBracketIcon className="h-4 w-4 text-white" />
                </div>
                <p className="text-sm font-medium text-purple-800">提交数量</p>
              </div>
              <p className="text-lg font-bold text-purple-900">
                {project.info?.commits_count}
              </p>
            </div>

            <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg p-4 border border-orange-200">
              <div className="flex items-center mb-2">
                <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center mr-2">
                  <ArrowPathIcon className="h-4 w-4 text-white" />
                </div>
                <p className="text-sm font-medium text-orange-800">远程仓库</p>
              </div>
              <a
                href={project.info?.remote_url || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-lg font-bold text-orange-900 hover:text-orange-700 hover:underline transition-colors duration-200 overflow-hidden whitespace-nowrap text-ellipsis block"
                title={project.info?.remote_url || "无"}
              >
                {project.info?.remote_url || "无"}
              </a>
            </div>
          </div>
        </div>
      </div>

      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4 border border-gray-200">
            <div className="flex items-center mb-4">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center mr-3">
                <TrashIcon className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  确认删除项目
                </h3>
                <p className="text-sm text-gray-500">此操作不可撤销</p>
              </div>
            </div>

            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <p className="text-gray-700 mb-2">
                确定要删除{" "}
                <span className="font-semibold text-red-700">
                  {project.info?.name}
                </span>{" "}
                吗？
              </p>
              <div className="text-sm text-gray-600 space-y-1">
                <p>• 数据库记录将被永久删除</p>
                <p>• 本地文件夹将被删除</p>
                <p>• 此操作不可撤销</p>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors duration-200"
              >
                取消
              </button>
              <button
                onClick={handleDeleteProject}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors duration-200 flex items-center"
              >
                {isDeleting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    删除中...
                  </>
                ) : (
                  "确认删除"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 顶部：项目信息和快速操作 */}
      <div className="mb-8">
        <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow p-6 border border-gray-100/50">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            {/* 项目基本信息 */}
            <div className="flex-1">
              <div className="flex items-center mb-3">
                <div className="p-3 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl mr-4">
                  <FolderIcon className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
                    {project?.info?.name || "加载中..."}
                  </h1>
                  <p className="text-sm text-gray-600 mt-1">{decodedPath}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-4 mt-4">
                <div className="flex items-center px-4 py-2 bg-gradient-to-r from-blue-50/50 to-indigo-50/50 rounded-xl border border-blue-200/50">
                  <CodeBracketIcon className="h-4 w-4 text-blue-600 mr-2" />
                  <span className="text-sm font-medium text-gray-700">
                    {project?.info?.current_branch || "main"}
                  </span>
                </div>
                <div className="flex items-center px-4 py-2 bg-gradient-to-r from-green-50/50 to-emerald-50/50 rounded-xl border border-green-200/50">
                  <ArrowPathIcon className="h-4 w-4 text-green-600 mr-2" />
                  <span className="text-sm font-medium text-gray-700">
                    {project?.info?.commits_count || 0} 次提交
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 主要内容区域 */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* 左侧：项目核心信息 */}
        <div className="xl:col-span-1 space-y-6">
          {/* 文件结构 */}
          <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow hover:shadow-lg transition-all duration-300 p-5 border border-gray-100/50 hover:border-gray-200">
            <div className="flex items-center mb-4">
              <div className="p-2 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg mr-3">
                <DocumentTextIcon className="h-5 w-5 text-white" />
              </div>
              <h2 className="text-lg font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
                文件结构
              </h2>
            </div>

            {/* 文件搜索框 */}
            <div className="mb-4">
              <div className="relative">
                <input
                  type="text"
                  placeholder="搜索文件..."
                  value={searchTerm}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all duration-200"
                />
                <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
              </div>

              {/* 搜索结果 */}
              {searchTerm && searchResults.length > 0 && (
                <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-xs text-green-700 mb-1">
                    找到 {searchResults.length} 个匹配文件:
                  </p>
                  <div className="space-y-1">
                    {searchResults.slice(0, 5).map((result) => (
                      <div
                        key={result}
                        className="px-2 py-1 text-sm text-green-800 hover:bg-green-100 rounded cursor-pointer transition-colors"
                        onClick={() => handleFileClick(result)}
                      >
                        {result}
                      </div>
                    ))}
                    {searchResults.length > 5 && (
                      <p className="text-xs text-green-600 italic">
                        还有 {searchResults.length - 5} 个文件...
                      </p>
                    )}
                  </div>
                </div>
              )}

              {searchTerm && searchResults.length === 0 && (
                <div className="mt-2 p-2 bg-gray-50 border border-gray-200 rounded-lg">
                  <p className="text-xs text-gray-600">未找到匹配的文件</p>
                </div>
              )}
            </div>
            {isLoadingFile && (
              <div className="flex justify-center items-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
                <span className="ml-3 text-gray-600">加载文件结构...</span>
              </div>
            )}
            <div className="border border-gray-200 rounded-lg p-4 h-[calc(100vh-300px)] min-h-[400px] overflow-y-auto hover:border-gray-300 transition-colors">
              {project?.file_tree && renderFileTree(project.file_tree)}
            </div>
          </div>

          {/* 最近提交 */}
          <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow hover:shadow-lg transition-all duration-300 p-5 border border-gray-100/50 hover:border-gray-200">
            <div className="flex items-center mb-4">
              <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg mr-3">
                <ArrowPathIcon className="h-5 w-5 text-white" />
              </div>
              <h2 className="text-lg font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
                最近提交
              </h2>
            </div>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {project.recent_commits?.slice(0, 5).map((commit) => (
                <div
                  key={commit.hash}
                  className="bg-gradient-to-r from-blue-50/50 to-indigo-50/50 rounded-xl p-4 hover:from-blue-100/50 hover:to-indigo-100/50 transition-all duration-300 border-l-4 border-blue-500/80 backdrop-blur-sm"
                >
                  <p className="text-sm font-semibold text-gray-800 mb-2 leading-relaxed">
                    {commit.message}
                  </p>
                  <div className="flex items-center justify-between text-xs text-gray-600">
                    <span className="flex items-center">
                      <UserIcon className="h-3 w-3 mr-1" />
                      {commit.author}
                    </span>
                    <span>{commit.date}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 分支信息 */}
          <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow hover:shadow-lg transition-all duration-300 p-5 border border-gray-100/50 hover:border-gray-200">
            <div className="flex items-center mb-4">
              <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg mr-3">
                <CodeBracketIcon className="h-5 w-5 text-white" />
              </div>
              <h2 className="text-lg font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
                分支
              </h2>
            </div>
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {project.branches?.map((branch) => (
                <div
                  key={branch.name}
                  className={`flex items-center justify-between p-3 rounded-xl transition-all duration-300 backdrop-blur-sm ${
                    branch.name === project?.info?.current_branch
                      ? "bg-gradient-to-r from-purple-100/50 to-pink-100/50 border border-purple-300/50"
                      : "bg-gradient-to-r from-gray-50/50 to-gray-100/50 hover:from-gray-100/50 hover:to-gray-200/50"
                  }`}
                >
                  <div className="flex items-center">
                    <div
                      className={`w-2 h-2 rounded-full mr-3 ${
                        branch.name === project?.info?.current_branch
                          ? "bg-gradient-to-r from-purple-500 to-pink-500"
                          : "bg-gray-400"
                      }`}
                    ></div>
                    <span
                      className={`text-sm font-medium ${
                        branch.name === project?.info?.current_branch
                          ? "text-purple-800"
                          : "text-gray-700"
                      }`}
                    >
                      {branch.name}
                    </span>
                  </div>
                  {branch.name === project?.info?.current_branch && (
                    <span className="text-xs bg-gradient-to-r from-purple-500 to-pink-500 text-white px-2 py-1 rounded-full">
                      当前
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：AI对话区域 */}
        <div className="xl:col-span-2">
          <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow hover:shadow-lg transition-all duration-300 border border-gray-100/50 hover:border-gray-200 h-full flex flex-col overflow-hidden">
            {/* 标题 */}
            <div className="bg-gradient-to-r from-indigo-50/50 to-purple-50/50 px-6 py-4 border-b border-indigo-200/50">
              <div className="flex items-center">
                <div className="p-2 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-lg mr-3">
                  <ChatBubbleLeftRightIcon className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-bold bg-gradient-to-r from-indigo-800 to-purple-800 bg-clip-text text-transparent">
                    AI 智能对话
                  </h2>
                  <p className="text-xs text-gray-600">使用MCP工具增强的AI助手</p>
                </div>
              </div>
            </div>

            {/* 对话面板 */}
            <div className="flex-1 p-6 overflow-hidden">
              <div className="h-full flex flex-col">
                <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden h-[calc(100vh-280px)]">
                  <ChatPanel
                    projectPath={decodedPath}
                    fileTree={project?.file_tree}
                    onFilePreview={handleFilePreview}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

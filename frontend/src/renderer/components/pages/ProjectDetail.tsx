import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import {
  FolderIcon,
  DocumentTextIcon,
  TrashIcon,
  DocumentChartBarIcon,
  ArrowPathIcon,
  ChatBubbleLeftRightIcon,
  LightBulbIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CodeBracketIcon,
} from "@heroicons/react/24/outline";
import { api } from "../../services/api";
import { FileViewer } from "../FileViewer";
import { SmartChatPanel } from "./SmartChatPanel";

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
  const [analysisQuery, setAnalysisQuery] = useState("");
  const [analysisResult, setAnalysisResult] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  // 添加展开文件夹状态
  const [expandedFolders, setExpandedFolders] = useState<
    Record<string, boolean>
  >({});

  // 一键触发功能状态
  const [isGeneratingArchitecture, setIsGeneratingArchitecture] =
    useState(false);
  const [architectureResult, setArchitectureResult] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateResult, setUpdateResult] = useState("");
  // 智能对话模式状态
  const [analysisMode, setAnalysisMode] = useState<"simple" | "smart">(
    "simple"
  );
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

  const handleAnalyze = async () => {
    if (!analysisQuery.trim()) {
      toast.error("请输入查询内容");
      return;
    }

    const provider = localStorage.getItem("ai-provider");
    const model = localStorage.getItem("ai-model");
    const apiKey = localStorage.getItem("ai-api-key");
    const baseUrl = localStorage.getItem("ai-base-url");

    if (!provider || !model || !apiKey) {
      toast.error("请先配置AI设置");
      return;
    }

    setIsAnalyzing(true);
    try {
      const result = await api.analyzeProject(
        decodedPath,
        analysisQuery,
        provider,
        model,
        apiKey,
        baseUrl || undefined
      );
      setAnalysisResult(result.analysis);
    } catch (error) {
      toast.error("项目分析失败");
    } finally {
      setIsAnalyzing(false);
    }
  };

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
        setUpdateResult(result.message || "仓库更新成功");
        toast.success("仓库更新成功");

        // 更新成功后自动刷新页面数据
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ["project", decodedPath] });
        }, 1000);
      } else {
        setUpdateResult(result.error || "仓库更新失败");
        toast.error(result.error || "仓库更新失败");
      }
    } catch (error) {
      console.error("更新仓库失败:", error);
      setUpdateResult("更新仓库时发生错误");
      toast.error("更新仓库失败");
    } finally {
      setIsUpdating(false);
    }
  };

  // 一键生成架构文档
  const handleGenerateArchitecture = async () => {
    const provider = localStorage.getItem("ai-provider");
    const model = localStorage.getItem("ai-model");
    const apiKey = localStorage.getItem("ai-api-key");
    const baseUrl = localStorage.getItem("ai-base-url");

    if (!provider || !model || !apiKey) {
      toast.error("请先配置AI设置");
      return;
    }

    setIsGeneratingArchitecture(true);
    try {
      const result = await api.generateArchitectureDocumentation(
        decodedPath,
        provider,
        model,
        apiKey,
        baseUrl || undefined
      );
      setArchitectureResult(
        result.analysis || result.message || "架构文档生成成功"
      );
      toast.success("架构文档生成成功");

      // 生成成功后自动刷新页面数据
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["project", decodedPath] });
      }, 1000);
    } catch (error) {
      console.error("生成架构文档失败:", error);
      toast.error("生成架构文档失败");
    } finally {
      setIsGeneratingArchitecture(false);
    }
  };

  // 处理文件预览
  const handleFilePreview = (filePath: string, content: string) => {
    setPreviewFile({ path: filePath, content });
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
        <div className="mb-4">
          <button
            onClick={() => {
              setSelectedFile(null);
              setFileContent(null);
            }}
            className="text-blue-600 hover:text-blue-800 text-sm"
          >
            ← 返回文件列表
          </button>
        </div>
        <FileViewer
          fileName={selectedFile.split("/").pop() || ""}
          fileContent={fileContent}
          filePath={selectedFile}
          projectRoot={decodedPath}
          onClose={() => {
            setSelectedFile(null);
            setFileContent(null);
          }}
          onFileContentUpdate={(newContent) => setFileContent(newContent)}
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
          onFileContentUpdate={(newContent) =>
            setPreviewFile({
              ...previewFile,
              content: newContent,
            })
          }
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
                className="flex items-center px-4 py-2 bg-white text-blue-600 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg border border-blue-200"
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
                className="flex items-center px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg border border-red-400"
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
                  <DocumentChartBarIcon className="h-4 w-4 text-white" />
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow duration-300 p-6 border border-gray-100">
            <div className="flex items-center mb-4">
              <DocumentTextIcon className="h-6 w-6 text-green-600 mr-2" />
              <h2 className="text-xl font-bold text-gray-900">文件结构</h2>
            </div>
            {isLoadingFile && (
              <div className="flex justify-center items-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <span className="ml-3 text-gray-600">加载文件结构...</span>
              </div>
            )}
            <div className="border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto hover:border-gray-300 transition-colors">
              {project?.file_tree && renderFileTree(project.file_tree)}
            </div>
          </div>

          {analysisMode === "simple" ? (
            <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow duration-300 p-6 border border-gray-100">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <LightBulbIcon className="h-6 w-6 text-yellow-500 mr-2" />
                  <h2 className="text-xl font-bold text-gray-900">AI分析</h2>
                </div>
                <button
                  onClick={() => setAnalysisMode("smart")}
                  className="flex items-center px-4 py-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-lg hover:from-blue-600 hover:to-blue-700 transition-all duration-200 text-sm shadow-md hover:shadow-lg"
                >
                  <LightBulbIcon className="h-4 w-4 mr-1" />
                  切换到智能对话
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    询问关于此项目的问题
                  </label>
                  <textarea
                    value={analysisQuery}
                    onChange={(e) => setAnalysisQuery(e.target.value)}
                    placeholder="例如：这个项目的主要目的是什么？代码是如何组织的？"
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                    rows={3}
                  />
                </div>

                <button
                  onClick={handleAnalyze}
                  disabled={isAnalyzing}
                  className="w-full px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 transition-all duration-200 shadow-md hover:shadow-lg flex items-center justify-center"
                >
                  {isAnalyzing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      分析中...
                    </>
                  ) : (
                    "开始分析"
                  )}
                </button>

                {analysisResult && (
                  <div className="mt-4 p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
                    <h3 className="text-sm font-bold text-blue-900 mb-2 flex items-center">
                      <LightBulbIcon className="h-4 w-4 mr-1" />
                      分析结果
                    </h3>
                    <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                      {analysisResult}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow duration-300 p-6 border border-gray-100">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 flex items-center">
                  <ChatBubbleLeftRightIcon className="h-6 w-6 mr-2 text-purple-600" />
                  智能对话分析
                </h2>
                <button
                  onClick={() => setAnalysisMode("simple")}
                  className="flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-all duration-200 text-sm"
                >
                  ← 返回简单分析
                </button>
              </div>
              <div
                className="border-2 border-gray-200 rounded-lg hover:border-purple-300 transition-colors duration-200"
                style={{ height: "400px" }}
              >
                <SmartChatPanel
                  projectPath={decodedPath}
                  fileTree={project?.file_tree}
                  onFilePreview={handleFilePreview}
                />
              </div>
            </div>
          )}
        </div>

        <div className="space-y-6">
          {/* 一键触发功能 */}
          <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow duration-300 p-6 border border-gray-100">
            <div className="flex items-center mb-4">
              <DocumentChartBarIcon className="h-6 w-6 text-green-600 mr-2" />
              <h2 className="text-xl font-bold text-gray-900">一键功能</h2>
            </div>
            <div className="space-y-3">
              <button
                onClick={handleGenerateArchitecture}
                disabled={isGeneratingArchitecture}
                className="w-full flex items-center justify-center px-4 py-3 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg hover:from-green-700 hover:to-green-800 disabled:opacity-50 transition-all duration-200 shadow-md hover:shadow-lg"
              >
                {isGeneratingArchitecture ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    生成中...
                  </>
                ) : (
                  <>
                    <DocumentChartBarIcon className="h-5 w-5 mr-2" />
                    生成架构文档
                  </>
                )}
              </button>
            </div>

            {architectureResult && (
              <div className="mt-4 p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg border border-green-200">
                <h3 className="text-sm font-bold text-green-900 mb-2 flex items-center">
                  <DocumentChartBarIcon className="h-4 w-4 mr-1" />
                  架构文档结果
                </h3>
                <div className="text-sm text-green-700 whitespace-pre-wrap leading-relaxed">
                  {architectureResult}
                </div>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow duration-300 p-6 border border-gray-100">
            <div className="flex items-center mb-4">
              <ArrowPathIcon className="h-6 w-6 text-blue-600 mr-2" />
              <h2 className="text-xl font-bold text-gray-900">最近提交</h2>
            </div>
            <div className="space-y-3">
              {project.recent_commits?.slice(0, 5).map((commit) => (
                <div
                  key={commit.hash}
                  className="bg-gray-50 rounded-lg p-3 hover:bg-gray-100 transition-colors duration-200 border-l-4 border-blue-500"
                >
                  <p className="text-sm font-medium text-gray-900 mb-1">
                    {commit.message}
                  </p>
                  <div className="flex items-center text-xs text-gray-500">
                    <span className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-800 rounded-full mr-2">
                      {commit.author}
                    </span>
                    <span>•</span>
                    <span className="ml-2">
                      {new Date(commit.date).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow hover:shadow-xl transition-shadow duration-300 p-6 border border-gray-100">
            <div className="flex items-center mb-4">
              <CodeBracketIcon className="h-6 w-6 text-purple-600 mr-2" />
              <h2 className="text-xl font-bold text-gray-900">分支</h2>
            </div>
            <div className="space-y-3">
              {project.branches?.map((branch) => (
                <div
                  key={branch.name}
                  className={`flex items-center justify-between p-3 rounded-lg transition-all duration-200 ${
                    branch.is_active
                      ? "bg-gradient-to-r from-purple-50 to-blue-50 border-l-4 border-purple-500 shadow-sm"
                      : "bg-gray-50 hover:bg-gray-100"
                  }`}
                >
                  <div className="flex items-center">
                    <CodeBracketIcon className="h-4 w-4 mr-2 text-gray-600" />
                    <span
                      className={`text-sm font-medium ${
                        branch.is_active ? "text-purple-700" : "text-gray-700"
                      }`}
                    >
                      {branch.name}
                    </span>
                  </div>
                  {branch.is_active && (
                    <span className="inline-flex items-center px-3 py-1 bg-gradient-to-r from-purple-500 to-blue-500 text-white text-xs font-medium rounded-full shadow-sm">
                      <div className="w-2 h-2 bg-white rounded-full mr-2 animate-pulse"></div>
                      活跃
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

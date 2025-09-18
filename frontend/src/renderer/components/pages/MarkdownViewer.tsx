import React, { useState, useEffect } from "react";
import { XMarkIcon, EyeIcon, CodeBracketIcon } from "@heroicons/react/24/outline";

interface MarkdownViewerProps {
  content: string;
  title?: string;
  onClose?: () => void;
  className?: string;
}

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({
  content,
  title = "Markdown 预览",
  onClose,
  className = ""
}) => {
  const [viewMode, setViewMode] = useState<"preview" | "source">("preview");

  // 简单的Markdown转HTML函数
  const markdownToHtml = (markdown: string): string => {
    let html = markdown;

    // 处理图片
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="max-w-full h-auto rounded-lg shadow-md my-4" />');

    // 处理标题
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-bold text-gray-800 mb-3 mt-6">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold text-gray-800 mb-4 mt-6">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-gray-800 mb-4 mt-6">$1</h1>');

    // 处理粗体和斜体
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold">$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');

    // 处理代码块
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-100 rounded-lg p-4 my-4 overflow-x-auto"><code>$1</code></pre>');

    // 处理行内代码
    html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-2 py-1 rounded text-sm font-mono">$1</code>');

    // 处理链接
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">$1</a>');

    // 处理表格
    html = html.replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').slice(1, -1);
      return '<tr>' + cells.map(cell => `<td class="border border-gray-300 px-4 py-2">${cell.trim()}</td>`).join('') + '</tr>';
    });

    // 处理表格标题行
    html = html.replace(/^(\|.*\|)\n\|([-\s|]+)\|/gm, (match, headerRow) => {
      const headers = headerRow.split('|').slice(1, -1);
      const headerHtml = '<tr>' + headers.map((header: string) => `<th class="border border-gray-300 px-4 py-2 bg-gray-50 font-semibold">${header.trim()}</th>`).join('') + '</tr>';
      return '<table class="border-collapse border border-gray-300 my-4 w-full">' + headerHtml;
    });

    // 关闭表格
    html = html.replace(/(<table[^>]*>[\s\S]*?)<\/tr>/g, '$1</tr></table>');

    // 处理列表
    html = html.replace(/^\* (.*$)/gim, '<li class="ml-4 mb-1">• $1</li>');
    html = html.replace(/^\d+\. (.*$)/gim, '<li class="ml-4 mb-1">$1</li>');

    // 处理段落
    html = html.replace(/\n\n/g, '</p><p class="mb-4 leading-relaxed">');
    html = html.replace(/\n/g, '<br>');

    // 包装段落
    if (!html.startsWith('<')) {
      html = '<p class="mb-4 leading-relaxed">' + html + '</p>';
    }

    return html;
  };

  const renderPreview = () => {
    const htmlContent = markdownToHtml(content);

    return (
      <div className="prose prose-sm max-w-none">
        <div
          className="text-gray-700 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: htmlContent }}
        />
      </div>
    );
  };

  const renderSource = () => {
    return (
      <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto text-sm font-mono text-gray-800 whitespace-pre-wrap border">
        {content}
      </pre>
    );
  };

  return (
    <div className={`bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden ${className}`}>
      {/* 头部工具栏 */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-3">
          <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setViewMode("preview")}
              className={`flex items-center px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                viewMode === "preview"
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <EyeIcon className="h-4 w-4 mr-1" />
              预览
            </button>
            <button
              onClick={() => setViewMode("source")}
              className={`flex items-center px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                viewMode === "source"
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <CodeBracketIcon className="h-4 w-4 mr-1" />
              源码
            </button>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* 内容区域 */}
      <div className="p-6 max-h-96 overflow-y-auto">
        {viewMode === "preview" ? renderPreview() : renderSource()}
      </div>
    </div>
  );
};

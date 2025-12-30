"""
文件搜索工具处理器
借鉴 Cline 的 search_files 工具
"""

import os
import re
from typing import Dict, Any, List
import logging

from ..base import ToolSpec, ToolParameter, ToolContext
from ..handler import BaseToolHandler


logger = logging.getLogger(__name__)


class SearchFilesToolHandler(BaseToolHandler):
    """文件内容搜索工具处理器"""

    @property
    def name(self) -> str:
        return "search_files"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_files",
            description="使用正则表达式在文件中搜索内容",
            category="search",
            parameters={
                "pattern": ToolParameter(
                    name="pattern",
                    type="string",
                    description="搜索的正则表达式模式",
                    required=True
                ),
                "path": ToolParameter(
                    name="path",
                    type="string",
                    description="搜索路径（相对于仓库根目录，空字符串表示所有文件）",
                    required=False,
                    default=""
                ),
                "file_pattern": ToolParameter(
                    name="file_pattern",
                    type="string",
                    description="文件名模式（例如 *.py, *.js），用于过滤文件",
                    required=False,
                    default=""
                ),
                "case_sensitive": ToolParameter(
                    name="case_sensitive",
                    type="boolean",
                    description="是否区分大小写",
                    required=False,
                    default=False
                ),
                "max_results": ToolParameter(
                    name="max_results",
                    type="integer",
                    description="返回的最大结果数",
                    required=False,
                    default=50
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件搜索"""
        pattern = parameters["pattern"]
        search_path = parameters.get("path", "")
        file_pattern = parameters.get("file_pattern", "")
        case_sensitive = parameters.get("case_sensitive", False)
        max_results = parameters.get("max_results", 50)
        repo_path = context.repository_path

        # 构建搜索路径
        if search_path:
            full_search_path = os.path.join(repo_path, search_path)
        else:
            full_search_path = repo_path

        # 安全检查
        if not os.path.abspath(full_search_path).startswith(os.path.abspath(repo_path)):
            raise ValueError(f"非法搜索路径: {search_path}")

        # 编译正则表达式
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"无效的正则表达式: {e}")

        # 收集搜索结果
        results = []
        total_matches = 0

        # 确定要搜索的文件
        files_to_search = self._get_files_to_search(full_search_path, file_pattern)

        for file_path in files_to_search:
            if total_matches >= max_results:
                break

            try:
                matches = self._search_in_file(file_path, regex, repo_path, max_results - total_matches)
                if matches:
                    results.extend(matches)
                    total_matches += len(matches)
            except Exception as e:
                logger.warning(f"搜索文件失败: {file_path}, 错误: {e}")

        return {
            "pattern": pattern,
            "path": search_path or "/",
            "file_pattern": file_pattern or "*",
            "total_matches": total_matches,
            "results": results
        }

    def _get_files_to_search(self, search_path: str, file_pattern: str) -> List[str]:
        """获取要搜索的文件列表"""
        files = []

        # 常见忽略的目录和文件
        ignore_dirs = {
            '.git', '.idea', '.vscode', 'node_modules', '__pycache__',
            'venv', 'env', '.venv', 'dist', 'build', 'target', 'bin',
            'obj', '.next', '.nuxt', 'coverage'
        }

        ignore_extensions = {
            '.pyc', '.pyo', '.exe', '.dll', '.so', '.dylib',
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
            '.zip', '.tar', '.gz', '.rar', '.7z',
            '.mp3', '.mp4', '.avi', '.mov', '.pdf'
        }

        if os.path.isfile(search_path):
            return [search_path]

        for root, dirs, filenames in os.walk(search_path):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for filename in filenames:
                # 检查扩展名
                _, ext = os.path.splitext(filename)
                if ext.lower() in ignore_extensions:
                    continue

                # 检查文件名模式
                if file_pattern:
                    if not self._matches_file_pattern(filename, file_pattern):
                        continue

                file_path = os.path.join(root, filename)
                files.append(file_path)

        return files

    def _matches_file_pattern(self, filename: str, pattern: str) -> bool:
        """检查文件名是否匹配模式"""
        # 简单的通配符匹配
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)

    def _search_in_file(
        self,
        file_path: str,
        regex: re.Pattern,
        repo_path: str,
        max_matches: int
    ) -> List[Dict[str, Any]]:
        """在单个文件中搜索"""
        matches = []

        try:
            # 尝试多种编码读取
            content = None
            for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                return matches

            # 搜索匹配
            relative_path = os.path.relpath(file_path, repo_path).replace('\\', '/')

            for line_num, line in enumerate(content.split('\n'), 1):
                if len(matches) >= max_matches:
                    break

                for match in regex.finditer(line):
                    matches.append({
                        "file": relative_path,
                        "line": line_num,
                        "column": match.start() + 1,
                        "match": match.group(),
                        "context": line.strip()
                    })

        except Exception as e:
            logger.warning(f"读取文件失败: {file_path}, 错误: {e}")

        return matches

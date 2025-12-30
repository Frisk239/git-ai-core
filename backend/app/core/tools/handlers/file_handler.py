"""
文件相关工具处理器
"""

import os
from typing import Dict, Any
import logging

from ..base import ToolSpec, ToolParameter, ToolContext, ToolResult
from ..handler import BaseToolHandler

logger = logging.getLogger(__name__)


class FileReadToolHandler(BaseToolHandler):
    """文件读取工具处理器"""

    @property
    def name(self) -> str:
        return "read_file"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="read_file",
            description="读取 Git 仓库中的文件内容",
            category="file",
            parameters={
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="要读取的文件路径（相对于仓库根目录）",
                    required=True
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件读取"""
        file_path = parameters["file_path"]
        repo_path = context.repository_path

        # 构建完整文件路径
        full_path = os.path.join(repo_path, file_path)

        # 安全检查：确保文件在仓库内
        if not os.path.abspath(full_path).startswith(os.path.abspath(repo_path)):
            raise ValueError(f"非法文件路径: {file_path}")

        # 检查文件是否存在
        if not os.path.exists(full_path):
            raise ValueError(f"文件不存在: {file_path}")

        if not os.path.isfile(full_path):
            raise ValueError(f"不是文件: {file_path}")

        # 读取文件内容
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            content = None
            used_encoding = None

            for encoding in encodings:
                try:
                    with open(full_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise ValueError(f"无法解码文件: {file_path}")

            # 获取文件统计信息
            file_stats = os.stat(full_path)

            return {
                "file_path": file_path,
                "content": content,
                "size": file_stats.st_size,
                "encoding": used_encoding,
                "relative_path": file_path
            }

        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, 错误: {e}")
            raise


class FileListToolHandler(BaseToolHandler):
    """文件列表工具处理器"""

    @property
    def name(self) -> str:
        return "list_files"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_files",
            description="列出目录中的文件和子目录",
            category="file",
            parameters={
                "directory": ToolParameter(
                    name="directory",
                    type="string",
                    description="要列出的目录路径（相对于仓库根目录，空字符串表示根目录）",
                    required=False,
                    default=""
                ),
                "recursive": ToolParameter(
                    name="recursive",
                    type="boolean",
                    description="是否递归列出子目录",
                    required=False,
                    default=False
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件列表"""
        directory = parameters.get("directory", "")
        recursive = parameters.get("recursive", False)
        repo_path = context.repository_path

        # 构建完整目录路径
        full_path = os.path.join(repo_path, directory)

        # 安全检查
        if not os.path.abspath(full_path).startswith(os.path.abspath(repo_path)):
            raise ValueError(f"非法目录路径: {directory}")

        if not os.path.exists(full_path):
            raise ValueError(f"目录不存在: {directory}")

        if not os.path.isdir(full_path):
            raise ValueError(f"不是目录: {directory}")

        # 列出文件
        if recursive:
            items = self._list_directory_recursive(full_path, repo_path)
        else:
            items = self._list_directory_flat(full_path, repo_path)

        return {
            "directory": directory or "/",
            "items": items,
            "total_count": len(items)
        }

    def _list_directory_flat(self, full_path: str, repo_path: str) -> list:
        """平铺列出目录"""
        items = []
        try:
            for entry in os.listdir(full_path):
                entry_path = os.path.join(full_path, entry)
                relative_path = os.path.relpath(entry_path, repo_path)

                stat_info = os.stat(entry_path)
                items.append({
                    "name": entry,
                    "path": relative_path.replace('\\', '/'),  # 统一使用 /
                    "type": "directory" if os.path.isdir(entry_path) else "file",
                    "size": stat_info.st_size if os.path.isfile(entry_path) else 0
                })
        except PermissionError:
            logger.warning(f"无权限访问目录: {full_path}")

        return sorted(items, key=lambda x: (x["type"] == "file", x["name"]))

    def _list_directory_recursive(self, full_path: str, repo_path: str) -> list:
        """递归列出目录"""
        items = []
        try:
            for root, dirs, files in os.walk(full_path):
                # 跳过隐藏目录和常见的忽略目录
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    'node_modules', '__pycache__', 'venv', 'env', '.git',
                    'dist', 'build', 'target', 'bin', 'obj'
                }]

                for entry in files:
                    if entry.startswith('.'):
                        continue

                    entry_path = os.path.join(root, entry)
                    relative_path = os.path.relpath(entry_path, repo_path)

                    stat_info = os.stat(entry_path)
                    items.append({
                        "name": entry,
                        "path": relative_path.replace('\\', '/'),
                        "type": "file",
                        "size": stat_info.st_size
                    })

                # 也添加目录
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    relative_path = os.path.relpath(dir_path, repo_path)
                    items.append({
                        "name": d,
                        "path": relative_path.replace('\\', '/'),
                        "type": "directory",
                        "size": 0
                    })

        except PermissionError:
            logger.warning(f"无权限访问目录: {full_path}")

        return sorted(items, key=lambda x: (x["path"].count('/'), x["name"]))

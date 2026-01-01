"""
文件相关工具处理器
"""

import os
import time
from typing import Dict, Any, List, Optional
import logging

from ..base import ToolSpec, ToolParameter, ToolContext, ToolResult
from ..handler import BaseToolHandler

logger = logging.getLogger(__name__)


# list_files 工具的缓存
_list_cache = {}
_cache_max_size = 50
_cache_ttl = 180  # 3分钟


def _get_list_cache_key(directory: str, recursive: bool, max_depth: int) -> str:
    """生成缓存键"""
    return f"{directory}:{recursive}:{max_depth}"


def _get_list_from_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """从缓存获取结果"""
    if cache_key in _list_cache:
        result, timestamp = _list_cache[cache_key]
        if time.time() - timestamp < _cache_ttl:
            return result
        else:
            del _list_cache[cache_key]
    return None


def _set_list_cache(cache_key: str, result: Dict[str, Any]) -> None:
    """设置缓存"""
    if len(_list_cache) >= _cache_max_size:
        # LRU淘汰：删除最旧的缓存
        oldest_key = min(_list_cache.keys(), key=lambda k: _list_cache[k][1])
        del _list_cache[oldest_key]
    _list_cache[cache_key] = (result, time.time())


class FileReadToolHandler(BaseToolHandler):
    """文件读取工具处理器"""

    @property
    def name(self) -> str:
        return "read_file"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="read_file",
            description="读取 Git 仓库中的文件内容。支持大文件截断、多编码检测。",
            category="file",
            parameters={
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="要读取的文件路径（相对于仓库根目录）",
                    required=True
                ),
                "max_size": ToolParameter(
                    name="max_size",
                    type="integer",
                    description="最大读取字节数（0表示不限制，默认100KB）",
                    required=False,
                    default=100_000
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件读取 - 优化版本"""
        file_path = parameters["file_path"]
        max_size = parameters.get("max_size", 100_000)
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

        # 文件大小检查
        file_stats = os.stat(full_path)
        file_size = file_stats.st_size

        # 如果文件过大，给出警告并截断
        is_truncated = False
        if max_size > 0 and file_size > max_size:
            logger.warning(f"文件过大，将截断读取: {file_path} ({file_size} bytes > {max_size} bytes)")
            is_truncated = True

        # 读取文件内容
        try:
            # 优化编码检测顺序
            encodings = ['utf-8', 'latin-1']
            content = None
            used_encoding = None

            for encoding in encodings:
                try:
                    with open(full_path, 'r', encoding=encoding) as f:
                        if max_size > 0 and file_size > max_size:
                            # 只读取指定字节数
                            content = f.read(max_size)
                        else:
                            content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise ValueError(f"无法解码文件: {file_path}")

            return {
                "file_path": file_path,
                "content": content,
                "size": file_stats.st_size,
                "encoding": used_encoding,
                "relative_path": file_path,
                "truncated": is_truncated,
                "truncated_size": max_size if is_truncated else None
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
            description="列出目录中的文件和子目录。支持深度限制、缓存、性能统计。",
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
                ),
                "max_depth": ToolParameter(
                    name="max_depth",
                    type="integer",
                    description="递归最大深度（0表示不限制，默认10）",
                    required=False,
                    default=10
                ),
                "max_results": ToolParameter(
                    name="max_results",
                    type="integer",
                    description="返回的最大结果数（0表示不限制，默认1000）",
                    required=False,
                    default=1000
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件列表 - 优化版本"""
        directory = parameters.get("directory", "")
        recursive = parameters.get("recursive", False)
        max_depth = parameters.get("max_depth", 10)
        max_results = parameters.get("max_results", 1000)
        repo_path = context.repository_path

        # 检查缓存
        cache_key = _get_list_cache_key(directory, recursive, max_depth)
        cached_result = _get_list_from_cache(cache_key)
        if cached_result:
            logger.info(f"使用缓存列表结果: {directory}")
            return cached_result

        # 开始计时
        start_time = time.time()

        # 标准化路径输入 - 支持 "/"、""、"." 表示根目录
        if not directory or directory in ["/", ".", "./"]:
            full_path = repo_path
        else:
            # 移除前导的 "/" 或 "./"
            normalized_dir = directory.lstrip("/").lstrip("./")
            full_path = os.path.join(repo_path, normalized_dir)

        # 安全检查
        try:
            abs_path = os.path.abspath(full_path)
            abs_repo = os.path.abspath(repo_path)
            if not abs_path.startswith(abs_repo):
                raise ValueError(f"非法目录路径: {directory}")
        except Exception as e:
            raise ValueError(f"路径验证失败: {e}")

        if not os.path.exists(full_path):
            raise ValueError(f"目录不存在: {directory}")

        if not os.path.isdir(full_path):
            raise ValueError(f"不是目录: {directory}")

        # 列出文件
        if recursive:
            items = self._list_directory_recursive(
                full_path,
                repo_path,
                max_depth=max_depth,
                max_results=max_results
            )
        else:
            items = self._list_directory_flat(full_path, repo_path, max_results=max_results)

        # 计算耗时
        elapsed_time = (time.time() - start_time) * 1000  # 转换为毫秒

        # 构建结果
        result = {
            "directory": directory or "/",
            "items": items,
            "total_count": len(items),
            "performance": {
                "time_ms": round(elapsed_time, 2),
                "truncated": len(items) >= max_results if max_results > 0 else False
            }
        }

        # 缓存结果
        _set_list_cache(cache_key, result)

        return result

    def _list_directory_flat(self, full_path: str, repo_path: str, max_results: int = 1000) -> list:
        """平铺列出目录"""
        items = []
        try:
            for entry in os.listdir(full_path):
                if max_results > 0 and len(items) >= max_results:
                    break

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

    def _list_directory_recursive(
        self,
        full_path: str,
        repo_path: str,
        max_depth: int = 10,
        max_results: int = 1000
    ) -> list:
        """递归列出目录 - 支持深度限制"""
        items = []
        base_depth = full_path.count(os.sep)

        try:
            for root, dirs, files in os.walk(full_path):
                # 检查深度限制
                current_depth = root.count(os.sep) - base_depth
                if max_depth > 0 and current_depth >= max_depth:
                    # 清空dirs列表以停止向下遍历
                    dirs[:] = []
                    continue

                # 跳过隐藏目录和常见的忽略目录
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    'node_modules', '__pycache__', 'venv', 'env', '.git',
                    'dist', 'build', 'target', 'bin', 'obj', '.next',
                    '.nuxt', 'coverage', '.vscode', '.idea'
                }]

                # 添加文件
                for entry in files:
                    if max_results > 0 and len(items) >= max_results:
                        return items  # 提前返回

                    if entry.startswith('.'):
                        continue

                    entry_path = os.path.join(root, entry)
                    relative_path = os.path.relpath(entry_path, repo_path)

                    try:
                        stat_info = os.stat(entry_path)
                        items.append({
                            "name": entry,
                            "path": relative_path.replace('\\', '/'),
                            "type": "file",
                            "size": stat_info.st_size
                        })
                    except (OSError, PermissionError):
                        continue

                # 添加目录
                for d in dirs:
                    if max_results > 0 and len(items) >= max_results:
                        return items  # 提前返回

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

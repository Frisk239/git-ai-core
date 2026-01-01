"""
文件搜索工具处理器
借鉴 Cline 的 search_files 工具
优化版本：添加缓存、并发搜索、性能统计
"""

import os
import re
import time
import asyncio
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

from ..base import ToolSpec, ToolParameter, ToolContext
from ..handler import BaseToolHandler


logger = logging.getLogger(__name__)


# 简单的内存缓存
_search_cache = {}
_cache_max_size = 100
_cache_ttl = 300  # 5分钟


def _get_cache_key(pattern: str, path: str, file_pattern: str, case_sensitive: bool) -> str:
    """生成缓存键"""
    return f"{pattern}:{path}:{file_pattern}:{case_sensitive}"


def _get_from_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """从缓存获取结果"""
    if cache_key in _search_cache:
        result, timestamp = _search_cache[cache_key]
        if time.time() - timestamp < _cache_ttl:
            return result
        else:
            del _search_cache[cache_key]
    return None


def _set_cache(cache_key: str, result: Dict[str, Any]) -> None:
    """设置缓存"""
    if len(_search_cache) >= _cache_max_size:
        # LRU淘汰：删除最旧的缓存
        oldest_key = min(_search_cache.keys(), key=lambda k: _search_cache[k][1])
        del _search_cache[oldest_key]
    _search_cache[cache_key] = (result, time.time())


class SearchFilesToolHandler(BaseToolHandler):
    """文件内容搜索工具处理器 - 支持并发搜索"""

    def __init__(self):
        super().__init__()
        # 线程池用于并发搜索（4个并发工作线程）
        self._executor = ThreadPoolExecutor(max_workers=4)

    @property
    def name(self) -> str:
        return "search_files"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_files",
            description="使用正则表达式在文件中高效搜索内容。支持缓存、性能统计。",
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
        """执行文件搜索 - 并发优化版本"""
        pattern = parameters["pattern"]
        search_path = parameters.get("path", "")
        file_pattern = parameters.get("file_pattern", "")
        case_sensitive = parameters.get("case_sensitive", False)
        max_results = parameters.get("max_results", 50)
        repo_path = context.repository_path

        # 构建搜索路径 - 标准化路径输入
        if not search_path or search_path in ["/", ".", "./"]:
            full_search_path = repo_path
        else:
            normalized_path = search_path.lstrip("/").lstrip("./")
            full_search_path = os.path.join(repo_path, normalized_path)

        # 安全检查
        try:
            abs_search = os.path.abspath(full_search_path)
            abs_repo = os.path.abspath(repo_path)
            if not abs_search.startswith(abs_repo):
                raise ValueError(f"非法搜索路径: {search_path}")
        except Exception as e:
            raise ValueError(f"路径验证失败: {e}")

        # 编译正则表达式
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"无效的正则表达式: {e}")

        # 检查缓存
        cache_key = _get_cache_key(pattern, search_path, file_pattern, case_sensitive)
        cached_result = _get_from_cache(cache_key)
        if cached_result:
            logger.info(f"使用缓存搜索结果: {pattern}")
            return cached_result

        # 开始计时
        start_time = time.time()

        # 确定要搜索的文件
        files_to_search = self._get_files_to_search(full_search_path, file_pattern)

        # 限制搜索文件数量
        max_files = 100
        files_to_search = files_to_search[:max_files]

        # 并发搜索文件
        results = []
        total_matches = 0
        files_scanned = 0

        # 使用线程池并发搜索
        loop = asyncio.get_event_loop()

        # 创建搜索任务
        tasks = [
            loop.run_in_executor(
                self._executor,
                self._search_in_file,
                file_path,
                regex,
                repo_path,
                min(10, max_results)  # 每个文件最多10个结果
            )
            for file_path in files_to_search
        ]

        # 等待所有任务完成（使用 gather 以支持并发）
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for matches in completed_tasks:
            if total_matches >= max_results:
                break

            if isinstance(matches, Exception):
                # 忽略单个文件的错误
                continue

            if matches:
                results.extend(matches)
                total_matches += len(matches)
                files_scanned += 1

        # 计算搜索时间
        search_time = (time.time() - start_time) * 1000  # 转换为毫秒

        # 构建结果
        result = {
            "pattern": pattern,
            "path": search_path or "/",
            "file_pattern": file_pattern or "*",
            "total_matches": total_matches,
            "results": results[:max_results],
            "performance": {
                "files_scanned": files_scanned,
                "files_total": len(files_to_search),
                "search_time_ms": round(search_time, 2),
                "concurrent": True,
                "concurrency": 4
            }
        }

        # 缓存结果
        _set_cache(cache_key, result)

        return result

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
        """在单个文件中搜索 - 优化版本"""
        matches = []

        try:
            # 文件大小检查：跳过过大的文件（>1MB）
            file_size = os.path.getsize(file_path)
            if file_size > 1_000_000:
                logger.debug(f"跳过过大文件: {file_path} ({file_size} bytes)")
                return matches

            # 优化编码检测：优先 UTF-8，失败后尝试其他编码
            content = None

            for encoding in ['utf-8', 'latin-1']:
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

            # 优化：逐行搜索，提前退出
            for line_num, line in enumerate(content.split('\n'), 1):
                if len(matches) >= max_matches:
                    break

                # 快速预检查：避免不必要的正则匹配
                if not regex.search(line):
                    continue

                # 精确匹配位置
                for match in regex.finditer(line):
                    matches.append({
                        "file": relative_path,
                        "line": line_num,
                        "column": match.start() + 1,
                        "match": match.group(),
                        "context": line.strip()
                    })

                    if len(matches) >= max_matches:
                        break

        except Exception as e:
            logger.warning(f"读取文件失败: {file_path}, 错误: {e}")

        return matches

    def __del__(self):
        """清理资源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)

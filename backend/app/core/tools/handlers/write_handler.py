"""
文件写入工具处理器
借鉴 Cline 的 write_to_file 工具
"""

import os
from typing import Dict, Any
import logging

from ..base import ToolSpec, ToolParameter, ToolContext
from ..handler import BaseToolHandler


logger = logging.getLogger(__name__)


class WriteToFileToolHandler(BaseToolHandler):
    """写入文件工具处理器"""

    @property
    def name(self) -> str:
        return "write_to_file"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="write_to_file",
            description="写入或创建文件，自动创建所需的目录",
            category="file",
            parameters={
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="要写入的文件路径（相对于仓库根目录）",
                    required=True
                ),
                "content": ToolParameter(
                    name="content",
                    type="string",
                    description="要写入的内容",
                    required=True
                ),
                "create_directories": ToolParameter(
                    name="create_directories",
                    type="boolean",
                    description="是否自动创建所需的目录",
                    required=False,
                    default=True
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件写入"""
        file_path = parameters["file_path"]
        content = parameters["content"]
        create_directories = parameters.get("create_directories", True)
        repo_path = context.repository_path

        # 构建完整文件路径
        full_path = os.path.join(repo_path, file_path)

        # 安全检查：确保文件在仓库内
        if not os.path.abspath(full_path).startswith(os.path.abspath(repo_path)):
            raise ValueError(f"非法文件路径: {file_path}")

        # 如果文件已存在，读取旧内容用于对比
        old_content = None
        if os.path.exists(full_path):
            try:
                for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                    try:
                        with open(full_path, 'r', encoding=encoding) as f:
                            old_content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
            except Exception as e:
                logger.warning(f"读取现有文件失败: {e}")

        # 创建所需目录
        if create_directories:
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"创建目录: {directory}")

        # 写入文件
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # 获取文件统计信息
            file_stats = os.stat(full_path)

            return {
                "file_path": file_path,
                "action": "created" if old_content is None else "updated",
                "size": file_stats.st_size,
                "old_size": len(old_content) if old_content else 0,
                "new_size": len(content),
                "relative_path": file_path
            }

        except Exception as e:
            logger.error(f"写入文件失败: {file_path}, 错误: {e}")
            raise


class ReplaceInFileToolHandler(BaseToolHandler):
    """文件内容替换工具处理器 - 使用 SEARCH/REPLACE 块"""

    @property
    def name(self) -> str:
        return "replace_in_file"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="replace_in_file",
            description="使用 SEARCH/REPLACE 块精确替换文件内容",
            category="file",
            parameters={
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="要修改的文件路径（相对于仓库根目录）",
                    required=True
                ),
                "search": ToolParameter(
                    name="search",
                    type="string",
                    description="要搜索的内容",
                    required=True
                ),
                "replace": ToolParameter(
                    name="replace",
                    type="string",
                    description="替换后的内容",
                    required=True
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件内容替换"""
        file_path = parameters["file_path"]
        search_text = parameters["search"]
        replace_text = parameters["replace"]
        repo_path = context.repository_path

        # 构建完整文件路径
        full_path = os.path.join(repo_path, file_path)

        # 安全检查
        if not os.path.abspath(full_path).startswith(os.path.abspath(repo_path)):
            raise ValueError(f"非法文件路径: {file_path}")

        if not os.path.exists(full_path):
            raise ValueError(f"文件不存在: {file_path}")

        # 读取文件内容
        content = None
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(full_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise ValueError(f"无法解码文件: {file_path}")

        # 检查搜索内容是否存在
        if search_text not in content:
            # 尝试忽略空格差异
            normalized_content = content.strip()
            normalized_search = search_text.strip()
            if normalized_search not in normalized_content:
                raise ValueError(f"搜索内容在文件中未找到")

        # 执行替换
        new_content = content.replace(search_text, replace_text)

        # 检查替换次数（避免意外多次替换）
        replace_count = content.count(search_text)
        if replace_count > 1:
            logger.warning(f"警告: 搜索内容出现了 {replace_count} 次，全部已替换")

        # 写入文件
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return {
                "file_path": file_path,
                "replacements": replace_count,
                "old_size": len(content),
                "new_size": len(new_content),
                "size_change": len(new_content) - len(content),
                "relative_path": file_path
            }

        except Exception as e:
            logger.error(f"替换文件内容失败: {file_path}, 错误: {e}")
            raise

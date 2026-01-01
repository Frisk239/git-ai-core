"""
文件写入工具处理器
借鉴 Cline 的 write_to_file 和 replace_in_file 工具
"""

import os
import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import logging

from ..base import ToolSpec, ToolParameter, ToolContext
from ..handler import BaseToolHandler


logger = logging.getLogger(__name__)


# SEARCH/REPLACE 块标记（Cline 兼容格式）
SEARCH_BLOCK_START = "------- SEARCH"
SEARCH_BLOCK_END = "======="
REPLACE_BLOCK_END = "+++++++ REPLACE"

# 正则表达式匹配标记（支持变体，如 "--- SEARCH" 或 "------- SEARCH"）
SEARCH_BLOCK_START_REGEX = re.compile(r'^[-]{3,}\s*SEARCH\s*?$')
SEARCH_BLOCK_END_REGEX = re.compile(r'^[=]{3,}$')
REPLACE_BLOCK_END_REGEX = re.compile(r'^[+]{3,}\s*REPLACE\s*?$')


@dataclass
class DiffBlock:
    """SEARCH/REPLACE 块"""
    search_content: str
    replace_content: str
    search_line_start: int = -1
    replace_line_start: int = -1


@dataclass
class DiffStats:
    """Diff 统计信息"""
    blocks_processed: int
    lines_added: int
    lines_removed: int
    lines_changed: int
    bytes_added: int
    bytes_removed: int


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
    """
    文件内容替换工具处理器 - 使用 Cline 兼容的 SEARCH/REPLACE 块格式

    支持标准化的 SEARCH/REPLACE 块格式：
    ------- SEARCH
    [exact content to find]
    =======
    [new content to replace with]
    +++++++ REPLACE

    特性：
    - 多块批量替换
    - 智能匹配（精确匹配、行修剪匹配、块锚定匹配）
    - 详细的 diff 统计
    - 冲突检测
    """

    @property
    def name(self) -> str:
        return "replace_in_file"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="replace_in_file",
            description=(
                "使用 SEARCH/REPLACE 块精确替换文件内容。"
                "支持多个 SEARCH/REPLACE 块批量替换。"
            ),
            category="file",
            parameters={
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="要修改的文件路径（相对于仓库根目录）",
                    required=True
                ),
                "diff": ToolParameter(
                    name="diff",
                    type="string",
                    description=(
                        "一个或多个 SEARCH/REPLACE 块。格式：\n"
                        "------- SEARCH\n"
                        "[exact content to find]\n"
                        "=======\n"
                        "[new content to replace with]\n"
                        "+++++++ REPLACE\n\n"
                        "关键规则：\n"
                        "1. SEARCH 内容必须精确匹配（包括空格、缩进、换行）\n"
                        "2. 每个 SEARCH/REPLACE 块只替换第一个匹配项\n"
                        "3. 使用多个块进行多次更改，按文件中出现的顺序排列\n"
                        "4. 保持块简洁，只包含需要更改的行"
                    ),
                    required=True
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行文件内容替换"""
        file_path = parameters["file_path"]
        diff_content = parameters["diff"]
        repo_path = context.repository_path

        # 构建完整文件路径
        full_path = os.path.join(repo_path, file_path)

        # 安全检查
        if not os.path.abspath(full_path).startswith(os.path.abspath(repo_path)):
            raise ValueError(f"非法文件路径: {file_path}")

        if not os.path.exists(full_path):
            raise ValueError(f"文件不存在: {file_path}")

        # 读取文件内容
        content = self._read_file_with_encoding(full_path)
        if content is None:
            raise ValueError(f"无法解码文件: {file_path}")

        # 解析 SEARCH/REPLACE 块
        diff_blocks = self._parse_diff_blocks(diff_content)

        if not diff_blocks:
            raise ValueError("未找到有效的 SEARCH/REPLACE 块。请确保格式正确。")

        logger.info(f"解析到 {len(diff_blocks)} 个 SEARCH/REPLACE 块")

        # 应用替换
        try:
            new_content, stats = self._apply_replacements(content, diff_blocks, file_path)
        except ValueError as e:
            logger.error(f"替换失败: {e}")
            raise

        # 检查是否有实际变更
        if new_content == content:
            return {
                "file_path": file_path,
                "success": True,
                "changed": False,
                "message": "未检测到任何变更",
                "stats": {
                    "blocks_processed": stats.blocks_processed,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "lines_changed": 0
                }
            }

        # 写入文件
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            logger.error(f"写入文件失败: {file_path}, 错误: {e}")
            raise

        return {
            "file_path": file_path,
            "success": True,
            "changed": True,
            "old_size": len(content),
            "new_size": len(new_content),
            "size_change": len(new_content) - len(content),
            "relative_path": file_path,
            "stats": {
                "blocks_processed": stats.blocks_processed,
                "lines_added": stats.lines_added,
                "lines_removed": stats.lines_removed,
                "lines_changed": stats.lines_changed,
                "bytes_added": stats.bytes_added,
                "bytes_removed": stats.bytes_removed
            }
        }

    def _read_file_with_encoding(self, file_path: str) -> Optional[str]:
        """使用多种编码读取文件"""
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return None

    def _parse_diff_blocks(self, diff_content: str) -> List[DiffBlock]:
        """解析 SEARCH/REPLACE 块"""
        blocks = []
        lines = diff_content.split('\n')

        current_search = []
        current_replace = []
        in_search = False
        in_replace = False
        search_line_start = -1
        replace_line_start = -1

        for line_num, line in enumerate(lines, 1):
            # 检查 SEARCH 块开始
            if SEARCH_BLOCK_START_REGEX.match(line):
                in_search = True
                in_replace = False
                search_line_start = line_num + 1
                current_search = []
                current_replace = []
                continue

            # 检查 SEARCH 块结束（REPLACE 块开始）
            if SEARCH_BLOCK_END_REGEX.match(line) and in_search:
                in_search = False
                in_replace = True
                replace_line_start = line_num + 1
                continue

            # 检查 REPLACE 块结束
            if REPLACE_BLOCK_END_REGEX.match(line) and in_replace:
                in_replace = False
                # 保存当前块
                blocks.append(DiffBlock(
                    search_content='\n'.join(current_search),
                    replace_content='\n'.join(current_replace),
                    search_line_start=search_line_start,
                    replace_line_start=replace_line_start
                ))
                continue

            # 收集内容
            if in_search:
                current_search.append(line)
            elif in_replace:
                current_replace.append(line)

        # 处理最后一个块（如果没有结束标记）
        if in_replace and current_search:
            blocks.append(DiffBlock(
                search_content='\n'.join(current_search),
                replace_content='\n'.join(current_replace),
                search_line_start=search_line_start,
                replace_line_start=replace_line_start
            ))

        return blocks

    def _apply_replacements(
        self,
        content: str,
        diff_blocks: List[DiffBlock],
        file_path: str
    ) -> Tuple[str, DiffStats]:
        """应用所有替换块"""
        result = content
        last_processed_index = 0
        stats = DiffStats(
            blocks_processed=0,
            lines_added=0,
            lines_removed=0,
            lines_changed=0,
            bytes_added=0,
            bytes_removed=0
        )

        for block_idx, block in enumerate(diff_blocks, 1):
            search_content = block.search_content
            replace_content = block.replace_content

            logger.info(f"处理块 {block_idx}/{len(diff_blocks)}")

            # 尝试匹配搜索内容
            match_start, match_end = self._find_match(
                result, search_content, last_processed_index
            )

            if match_start == -1:
                # 匹配失败，提供详细错误信息
                search_preview = search_content[:200] + "..." if len(search_content) > 200 else search_content
                raise ValueError(
                    f"SEARCH 块 {block_idx} 未找到匹配项\n"
                    f"搜索内容预览:\n{search_preview}\n"
                    f"文件: {file_path}\n"
                    f"位置: 第 {block.search_line_start} 行\n\n"
                    f"提示：确保 SEARCH 内容精确匹配文件内容（包括空格和缩进）"
                )

            # 统计
            search_lines = search_content.count('\n') + 1
            replace_lines = replace_content.count('\n') + 1 if replace_content else 0

            stats.lines_removed += search_lines
            stats.lines_added += replace_lines
            stats.bytes_removed += len(search_content)
            stats.bytes_added += len(replace_content)
            stats.lines_changed += max(search_lines, replace_lines)

            # 执行替换
            result = (
                result[:match_start] +
                replace_content +
                result[match_end:]
            )

            # 更新处理位置
            last_processed_index = match_start + len(replace_content)
            stats.blocks_processed += 1

            logger.info(f"块 {block_idx} 替换成功: "
                       f"删除 {search_lines} 行, 添加 {replace_lines} 行")

        return result, stats

    def _find_match(
        self,
        content: str,
        search_content: str,
        start_index: int
    ) -> Tuple[int, int]:
        """
        查找搜索内容的匹配位置

        匹配策略（按优先级）:
        1. 精确匹配
        2. 行修剪匹配（忽略每行首尾空格）
        3. 块锚定匹配（使用首尾行作为锚点）

        返回: (match_start, match_end) 或 (-1, -1)
        """

        # 策略 1: 精确匹配
        exact_index = content.find(search_content, start_index)
        if exact_index != -1:
            return exact_index, exact_index + len(search_content)

        # 策略 2: 行修剪匹配
        line_match = self._line_trimmed_match(content, search_content, start_index)
        if line_match:
            return line_match

        # 策略 3: 块锚定匹配（仅对3行以上的块）
        search_lines = search_content.split('\n')
        if len(search_lines) >= 3:
            block_match = self._block_anchor_match(content, search_content, start_index)
            if block_match:
                return block_match

        # 所有策略都失败
        return -1, -1

    def _line_trimmed_match(
        self,
        content: str,
        search_content: str,
        start_index: int
    ) -> Optional[Tuple[int, int]]:
        """行修剪匹配 - 忽略每行首尾空格"""
        content_lines = content.split('\n')
        search_lines = search_content.split('\n')

        # 移除末尾空行
        if search_lines and search_lines[-1] == '':
            search_lines.pop()

        # 找到 start_index 对应的行号
        current_pos = 0
        start_line = 0
        for i, line in enumerate(content_lines):
            current_pos += len(line) + 1  # +1 for '\n'
            if current_pos > start_index:
                start_line = i
                break

        # 尝试匹配
        for i in range(start_line, len(content_lines) - len(search_lines) + 1):
            match = True
            for j in range(len(search_lines)):
                content_trimmed = content_lines[i + j].strip()
                search_trimmed = search_lines[j].strip()
                if content_trimmed != search_trimmed:
                    match = False
                    break

            if match:
                # 计算精确位置
                match_start = 0
                for k in range(i):
                    match_start += len(content_lines[k]) + 1

                match_end = match_start
                for k in range(len(search_lines)):
                    match_end += len(content_lines[i + k]) + 1

                return match_start, match_end

        return None

    def _block_anchor_match(
        self,
        content: str,
        search_content: str,
        start_index: int
    ) -> Optional[Tuple[int, int]]:
        """
        块锚定匹配 - 使用首尾行作为锚点

        适用于 3 行以上的块，通过匹配首尾行来定位块
        """
        content_lines = content.split('\n')
        search_lines = search_content.split('\n')

        if len(search_lines) < 3:
            return None

        # 移除末尾空行
        if search_lines[-1] == '':
            search_lines.pop()

        first_line_search = search_lines[0].strip()
        last_line_search = search_lines[-1].strip()
        block_size = len(search_lines)

        # 找到 start_index 对应的行号
        current_pos = 0
        start_line = 0
        for i, line in enumerate(content_lines):
            current_pos += len(line) + 1
            if current_pos > start_index:
                start_line = i
                break

        # 查找匹配首尾行的块
        for i in range(start_line, len(content_lines) - block_size + 1):
            if content_lines[i].strip() != first_line_search:
                continue

            if content_lines[i + block_size - 1].strip() != last_line_search:
                continue

            # 找到匹配，计算精确位置
            match_start = 0
            for k in range(i):
                match_start += len(content_lines[k]) + 1

            match_end = match_start
            for k in range(block_size):
                match_end += len(content_lines[i + k]) + 1

            return match_start, match_end

        return None

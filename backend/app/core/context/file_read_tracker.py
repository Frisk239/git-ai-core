"""
文件读取历史追踪器

参考 Cline 的 ContextManager 实现：
- 检测重复的文件读取
- 将重复读取替换为简短提示
- 保留最新的文件读取内容
"""

import re
import logging
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class FileReadTracker:
    """
    文件读取追踪器

    追踪所有文件读取操作，识别重复读取，并提供优化建议
    """

    # 重复文件读取的提示文本（参考 Cline）
    DUPLICATE_FILE_READ_NOTICE = (
        "[NOTE] 此文件读取已被移除以节省上下文窗口空间。"
        "请参考最新的文件读取以获取此文件的最新版本。"
    )

    def __init__(self):
        # {file_path: [(message_index, content_index, original_length)]}
        self.file_read_history: Dict[str, List[Tuple[int, int, int]]] = defaultdict(list)

    def record_file_read(
        self,
        file_path: str,
        message_index: int,
        content_index: int,
        content_length: int
    ):
        """
        记录文件读取

        Args:
            file_path: 文件路径
            message_index: 在消息列表中的索引
            content_index: 在消息内容中的索引
            content_length: 内容长度
        """
        self.file_read_history[file_path].append((message_index, content_index, content_length))
        logger.debug(f"记录文件读取: {file_path} (索引: {message_index}, 长度: {content_length})")

    def get_duplicate_file_reads(self) -> Dict[str, List[Tuple[int, int, int]]]:
        """
        获取所有重复的文件读取（出现次数 > 1）

        Returns:
            {file_path: [(message_index, content_index, length), ...]}
        """
        duplicates = {
            path: indices
            for path, indices in self.file_read_history.items()
            if len(indices) > 1
        }
        return duplicates

    def calculate_savings(self) -> Dict[str, Any]:
        """
        计算如果替换重复读取能节省的字符数

        Returns:
            {
                "total_savings": 总节省字符数,
                "file_count": 涉及的文件数量,
                "read_count": 涉及的读取次数,
                "files": {file_path: savings}
            }
        """
        duplicates = self.get_duplicate_file_reads()
        total_savings = 0
        total_reads = 0
        file_details = {}

        for file_path, indices in duplicates.items():
            # 保留最后一次读取，替换之前的所有读取
            # 只替换 indices[:-1]，保留 indices[-1]
            file_savings = sum(length for _, _, length in indices[:-1])

            # 替换为提示文本的长度
            notice_length = len(self.DUPLICATE_FILE_READ_NOTICE)
            replacement_cost = notice_length * (len(indices) - 1)

            actual_savings = max(0, file_savings - replacement_cost)

            total_savings += actual_savings
            total_reads += len(indices)

            file_details[file_path] = {
                "read_count": len(indices),
                "savings": actual_savings,
                "original_size": sum(length for _, _, length in indices),
                "indices": [idx for idx, _, _ in indices]
            }

        return {
            "total_savings": total_savings,
            "file_count": len(duplicates),
            "read_count": total_reads,
            "files": file_details
        }

    def should_optimize(self, threshold_savings: int = 5000) -> bool:
        """
        判断是否应该进行优化

        Args:
            threshold_savings: 节省字符数阈值

        Returns:
            是否应该优化
        """
        savings = self.calculate_savings()
        return savings["total_savings"] >= threshold_savings

    def reset(self):
        """重置追踪器"""
        self.file_read_history.clear()

    def get_optimization_report(self) -> str:
        """获取优化报告（用于日志）"""
        savings = self.calculate_savings()

        if savings["file_count"] == 0:
            return "没有检测到重复的文件读取"

        lines = [
            f"\n📊 文件读取优化分析:",
            f"   - 重复读取的文件: {savings['file_count']} 个",
            f"   - 总读取次数: {savings['read_count']} 次",
            f"   - 可节省字符数: {savings['total_savings']:,} 字符",
            f"\n   详细信息:"
        ]

        for file_path, details in savings["files"].items():
            lines.append(
                f"   - {file_path}:"
                f" 读取 {details['read_count']} 次, "
                f"可节省 {details['savings']:,} 字符"
            )

        return "\n".join(lines)


def extract_file_reads_from_messages(
    messages: List[Dict[str, Any]]
) -> List[Tuple[str, int, int, int]]:
    """
    从消息列表中提取所有文件读取

    Args:
        messages: 消息列表

    Returns:
        [(file_path, message_index, content_index, content_length), ...]
    """
    file_reads = []

    # 文件读取的模式（从工具结果中提取）
    # 格式1: [read_file for 'path/to/file'] Result: content
    pattern1 = r"\[read_file\s+for\s+'([^']+)'\]\s+Result:"

    # 格式2: <file_content path="path/to/file">content</file_content>
    pattern2 = r'<file_content\s+path="([^"]+)">'

    for msg_idx, message in enumerate(messages):
        if message.get("role") != "user":
            continue

        content = message.get("content", "")
        if not isinstance(content, str):
            continue

        # 尝试匹配格式1
        match1 = re.match(pattern1, content)
        if match1:
            file_path = match1.group(1)
            content_length = len(content)
            file_reads.append((file_path, msg_idx, 0, content_length))
            continue

        # 尝试匹配格式2
        match2 = re.search(pattern2, content)
        if match2:
            file_path = match2.group(1)
            content_length = len(content)
            file_reads.append((file_path, msg_idx, 0, content_length))

    return file_reads


def replace_duplicate_file_reads(
    messages: List[Dict[str, Any]],
    tracker: FileReadTracker
) -> List[Dict[str, Any]]:
    """
    替换重复的文件读取为简短提示

    Args:
        messages: 原始消息列表
        tracker: 文件读取追踪器

    Returns:
        优化后的消息列表
    """
    duplicates = tracker.get_duplicate_file_reads()

    if not duplicates:
        return messages

    # 创建消息副本（深拷贝）
    import copy
    optimized_messages = copy.deepcopy(messages)

    for file_path, indices in duplicates.items():
        # 保留最后一次读取，替换之前的所有读取
        for msg_idx, content_idx, _ in indices[:-1]:
            if msg_idx < len(optimized_messages):
                message = optimized_messages[msg_idx]

                # 替换为提示文本
                if message.get("role") == "user":
                    content = message.get("content", "")

                    # 格式1: [read_file for 'path'] Result: content
                    pattern1 = rf"\[read_file\s+for\s+'{re.escape(file_path)}'\]\s+Result:.*"
                    replacement1 = f"[read_file for '{file_path}'] Result:\n{tracker.DUPLICATE_FILE_READ_NOTICE}"

                    # 格式2: <file_content path="path">content</file_content>
                    pattern2 = rf'<file_content\s+path="{re.escape(file_path)}">[\s\S]*?</file_content>'
                    replacement2 = f'<file_content path="{file_path}">{tracker.DUPLICATE_FILE_READ_NOTICE}</file_content>'

                    # 尝试替换
                    new_content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)
                    if new_content == content:
                        new_content = re.sub(pattern2, replacement2, content, flags=re.DOTALL)

                    if new_content != content:
                        message["content"] = new_content
                        logger.debug(f"替换重复文件读取: {file_path} (消息索引: {msg_idx})")

    return optimized_messages

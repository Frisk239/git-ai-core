"""
上下文压缩策略

参考 Cline 的实现：
1. 渐进式压缩：先优化文件读取，再截断消息
2. 智能文件处理：识别并标记重复的文件读取（而非删除）
3. 分层消息管理：保留关键消息，压缩历史消息
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from app.core.context.token_counter import TokenCounter
from app.core.ai_manager import AIManager
from app.core.context.file_read_tracker import (
    FileReadTracker,
    extract_file_reads_from_messages,
    replace_duplicate_file_reads
)

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """压缩级别"""
    NONE = "none"  # 不压缩
    LIGHT = "light"  # 轻度压缩（保留 75%）
    MEDIUM = "medium"  # 中度压缩（保留 50%）
    AGGRESSIVE = "aggressive"  # 激进压缩（保留 25%）


class CompressionStrategy:
    """
    上下文压缩策略

    参考 Cline 的 ContextManager 实现
    """

    # 压缩阈值（参考 Cline，更激进地在早期压缩）
    SHOULD_COMPRESS_THRESHOLD = 0.5  # 当使用量超过 50% 时压缩（原来是 80%）
    MUST_COMPRESS_THRESHOLD = 0.7  # 当使用量超过 70% 时强制压缩（原来是 95%）

    # 保留策略
    KEEP_FIRST_N_PAIRS = 1  # 保留前 N 轮对话
    KEEP_LAST_N_PAIRS = 2  # 保留最后 N 轮对话

    def __init__(self, ai_manager: Optional[AIManager] = None):
        self.ai_manager = ai_manager or AIManager()
        self.token_counter = TokenCounter()
        self.file_read_tracker = FileReadTracker()

    def should_compress(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        threshold: Optional[float] = None
    ) -> bool:
        """
        判断是否需要压缩

        Args:
            messages: 当前消息列表
            model: 模型名称
            threshold: 自定义阈值

        Returns:
            是否需要压缩
        """
        threshold = threshold or self.SHOULD_COMPRESS_THRESHOLD
        info = self.token_counter.get_compression_info(messages, model)
        return info["usage_percentage"] >= threshold

    def must_compress(self, messages: List[Dict[str, Any]], model: str) -> bool:
        """判断是否必须压缩"""
        info = self.token_counter.get_compression_info(messages, model)
        return info["must_compress"]

    async def compress_conversation_history(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        ai_config: Dict[str, Any],
        compression_level: Optional[CompressionLevel] = None
    ) -> List[Dict[str, Any]]:
        """
        压缩对话历史

        参考 Cline 的两阶段策略：
        1. **第一阶段：优化重复文件读取**（不删除消息，只替换内容）
           - 检测重复的文件读取
           - 将旧的读取替换为简短提示
           - 保留最新的文件读取内容
           - 这样 AI 仍然知道已经读过这些文件

        2. **第二阶段：三明治截断**（仅在需要时）
           - 保留系统提示词（始终保留）
           - 保留第一轮用户消息和助手回复（任务起点）
           - 删除中间的历史消息
           - 保留最后几轮对话（最近状态）

        Args:
            messages: 原始消息列表
            model: 模型名称
            ai_config: AI 配置
            compression_level: 压缩级别

        Returns:
            压缩后的消息列表
        """
        if len(messages) <= 4:
            # 消息太少，不需要压缩
            return messages

        print(f"\n🗜️  开始压缩上下文...")
        print(f"   - 原始消息数: {len(messages)}")

        # === 阶段 1: 优化重复文件读取（Cline 的关键策略）===
        print(f"\n📖 阶段 1: 扫描文件读取...")

        # 提取所有文件读取
        file_reads = extract_file_reads_from_messages(messages)
        print(f"   - 发现 {len(file_reads)} 次文件读取")

        # 记录到追踪器
        for file_path, msg_idx, content_idx, content_length in file_reads:
            self.file_read_tracker.record_file_read(file_path, msg_idx, content_idx, content_length)

        # 打印分析报告
        report = self.file_read_tracker.get_optimization_report()
        print(report)

        # 如果有重复读取，进行优化
        optimized_messages = messages
        if self.file_read_tracker.should_optimize(threshold_savings=1000):
            print(f"\n✨ 阶段 1b: 优化重复文件读取...")
            optimized_messages = replace_duplicate_file_reads(messages, self.file_read_tracker)

            # 计算节省
            savings = self.file_read_tracker.calculate_savings()
            print(f"   ✅ 已替换 {savings['file_count']} 个文件的重复读取")
            print(f"   ✅ 节省约 {savings['total_savings']:,} 字符")

        # 检查优化后是否还需要截断
        total_chars = sum(len(str(msg.get("content", ""))) for msg in optimized_messages)
        MAX_TOTAL_CHARS = 40_000  # GLM 模型限制

        if total_chars <= MAX_TOTAL_CHARS:
            print(f"\n✅ 优化后字符数: {total_chars:,} (在限制内)")
            return optimized_messages

        # === 阶段 2: 三明治截断（仅在优化后仍然超限时）===
        print(f"\n📊 阶段 2: 消息截断...")
        print(f"   - 当前字符数: {total_chars:,} > {MAX_TOTAL_CHARS:,}")
        print(f"   - 需要截断历史消息...")

        # 1. 提取系统提示词（如果有）
        system_messages = [msg for msg in optimized_messages if msg.get("role") == "system"]
        non_system_messages = [msg for msg in optimized_messages if msg.get("role") != "system"]

        if len(non_system_messages) <= 4:
            # 非系统消息太少，不需要压缩
            return optimized_messages

        # 2. Cline 的"三明治截断法"
        compressed = []

        # 添加系统消息
        compressed.extend(system_messages)

        # 保留第一轮对话（前 2 条消息：user + assistant）
        first_pair = non_system_messages[:2]
        compressed.extend(first_pair)

        # 确定要保留的最后几轮对话
        # 参考 Cline: keep="lastTwo" 表示保留最后 1 轮对话（2 条消息）
        if compression_level == CompressionLevel.AGGRESSIVE:
            # 激进压缩：只保留第一轮和最后一轮
            last_pair_count = 2
        elif compression_level == CompressionLevel.MEDIUM:
            # 中度压缩：保留第一轮和最后两轮
            last_pair_count = 4
        else:  # LIGHT
            # 轻度压缩：保留第一轮和最后 4 轮
            last_pair_count = 8

        # 添加最后的对话
        if len(non_system_messages) > 2 + last_pair_count:
            last_pairs = non_system_messages[-last_pair_count:]
            compressed.extend(last_pairs)
        else:
            # 如果消息总数不够，就全部保留
            compressed.extend(non_system_messages[2:])

        # 计算最终字符数
        final_chars = sum(len(str(msg.get("content", ""))) for msg in compressed)
        print(f"   - 截断后消息数: {len(compressed)}")
        print(f"   - 截断后字符数: {final_chars:,}")
        print(f"   - 删除了 {len(optimized_messages) - len(compressed)} 条历史消息")
        print(f"   - 总压缩率: {(1 - len(compressed)/len(messages)) * 100:.1f}%")

        return compressed

    def _determine_compression_level(
        self,
        messages: List[Dict[str, Any]],
        model: str
    ) -> CompressionLevel:
        """根据 token 使用量确定压缩级别"""
        info = self.token_counter.get_compression_info(messages, model)
        usage = info["usage_percentage"]

        if usage >= self.MUST_COMPRESS_THRESHOLD:
            return CompressionLevel.AGGRESSIVE
        elif usage >= self.SHOULD_COMPRESS_THRESHOLD:
            return CompressionLevel.MEDIUM
        else:
            return CompressionLevel.LIGHT

    async def _summarize_messages(
        self,
        messages: List[Dict[str, Any]],
        ai_config: Dict[str, Any]
    ) -> Optional[str]:
        """
        使用 AI 总结消息

        参考 Cline 的 SummarizeTask 工具实现
        """
        try:
            # 构建总结提示词
            summarize_prompt = self._build_summarize_prompt()

            # 将消息转换为文本
            messages_text = self._format_messages_for_summary(messages)

            # 调用 AI
            response = await self.ai_manager.chat(
                provider=ai_config.get("ai_provider", "deepseek"),
                model=ai_config.get("ai_model", "deepseek-chat"),
                messages=[{
                    "role": "user",
                    "content": f"{summarize_prompt}\n\n对话历史：\n{messages_text}"
                }],
                api_key=ai_config.get("ai_api_key"),
                base_url=ai_config.get("ai_base_url"),
                temperature=0.3,
                max_tokens=2000
            )

            if response and response.get("content"):
                return response["content"].strip()

        except Exception as e:
            logger.error(f"AI 总结失败: {e}")

        return None

    def _build_summarize_prompt(self) -> str:
        """构建总结提示词（参考 Cline 的 summarizeTask）"""
        return """请详细总结之前的对话内容，包含以下部分：

1. **用户的主要请求**: 用户想要完成什么任务？

2. **技术概念**: 讨论了哪些技术概念、框架或工具？

3. **关键文件**: 查看或修改了哪些文件？（列出文件路径）

4. **问题解决**: 解决了哪些问题？如何解决的？

5. **当前状态**: 目前任务进行到哪一步了？

6. **待办事项**: 还有哪些未完成的任务？

请简洁但完整地总结，便于继续完成任务。"""

    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        """将消息格式化为适合总结的文本"""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # 截断过长的内容
            if len(content) > 500:
                content = content[:500] + "...(内容已截断)"

            parts.append(f"{role.upper()}: {content}")

        return "\n\n".join(parts)

    def truncate_tool_result(self, tool_name: str, result: Any, max_chars: int = 5000) -> str:
        """
        截断过长的工具结果

        参考 Cline 的终端输出截断逻辑
        """
        result_str = str(result)

        if len(result_str) <= max_chars:
            return result_str

        # 保留前半部分和后半部分
        half = max_chars // 2
        truncated = f"{result_str[:half]}\n\n... (结果已截断，原长度: {len(result_str)} 字符) ...\n\n{result_str[-half:]}"

        return truncated

    def optimize_file_reads(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        优化文件读取消息

        参考 Cline 的文件读取优化：
        1. 识别重复的文件读取
        2. 将重复的读取替换为引用
        """
        # TODO: 实现文件读取优化
        # 这需要解析工具调用结果，识别 file_content 块
        return messages

    def get_compression_stats(
        self,
        original: List[Dict[str, Any]],
        compressed: List[Dict[str, Any]],
        model: str
    ) -> Dict[str, Any]:
        """获取压缩统计信息"""
        original_tokens = self.token_counter.count_messages_tokens(original)
        compressed_tokens = self.token_counter.count_messages_tokens(compressed)

        return {
            "original_messages": len(original),
            "compressed_messages": len(compressed),
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "tokens_saved": original_tokens - compressed_tokens,
            "compression_ratio": (1 - compressed_tokens / original_tokens) if original_tokens > 0 else 0,
            "context_window": self.token_counter.get_context_window(model),
            "max_allowed": self.token_counter.get_max_allowed_size(model),
        }

"""
上下文管理模块

参考 Cline 的上下文压缩策略，实现智能的对话历史管理。
"""

from app.core.context.token_counter import TokenCounter
from app.core.context.compression_strategy import CompressionStrategy
from app.core.context.summary_generator import SummaryGenerator

__all__ = [
    "TokenCounter",
    "CompressionStrategy",
    "SummaryGenerator",
]

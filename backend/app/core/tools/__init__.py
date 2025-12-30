"""
工具系统 - 借鉴 Cline 的工具架构

提供统一的工具注册、管理和执行接口
"""

from .base import (
    ToolCallStatus,
    ToolParameter,
    ToolSpec,
    ToolCall,
    ToolResult,
    ToolContext
)

from .handler import BaseToolHandler

from .coordinator import (
    ToolCoordinator,
    get_tool_coordinator
)


__all__ = [
    # 基础类型
    "ToolCallStatus",
    "ToolParameter",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "ToolContext",

    # 处理器
    "BaseToolHandler",

    # 协调器
    "ToolCoordinator",
    "get_tool_coordinator",
]

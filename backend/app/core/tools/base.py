"""
工具系统基础类型定义
借鉴 Cline 的工具架构，提供统一的工具接口
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from enum import Enum


class ToolCallStatus(str, Enum):
    """工具调用状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolSpec(BaseModel):
    """工具规范"""
    name: str
    description: str
    parameters: Dict[str, ToolParameter]
    category: str = "general"  # 工具分类: git, file, analysis, mcp 等


class ToolCall(BaseModel):
    """工具调用请求"""
    id: str
    name: str
    parameters: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "success": self.success
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class ToolContext(BaseModel):
    """工具执行上下文"""
    repository_path: str
    user_intent: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True

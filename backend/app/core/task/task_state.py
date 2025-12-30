"""
任务状态管理 - 借鉴 Cline 的 TaskState
集中管理任务的所有状态
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum


class ErrorType(str, Enum):
    """错误类型"""
    API_ERROR = "api_error"
    TOOL_ERROR = "tool_error"
    VALIDATION_ERROR = "validation_error"
    CONTEXT_ERROR = "context_error"


@dataclass
class TaskState:
    """任务状态 - 管理 AI 任务执行过程中的所有状态"""

    # 流式响应标志
    is_streaming: bool = False
    is_waiting_for_first_chunk: bool = False
    did_complete_reading_stream: bool = False

    # 消息内容
    assistant_message_content: List[Dict[str, Any]] = field(default_factory=list)
    user_message_content: List[Dict[str, Any]] = field(default_factory=list)
    tool_use_id_map: Dict[str, str] = field(default_factory=dict)

    # 工具执行标志
    did_reject_tool: bool = False
    did_already_use_tool: bool = False
    did_edit_file: bool = False

    # 错误追踪
    consecutive_mistake_count: int = 0
    auto_retry_attempts: int = 0

    # 任务中止
    abort: bool = False

    # API 请求统计
    api_request_count: int = 0
    api_requests_since_last_todo_update: int = 0

    # 自动上下文压缩
    currently_summarizing: bool = False
    last_auto_compact_trigger_index: int = 0

    def reset_for_new_task(self):
        """重置状态用于新任务"""
        self.is_streaming = False
        self.is_waiting_for_first_chunk = False
        self.did_complete_reading_stream = False
        self.assistant_message_content = []
        self.user_message_content = []
        self.tool_use_id_map = {}
        self.did_reject_tool = False
        self.did_already_use_tool = False
        self.did_edit_file = False
        self.consecutive_mistake_count = 0
        self.auto_retry_attempts = 0
        self.abort = False
        self.api_request_count = 0
        self.api_requests_since_last_todo_update = 0
        self.currently_summarizing = False
        self.last_auto_compact_trigger_index = 0

    def increment_api_request_count(self):
        """增加 API 请求计数"""
        self.api_request_count += 1
        self.api_requests_since_last_todo_update += 1

    def increment_mistake_count(self):
        """增加连续错误计数"""
        self.consecutive_mistake_count += 1

    def should_abort(self) -> bool:
        """检查是否应该中止任务"""
        return self.abort

    def mark_tool_used(self):
        """标记已使用工具"""
        self.did_already_use_tool = True

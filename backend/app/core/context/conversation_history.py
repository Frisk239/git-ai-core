"""
对话历史持久化管理器

参考 Cline 的 ContextManager 实现：
- 保存和加载对话历史
- 支持消息的增删改查
- 记录压缩历史（删除范围）
- 为后续的状态恢复打基础
"""

import json
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """工具调用记录"""
    id: str
    name: str
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class ConversationMessage:
    """
    对话消息

    参考 Cline 的 ClineMessage 结构
    """
    timestamp: float  # 消息时间戳
    role: str  # "user" | "assistant" | "system"
    content: str  # 消息内容

    # 工具调用相关
    tool_calls: Optional[List[ToolCall]] = None  # 工具调用列表
    tool_results: Optional[List[Dict[str, Any]]] = None  # 工具执行结果

    # 元数据
    model: Optional[str] = None  # 使用的模型
    tokens_used: Optional[int] = None  # 使用的 token 数

    # 压缩相关
    compression_deleted_range: Optional[Tuple[int, int]] = None  # 压缩删除的范围 [start, end]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "timestamp": self.timestamp,
            "role": self.role,
            "content": self.content,
        }

        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "name": tc.name,
                    "parameters": tc.parameters,
                    "result": tc.result,
                    "timestamp": tc.timestamp,
                }
                for tc in self.tool_calls
            ]

        if self.tool_results:
            data["tool_results"] = self.tool_results

        if self.model:
            data["model"] = self.model

        if self.tokens_used:
            data["tokens_used"] = self.tokens_used

        if self.compression_deleted_range:
            data["compression_deleted_range"] = self.compression_deleted_range

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        """从字典创建"""
        tool_calls = None
        if data.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc.get("id", str(uuid.uuid4())),  # 如果没有 id,生成一个
                    name=tc["name"],
                    parameters=tc["parameters"],
                    result=tc.get("result"),
                    timestamp=tc.get("timestamp"),
                )
                for tc in data["tool_calls"]
            ]

        return cls(
            timestamp=data["timestamp"],
            role=data["role"],
            content=data["content"],
            tool_calls=tool_calls,
            tool_results=data.get("tool_results"),
            model=data.get("model"),
            tokens_used=data.get("tokens_used"),
            compression_deleted_range=tuple(data["compression_deleted_range"]) if data.get("compression_deleted_range") else None,
        )


class ConversationHistoryManager:
    """
    对话历史管理器 - 任务级别

    参考 Cline 设计：
    - 任务 = 会话
    - 每个任务独立存储对话历史
    - 任务历史由 TaskHistoryManager 管理

    职责：
    1. 保存和加载单个任务的对话历史
    2. 管理消息的增删改查
    3. 记录压缩历史
    """

    def __init__(self, task_id: str, workspace_path: str):
        """
        初始化对话历史管理器

        Args:
            task_id: 任务 ID（也是会话 ID）
            workspace_path: 工作空间路径
        """
        self.task_id = task_id
        self.workspace_path = Path(workspace_path)

        # 对话消息列表
        self.messages: List[ConversationMessage] = []

        # 任务目录（每个任务一个目录）
        self.task_dir = self.workspace_path / ".ai" / "tasks" / task_id

        # 历史文件（参考 Cline 的命名）
        self.api_history_file = self.task_dir / "api_conversation_history.json"
        self.ui_messages_file = self.task_dir / "ui_messages.json"
        self.task_metadata_file = self.task_dir / "task_metadata.json"

        logger.info(f"初始化对话历史管理器: task_id={task_id}")

    def append_message(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[ToolCall]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> ConversationMessage:
        """
        添加新消息

        Args:
            role: 消息角色 ("user" | "assistant" | "system")
            content: 消息内容
            tool_calls: 工具调用列表
            tool_results: 工具执行结果
            model: 使用的模型
            tokens_used: 使用的 token 数

        Returns:
            创建的消息对象
        """
        message = ConversationMessage(
            timestamp=time.time(),
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
            model=model,
            tokens_used=tokens_used,
        )

        self.messages.append(message)
        logger.debug(f"添加消息: role={role}, length={len(content)}")

        return message

    def get_messages(
        self,
        role: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[ConversationMessage]:
        """
        获取消息列表

        Args:
            role: 过滤角色 (None 表示不过滤)
            limit: 限制数量 (None 表示不限制)

        Returns:
            消息列表
        """
        messages = self.messages

        if role:
            messages = [m for m in messages if m.role == role]

        if limit:
            messages = messages[-limit:]

        return messages

    def to_api_messages(self) -> List[Dict[str, Any]]:
        """
        转换为 API 消息格式

        用于发送给 AI 模型的消息列表

        Returns:
            API 消息列表 [{"role": "...", "content": "..."}]
        """
        api_messages = []

        for msg in self.messages:
            api_msg = {
                "role": msg.role,
                "content": msg.content,
            }

            # 如果有工具调用，添加到 content 中（用于显示）
            # 实际的工具调用通过其他机制处理

            api_messages.append(api_msg)

        return api_messages

    def record_compression(self, deleted_range: Tuple[int, int]):
        """
        记录压缩操作

        Args:
            deleted_range: 删除的消息范围 [start, end]
        """
        # 在最后一条消息中记录压缩范围
        if self.messages:
            last_message = self.messages[-1]
            last_message.compression_deleted_range = deleted_range
            logger.info(f"记录压缩范围: {deleted_range}")

    async def save_history(self) -> bool:
        """
        保存对话历史到磁盘

        保存 API 对话历史到 api_conversation_history.json

        Returns:
            是否保存成功
        """
        try:
            # 确保任务目录存在
            self.task_dir.mkdir(parents=True, exist_ok=True)

            # 序列化消息
            data = {
                "task_id": self.task_id,
                "workspace_path": str(self.workspace_path),
                "created_at": self.messages[0].timestamp if self.messages else time.time(),
                "updated_at": time.time(),
                "message_count": len(self.messages),
                "messages": [msg.to_dict() for msg in self.messages],
            }

            # 写入 API 历史文件
            with open(self.api_history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"对话历史已保存: {self.api_history_file.name} ({len(self.messages)} 条消息)")
            return True

        except Exception as e:
            logger.error(f"保存对话历史失败: {e}", exc_info=True)
            return False

    async def load_history(self) -> bool:
        """
        从磁盘加载对话历史

        从 api_conversation_history.json 加载

        Returns:
            是否加载成功
        """
        try:
            if not self.api_history_file.exists():
                logger.info(f"对话历史文件不存在: {self.api_history_file.name}")
                return False

            # 读取文件
            with open(self.api_history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证 task_id
            if data.get("task_id") != self.task_id:
                logger.warning(f"task_id 不匹配: {data.get('task_id')} != {self.task_id}")
                return False

            # 反序列化消息
            self.messages = [
                ConversationMessage.from_dict(msg_data)
                for msg_data in data.get("messages", [])
            ]

            logger.info(f"对话历史已加载: {self.api_history_file.name} ({len(self.messages)} 条消息)")
            return True

        except Exception as e:
            logger.error(f"加载对话历史失败: {e}", exc_info=True)
            return False

    def clear_history(self):
        """清空对话历史（仅内存）"""
        self.messages.clear()
        logger.info("对话历史已清空")

    def delete_history_files(self) -> bool:
        """
        删除任务的所有历史文件

        Returns:
            是否删除成功
        """
        try:
            if self.task_dir.exists():
                import shutil
                shutil.rmtree(self.task_dir)
                logger.info(f"任务目录已删除: {self.task_dir}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除任务目录失败: {e}", exc_info=True)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        user_messages = [m for m in self.messages if m.role == "user"]
        assistant_messages = [m for m in self.messages if m.role == "assistant"]
        system_messages = [m for m in self.messages if m.role == "system"]

        total_tokens = sum(m.tokens_used or 0 for m in self.messages)

        # 计算任务目录大小
        task_dir_size = 0
        if self.task_dir.exists():
            for file in self.task_dir.rglob("*"):
                if file.is_file():
                    task_dir_size += file.stat().st_size

        return {
            "task_id": self.task_id,
            "total_messages": len(self.messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "system_messages": len(system_messages),
            "total_tokens": total_tokens,
            "task_dir_exists": self.task_dir.exists(),
            "task_dir_size": task_dir_size,
        }

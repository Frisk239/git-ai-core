"""
任务历史管理 - 参考 Cline 的 HistoryItem 设计

核心概念：
- 任务 = 会话（一个 task_id 就是一个会话）
- 每个任务独立存储对话历史
- 任务历史记录所有任务的元数据
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class HistoryItem:
    """
    任务历史项 - 参考 Cline 的 HistoryItem

    每个任务对应一个会话，包含任务的元数据和使用统计
    """
    id: str  # 任务 ID（也是会话 ID）
    task: str  # 任务描述（用户输入的摘要）

    # 时间戳
    ts: float = field(default_factory=time.time)  # 创建时间
    last_updated: float = field(default_factory=time.time)  # 最后更新时间

    # Token 统计
    tokens_in: int = 0  # 输入 tokens
    tokens_out: int = 0  # 输出 tokens
    cache_writes: int = 0  # 缓存写入
    cache_reads: int = 0  # 缓存读取

    # 成本统计
    total_cost: float = 0.0  # 总成本（美元）

    # 其他元数据
    size: int = 0  # 任务大小（字节）
    is_favorited: bool = False  # 是否收藏

    # API 相关
    api_provider: Optional[str] = None  # AI 提供商
    api_model: Optional[str] = None  # AI 模型

    # 仓库路径
    repository_path: Optional[str] = None  # Git 仓库路径

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryItem":
        """从字典创建"""
        return cls(**data)

    def update_timestamp(self):
        """更新最后更新时间"""
        self.last_updated = time.time()


class TaskHistoryManager:
    """
    任务历史管理器 - 参考 Cline 的任务历史管理

    职责：
    1. 保存和加载任务历史列表
    2. 添加新任务到历史
    3. 更新任务统计信息
    4. 支持搜索和过滤
    """

    def __init__(self, workspace_path: str):
        """
        初始化任务历史管理器

        Args:
            workspace_path: 工作空间路径
        """
        self.workspace_path = Path(workspace_path)

        # 历史文件路径
        self.history_dir = self.workspace_path / ".ai" / "history"
        self.history_file = self.history_dir / "task_history.json"

        # 任务历史列表
        self.history_items: List[HistoryItem] = []

        logger.info(f"初始化任务历史管理器: {self.history_file}")

    async def load_history(self) -> bool:
        """
        加载任务历史

        Returns:
            是否加载成功
        """
        try:
            if not self.history_file.exists():
                logger.info(f"任务历史文件不存在: {self.history_file}")
                self.history_items = []
                return False

            # 读取文件
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 反序列化
            self.history_items = [
                HistoryItem.from_dict(item_data)
                for item_data in data
            ]

            logger.info(f"已加载 {len(self.history_items)} 个任务历史")
            return True

        except Exception as e:
            logger.error(f"加载任务历史失败: {e}", exc_info=True)
            self.history_items = []
            return False

    async def save_history(self) -> bool:
        """
        保存任务历史

        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            self.history_dir.mkdir(parents=True, exist_ok=True)

            # 序列化
            data = [item.to_dict() for item in self.history_items]

            # 写入文件
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"已保存 {len(self.history_items)} 个任务历史")
            return True

        except Exception as e:
            logger.error(f"保存任务历史失败: {e}", exc_info=True)
            return False

    def add_or_update_task(
        self,
        task_id: str,
        task_description: str,
        api_provider: Optional[str] = None,
        api_model: Optional[str] = None,
        repository_path: Optional[str] = None,
    ) -> HistoryItem:
        """
        添加或更新任务

        Args:
            task_id: 任务 ID
            task_description: 任务描述
            api_provider: AI 提供商
            api_model: AI 模型
            repository_path: 仓库路径

        Returns:
            创建或更新的 HistoryItem
        """
        # 检查是否已存在
        existing_item = next(
            (item for item in self.history_items if item.id == task_id),
            None
        )

        if existing_item:
            # 更新现有任务
            existing_item.update_timestamp()
            return existing_item
        else:
            # 创建新任务
            new_item = HistoryItem(
                id=task_id,
                task=task_description,
                api_provider=api_provider,
                api_model=api_model,
                repository_path=repository_path,
            )
            self.history_items.append(new_item)

            # 按时间倒序排序（最新的在前）
            self.history_items.sort(key=lambda x: x.ts, reverse=True)

            logger.info(f"添加新任务到历史: {task_id}")
            return new_item

    def get_task(self, task_id: str) -> Optional[HistoryItem]:
        """
        获取指定任务

        Args:
            task_id: 任务 ID

        Returns:
            HistoryItem 或 None
        """
        return next(
            (item for item in self.history_items if item.id == task_id),
            None
        )

    def search_tasks(
        self,
        query: Optional[str] = None,
        favorites_only: bool = False,
        sort_by: str = "newest",  # "newest" | "oldest" | "cost"
        limit: int = 100,
    ) -> List[HistoryItem]:
        """
        搜索任务

        Args:
            query: 搜索关键词
            favorites_only: 只显示收藏
            sort_by: 排序方式
            limit: 限制数量

        Returns:
            过滤和排序后的任务列表
        """
        items = self.history_items

        # 过滤：收藏
        if favorites_only:
            items = [item for item in items if item.is_favorited]

        # 过滤：搜索关键词
        if query:
            query_lower = query.lower()
            items = [
                item for item in items
                if query_lower in item.task.lower() or query_lower in item.id.lower()
            ]

        # 排序
        if sort_by == "newest":
            items.sort(key=lambda x: x.ts, reverse=True)
        elif sort_by == "oldest":
            items.sort(key=lambda x: x.ts, reverse=False)
        elif sort_by == "cost":
            items.sort(key=lambda x: x.total_cost, reverse=True)

        # 限制数量
        return items[:limit]

    def toggle_favorite(self, task_id: str) -> bool:
        """
        切换任务的收藏状态

        Args:
            task_id: 任务 ID

        Returns:
            新的收藏状态
        """
        item = self.get_task(task_id)
        if item:
            item.is_favorited = not item.is_favorited
            item.update_timestamp()
            logger.info(f"任务 {task_id} 收藏状态: {item.is_favorited}")
            return item.is_favorited
        return False

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务历史

        Args:
            task_id: 任务 ID

        Returns:
            是否删除成功
        """
        original_length = len(self.history_items)
        self.history_items = [item for item in self.history_items if item.id != task_id]

        deleted = len(self.history_items) < original_length
        if deleted:
            logger.info(f"已删除任务历史: {task_id}")

        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        total_tokens = sum(item.tokens_in + item.tokens_out for item in self.history_items)
        total_cost = sum(item.total_cost for item in self.history_items)
        favorite_count = sum(1 for item in self.history_items if item.is_favorited)

        return {
            "total_tasks": len(self.history_items),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "favorite_count": favorite_count,
            "history_file_exists": self.history_file.exists(),
        }

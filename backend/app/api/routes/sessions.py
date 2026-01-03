"""
会话管理 API 路由

参考 Cline 的任务历史管理，提供：
1. 获取任务/会话列表
2. 恢复任务/会话
3. 删除任务/会话
4. 收藏/取消收藏任务
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ============================================================================
# 数据模型
# ============================================================================

class TaskInfo(BaseModel):
    """任务信息"""
    id: str
    task: str
    ts: float
    last_updated: float
    tokens_in: int = 0
    tokens_out: int = 0
    cache_writes: int = 0
    cache_reads: int = 0
    total_cost: float = 0.0
    size: int = 0
    is_favorited: bool = False
    api_provider: Optional[str] = None
    api_model: Optional[str] = None
    repository_path: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskInfo]
    total_count: int
    total_tokens: int
    total_cost: float


class TaskDeleteResponse(BaseModel):
    """任务删除响应"""
    success: bool
    message: str


class TaskToggleFavoriteResponse(BaseModel):
    """收藏切换响应"""
    success: bool
    is_favorited: bool
    message: str


# ============================================================================
# 工具函数
# ============================================================================

def get_task_history_manager(repository_path: str):
    """获取任务历史管理器"""
    from app.core.context.task_history import TaskHistoryManager
    return TaskHistoryManager(workspace_path=repository_path)


def get_conversation_history_manager(task_id: str, repository_path: str):
    """获取对话历史管理器"""
    from app.core.context.conversation_history import ConversationHistoryManager
    return ConversationHistoryManager(
        task_id=task_id,
        workspace_path=repository_path
    )


# ============================================================================
# API 端点
# ============================================================================

@router.get("/list", response_model=TaskListResponse)
async def list_tasks(
    repository_path: str = Query(..., description="Git 仓库路径"),
    search_query: Optional[str] = Query(None, description="搜索关键词"),
    favorites_only: bool = Query(False, description="只显示收藏"),
    sort_by: str = Query("newest", description="排序方式: newest | oldest | cost"),
    limit: int = Query(100, description="限制数量"),
):
    """
    获取任务/会话列表

    参考 Cline 的 GetTaskHistory API
    """
    try:
        manager = get_task_history_manager(repository_path)
        await manager.load_history()

        # 搜索和过滤
        tasks = manager.search_tasks(
            query=search_query,
            favorites_only=favorites_only,
            sort_by=sort_by,
            limit=limit,
        )

        # 转换为响应模型
        task_infos = [
            TaskInfo(**task.to_dict())
            for task in tasks
        ]

        # 获取统计信息
        stats = manager.get_stats()

        return TaskListResponse(
            tasks=task_infos,
            total_count=stats['total_tasks'],
            total_tokens=stats['total_tokens'],
            total_cost=stats['total_cost'],
        )

    except Exception as e:
        logger.error(f"获取任务列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete/{task_id}", response_model=TaskDeleteResponse)
async def delete_task(
    task_id: str,
    repository_path: str = Query(..., description="Git 仓库路径"),
):
    """
    删除任务/会话

    删除任务的对话历史和元数据
    """
    try:
        # 删除对话历史文件
        conv_manager = get_conversation_history_manager(task_id, repository_path)
        conv_deleted = conv_manager.delete_history_files()

        # 从任务历史中移除
        task_manager = get_task_history_manager(repository_path)
        await task_manager.load_history()
        task_deleted = task_manager.delete_task(task_id)
        await task_manager.save_history()

        if conv_deleted or task_deleted:
            return TaskDeleteResponse(
                success=True,
                message=f"任务 {task_id} 已删除"
            )
        else:
            return TaskDeleteResponse(
                success=False,
                message=f"任务 {task_id} 不存在"
            )

    except Exception as e:
        logger.error(f"删除任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle-favorite/{task_id}", response_model=TaskToggleFavoriteResponse)
async def toggle_favorite(
    task_id: str,
    repository_path: str = Query(..., description="Git 仓库路径"),
):
    """
    切换任务收藏状态
    """
    try:
        manager = get_task_history_manager(repository_path)
        await manager.load_history()

        new_state = manager.toggle_favorite(task_id)

        if new_state is not False:
            await manager.save_history()
            return TaskToggleFavoriteResponse(
                success=True,
                is_favorited=new_state,
                message=f"任务 {task_id} 收藏状态已更新"
            )
        else:
            return TaskToggleFavoriteResponse(
                success=False,
                is_favorited=False,
                message=f"任务 {task_id} 不存在"
            )

    except Exception as e:
        logger.error(f"切换收藏状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/load/{task_id}")
async def load_task(
    task_id: str,
    repository_path: str = Query(..., description="Git 仓库路径"),
):
    """
    获取任务的详细信息（用于恢复会话）

    返回任务的对话历史和元数据
    """
    try:
        # 加载任务历史
        task_manager = get_task_history_manager(repository_path)
        await task_manager.load_history()

        history_item = task_manager.get_task(task_id)
        if not history_item:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

        # 加载对话历史
        conv_manager = get_conversation_history_manager(task_id, repository_path)
        await conv_manager.load_history()

        # 转换为 API 消息格式
        api_messages = conv_manager.to_api_messages()

        return {
            "task_id": task_id,
            "task": history_item.task,
            "created_at": history_item.ts,
            "last_updated": history_item.last_updated,
            "api_provider": history_item.api_provider,
            "api_model": history_item.api_model,
            "messages": api_messages,
            "message_count": len(api_messages),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加载任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

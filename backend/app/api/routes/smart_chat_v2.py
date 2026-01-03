"""
新的智能对话 API - 基于任务执行引擎

替代旧的对话系统，提供完整的工具调用能力
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import logging

from app.api.routes.chat import get_ai_config
from app.core.task import TaskEngine


router = APIRouter()
logger = logging.getLogger(__name__)


class SmartChatRequest(BaseModel):
    """智能聊天请求"""
    message: str
    repository_path: Optional[str] = None
    conversation_id: Optional[int] = None


@router.post("/smart-chat/stream")
async def smart_chat_stream(request: SmartChatRequest):
    """
    智能聊天 - 流式响应（支持工具调用）

    这是新的对话端点，基于 Cline 架构实现：
    - 递归任务循环
    - AI 自主调用工具
    - 流式返回进度
    """
    # 1. 获取 AI 配置
    try:
        ai_config = await get_ai_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 AI 配置失败: {str(e)}")

    # 2. 确定仓库路径
    repository_path = request.repository_path or os.getcwd()

    # 🔥 关键修复：从 app.state 获取 tool_coordinator,而不是使用全局单例
    from app.main import app
    tool_coordinator = app.state.tool_coordinator

    # 🔥 调试日志：检查 tool_coordinator 状态
    tools_count = len(tool_coordinator.list_tools())
    coordinator_id = id(tool_coordinator)
    logger.info(f"🔧 smart_chat_v2: tool_coordinator id={coordinator_id}, 工具数量={tools_count}")

    # 3. 创建任务引擎，传入正确的 tool_coordinator
    task_engine = TaskEngine(tool_coordinator=tool_coordinator)

    # 🔥 调试日志：验证 TaskEngine 内部的 tool_coordinator
    logger.info(f"🔧 TaskEngine.tool_coordinator id={id(task_engine.tool_coordinator)}, 工具数量={len(task_engine.tool_coordinator.list_tools())}")

    # 4. 执行任务（使用 Server-Sent Events 返回流式数据）
    from fastapi.responses import StreamingResponse

    async def event_generator():
        """生成 SSE 事件"""
        try:
            async for event in task_engine.execute_task(
                user_input=request.message,
                repository_path=repository_path,
                ai_config=ai_config
            ):
                # 将事件转换为 SSE 格式
                event_data = _format_sse_event(event)
                yield f"data: {event_data}\n\n"

        except Exception as e:
            error_event = {
                "type": "error",
                "message": f"任务执行异常: {str(e)}"
            }
            yield f"data: {_format_sse_event(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


def _format_sse_event(event: Dict[str, Any]) -> str:
    """格式化 SSE 事件"""
    import json
    return json.dumps(event, ensure_ascii=False)


@router.post("/smart-chat")
async def smart_chat(request: SmartChatRequest):
    """
    智能聊天 - 非流式版本（用于简单场景）

    返回完整的对话结果
    """
    # 🔥 调试日志：函数入口
    logger.info("🔧🔧🔧 smart_chat 函数被调用")

    # 1. 获取 AI 配置
    try:
        ai_config = await get_ai_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 AI 配置失败: {str(e)}")

    # 2. 确定仓库路径
    repository_path = request.repository_path or os.getcwd()

    # 🔥 关键修复：从 app.state 获取 tool_coordinator,而不是使用全局单例
    from app.main import app
    tool_coordinator = app.state.tool_coordinator

    # 🔥 调试日志：检查 tool_coordinator 状态
    tools_count = len(tool_coordinator.list_tools())
    coordinator_id = id(tool_coordinator)
    logger.info(f"🔧 smart_chat: tool_coordinator id={coordinator_id}, 工具数量={tools_count}")

    # 3. 创建任务引擎，传入正确的 tool_coordinator
    task_engine = TaskEngine(tool_coordinator=tool_coordinator)

    # 🔥 调试日志：验证 TaskEngine 内部的 tool_coordinator
    logger.info(f"🔧 TaskEngine.tool_coordinator id={id(task_engine.tool_coordinator)}, 工具数量={len(task_engine.tool_coordinator.list_tools())}")

    # 4. 执行任务并收集所有事件
    events = []
    final_content = None

    async for event in task_engine.execute_task(
        user_input=request.message,
        repository_path=repository_path,
        ai_config=ai_config
    ):
        events.append(event)

        # 捕获最终内容
        if event.get("type") == "completion":
            final_content = event.get("content")

    # 5. 返回结果
    return {
        "success": True,
        "content": final_content or "任务完成，但没有生成内容",
        "events": events,
        "event_count": len(events)
    }


@router.get("/tools")
async def list_available_tools():
    """列出所有可用工具"""
    from app.core.tools import get_tool_coordinator
    from app.main import app

    # 🔥 比较全局单例和 app.state 的 coordinator
    global_coordinator = get_tool_coordinator()
    state_coordinator = app.state.tool_coordinator

    global_tools = global_coordinator.list_tools()
    state_tools = state_coordinator.list_tools()

    logger.info(f"🔧 /tools endpoint: 全局 coordinator 有 {len(global_tools)} 个工具")
    logger.info(f"🔧 /tools endpoint: app.state coordinator 有 {len(state_tools)} 个工具")

    # 使用 app.state 的 coordinator（正确的）
    coordinator = state_coordinator
    tools = state_tools

    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "parameters": {
                    name: {
                        "type": param.type,
                        "description": param.description,
                        "required": param.required
                    }
                    for name, param in tool.parameters.items()
                }
            }
            for tool in tools
        ],
        "total_count": len(tools)
    }

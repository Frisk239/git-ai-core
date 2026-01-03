"""
动态 MCP 工具处理器

处理动态注册的 MCP 工具调用
"""

import logging
import json
from typing import Dict, Any
from ..handler import BaseToolHandler
from ..base import ToolSpec, ToolResult, ToolContext
from ..mcp_dynamic import parse_dynamic_tool_name
from app.core.mcp_server import MCPServerManager


logger = logging.getLogger(__name__)


def get_mcp_server_manager() -> MCPServerManager:
    """获取全局 MCP 服务器管理器"""
    from ..handlers.mcp_handler import get_mcp_server_manager
    return get_mcp_server_manager()


class DynamicMcpToolHandler(BaseToolHandler):
    """
    动态 MCP 工具处理器

    为每个动态注册的 MCP 工具创建处理器实例
    """

    def __init__(self, tool_spec: ToolSpec):
        """
        初始化动态 MCP 工具处理器

        Args:
            tool_spec: 工具规范（包含动态工具名称）
        """
        self._tool_spec = tool_spec

        # 解析工具名称，提取服务器名和工具名
        parsed = parse_dynamic_tool_name(tool_spec.name)
        if not parsed:
            raise ValueError(f"无效的 MCP 工具名称: {tool_spec.name}")

        self._server_name, self._mcp_tool_name = parsed

    @property
    def name(self) -> str:
        """获取工具名称"""
        return self._tool_spec.name

    def get_spec(self) -> ToolSpec:
        """获取工具规范"""
        return self._tool_spec

    async def execute(self, parameters: Dict[str, Any], context: ToolContext) -> Any:
        """
        执行工具调用

        Args:
            parameters: 工具参数
            context: 工具执行上下文

        Returns:
            工具执行结果
        """
        try:
            # 1. 获取 MCP 服务器管理器
            mcp_manager = get_mcp_server_manager()

            # 2. 检查服务器是否存在
            server_config = mcp_manager.get_server(self._server_name)
            if not server_config:
                return ToolResult(
                    success=False,
                    error=f"MCP 服务器不存在: {self._server_name}"
                )

            # 3. 检查服务器是否启用
            if not server_config.get("enabled", True):
                return ToolResult(
                    success=False,
                    error=f"MCP 服务器已禁用: {self._server_name}"
                )

            # 4. 确保服务器已启动
            client = mcp_manager._active_clients.get(self._server_name)
            if not client:
                logger.info(f"启动 MCP 服务器: {self._server_name}")
                success = await mcp_manager.start_server(self._server_name)
                if not success:
                    return ToolResult(
                        success=False,
                        error=f"无法启动 MCP 服务器: {self._server_name}"
                    )

            # 5. 调用 MCP 工具
            logger.info(f"调用动态 MCP 工具: {self._server_name}.{self._mcp_tool_name}")
            logger.debug(f"  参数: {parameters}")

            result = await mcp_manager.execute_tool(
                server_name=self._server_name,
                tool_name=self._mcp_tool_name,
                arguments=parameters
            )

            # 6. 处理结果
            if not result.get("success"):
                return ToolResult(
                    success=False,
                    error=result.get("error", "工具调用失败")
                )

            # 7. 格式化返回数据
            tool_result = result.get("result")

            # 处理 MCP 工具返回的内容列表
            if isinstance(tool_result, dict) and "content" in tool_result:
                content_list = tool_result["content"]

                if isinstance(content_list, list):
                    # 格式化内容项
                    formatted_parts = []
                    for item in content_list:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                formatted_parts.append(item.get("text", ""))
                            elif item.get("type") == "image":
                                formatted_parts.append(f"[图像: {item.get('data', '')[:50]}...]")
                            elif item.get("type") == "resource":
                                formatted_parts.append(f"[资源: {json.dumps(item.get('resource', {}), ensure_ascii=False)}]")
                            else:
                                # 其他类型直接转 JSON
                                formatted_parts.append(json.dumps(item, ensure_ascii=False))
                        else:
                            formatted_parts.append(str(item))

                    return ToolResult(
                        success=True,
                        data="\n\n".join(formatted_parts),
                        metadata={
                            "server_name": self._server_name,
                            "tool_name": self._mcp_tool_name,
                            "mcp_tool": True
                        }
                    )
                else:
                    # 单个内容项
                    return ToolResult(
                        success=True,
                        data=str(content_list),
                        metadata={
                            "server_name": self._server_name,
                            "tool_name": self._mcp_tool_name,
                            "mcp_tool": True
                        }
                    )
            else:
                # 其他格式直接返回
                return ToolResult(
                    success=True,
                    data=json.dumps(tool_result, ensure_ascii=False, indent=2),
                    metadata={
                        "server_name": self._server_name,
                        "tool_name": self._mcp_tool_name,
                        "mcp_tool": True
                    }
                )

        except Exception as e:
            logger.error(f"动态 MCP 工具执行失败 {self.name}: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"工具执行异常: {str(e)}"
            )

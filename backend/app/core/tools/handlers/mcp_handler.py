"""
MCP 工具处理器 - 参考Cline的UseMcpToolHandler和AccessMcpResourceHandler

提供三个核心工具：
1. use_mcp_tool - 调用 MCP 服务器的工具
2. access_mcp_resource - 访问 MCP 服务器的资源
3. list_mcp_servers - 列出可用的 MCP 服务器
"""

import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ..handler import BaseToolHandler
from ..base import ToolSpec, ToolParameter, ToolResult, ToolContext
from app.core.mcp_server import MCPServerManager


logger = logging.getLogger(__name__)


# 全局 MCP 服务器管理器
_mcp_server_manager: Optional[MCPServerManager] = None


def get_mcp_server_manager() -> MCPServerManager:
    """获取全局 MCP 服务器管理器"""
    global _mcp_server_manager
    if _mcp_server_manager is None:
        _mcp_server_manager = MCPServerManager()
    return _mcp_server_manager


class UseMcpToolHandler(BaseToolHandler):
    """
    use_mcp_tool 工具处理器

    参考 Cline 的 UseMcpToolHandler 实现
    允许 AI 调用 MCP 服务器提供的工具
    """

    @property
    def name(self) -> str:
        return "use_mcp_tool"

    def get_spec(self) -> ToolSpec:
        """获取工具规范"""
        return ToolSpec(
            name=self.name,
            description=(
                "调用 MCP (Model Context Protocol) 服务器提供的工具。\n\n"
                "⚠️ 重要：使用此工具前，你必须先调用 `list_mcp_servers` 工具来查看可用的 MCP 服务器及其工具列表。\n\n"
                "从 `list_mcp_servers` 的返回结果中，你可以看到每个 MCP 服务器提供了哪些工具。"
                "工具名称（tool_name）必须完全匹配，不要猜测或创造工具名称。\n\n"
                "示例流程：\n"
                "1. 先调用 list_mcp_servers 查看可用的服务器和工具\n"
                "2. 从返回结果中找到你需要的 tool_name（例如: 'mcp__drawio__create_new_diagram'）\n"
                "3. 调用 use_mcp_tool，使用准确的 tool_name\n\n"
                "MCP 服务器可以扩展 AI 的能力，提供额外的功能。"
            ),
            category="mcp",
            parameters={
                "server_name": ToolParameter(
                    name="server_name",
                    type="string",
                    description="MCP 服务器的名称（配置文件中定义的名称，例如: 'drawio'）",
                    required=True
                ),
                "tool_name": ToolParameter(
                    name="tool_name",
                    type="string",
                    description=(
                        "要调用的工具名称。"
                        "⚠️ 必须从 `list_mcp_servers` 的返回结果中获取准确的工具名称，"
                        "不要猜测！例如: 'mcp__drawio__create_new_diagram'"
                    ),
                    required=True
                ),
                "arguments": ToolParameter(
                    name="arguments",
                    type="string",
                    description="工具参数的 JSON 字符串，例如: {\"param1\": \"value1\"}",
                    required=False
                )
            }
        )

    async def execute(self, parameters: Dict[str, Any], context: ToolContext) -> Any:
        """执行工具调用"""
        try:
            # 1. 提取参数
            server_name = parameters.get("server_name")
            tool_name = parameters.get("tool_name")
            arguments_str = parameters.get("arguments", "{}")

            # 2. 验证必需参数
            if not server_name:
                return ToolResult(
                    success=False,
                    error="缺少必需参数: server_name"
                )

            if not tool_name:
                return ToolResult(
                    success=False,
                    error="缺少必需参数: tool_name"
                )

            # 3. 解析 JSON 参数
            try:
                arguments = json.loads(arguments_str) if arguments_str else {}
            except json.JSONDecodeError as e:
                return ToolResult(
                    success=False,
                    error=f"参数 JSON 解析失败: {e}"
                )

            # 4. 获取 MCP 服务器管理器
            mcp_manager = get_mcp_server_manager()

            # 5. 检查服务器是否存在
            server_config = mcp_manager.get_server(server_name)
            if not server_config:
                return ToolResult(
                    success=False,
                    error=f"MCP 服务器不存在: {server_name}"
                )

            # 6. 检查服务器是否启用
            if not server_config.get("enabled", True):
                return ToolResult(
                    success=False,
                    error=f"MCP 服务器已禁用: {server_name}"
                )

            # 7. 确保服务器已启动
            client = mcp_manager._active_clients.get(server_name)
            if not client:
                # 尝试启动服务器
                logger.info(f"启动 MCP 服务器: {server_name}")
                success = await mcp_manager.start_server(server_name)
                if not success:
                    return ToolResult(
                        success=False,
                        error=f"无法启动 MCP 服务器: {server_name}"
                    )

            # 8. 调用 MCP 工具
            logger.info(f"调用 MCP 工具: {server_name}.{tool_name}")
            logger.debug(f"  参数: {arguments}")

            result = await mcp_manager.execute_tool(
                server_name=server_name,
                tool_name=tool_name,
                arguments=arguments
            )

            # 9. 处理结果
            if not result.get("success"):
                return ToolResult(
                    success=False,
                    error=result.get("error", "工具调用失败")
                )

            # 10. 格式化返回数据
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
                            "server_name": server_name,
                            "tool_name": tool_name
                        }
                    )
                else:
                    # 单个内容项
                    return ToolResult(
                        success=True,
                        data=str(content_list),
                        metadata={
                            "server_name": server_name,
                            "tool_name": tool_name
                        }
                    )
            else:
                # 其他格式直接返回
                return ToolResult(
                    success=True,
                    data=json.dumps(tool_result, ensure_ascii=False, indent=2),
                    metadata={
                        "server_name": server_name,
                        "tool_name": tool_name
                    }
                )

        except Exception as e:
            logger.error(f"use_mcp_tool 执行失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"工具执行异常: {str(e)}"
            )


class AccessMcpResourceHandler(BaseToolHandler):
    """
    access_mcp_resource 工具处理器

    参考 Cline 的 AccessMcpResourceHandler 实现
    允许 AI 访问 MCP 服务器提供的资源
    """

    @property
    def name(self) -> str:
        return "access_mcp_resource"

    def get_spec(self) -> ToolSpec:
        """获取工具规范"""
        return ToolSpec(
            name=self.name,
            description="访问 MCP (Model Context Protocol) 服务器提供的资源。"
                      "资源可以是文件、数据或其他服务器暴露的内容。",
            category="mcp",
            parameters={
                "server_name": ToolParameter(
                    name="server_name",
                    type="string",
                    description="MCP 服务器的名称（配置文件中定义的名称）",
                    required=True
                ),
                "uri": ToolParameter(
                    name="uri",
                    type="string",
                    description="要读取的资源 URI，例如: file:///path/to/file 或 resource://data",
                    required=True
                )
            }
        )

    async def execute(self, parameters: Dict[str, Any], context: ToolContext) -> Any:
        """执行工具调用"""
        try:
            # 1. 提取参数
            server_name = parameters.get("server_name")
            uri = parameters.get("uri")

            # 2. 验证必需参数
            if not server_name:
                return ToolResult(
                    success=False,
                    error="缺少必需参数: server_name"
                )

            if not uri:
                return ToolResult(
                    success=False,
                    error="缺少必需参数: uri"
                )

            # 3. 获取 MCP 服务器管理器
            mcp_manager = get_mcp_server_manager()

            # 4. 检查服务器是否存在
            server_config = mcp_manager.get_server(server_name)
            if not server_config:
                return ToolResult(
                    success=False,
                    error=f"MCP 服务器不存在: {server_name}"
                )

            # 5. 确保服务器已启动
            client = mcp_manager._active_clients.get(server_name)
            if not client:
                success = await mcp_manager.start_server(server_name)
                if not success:
                    return ToolResult(
                        success=False,
                        error=f"无法启动 MCP 服务器: {server_name}"
                    )

            # 6. 读取资源
            logger.info(f"读取 MCP 资源: {server_name} - {uri}")

            result = await mcp_manager.read_resource(
                server_name=server_name,
                uri=uri
            )

            # 7. 处理结果
            if not result.get("success"):
                return ToolResult(
                    success=False,
                    error=result.get("error", "资源读取失败")
                )

            # 8. 格式化返回数据
            content = result.get("content")

            if isinstance(content, dict):
                # 处理单个内容项
                if content.get("type") == "text":
                    data = content.get("text", "")
                else:
                    data = json.dumps(content, ensure_ascii=False, indent=2)
            else:
                # 其他格式
                data = str(content)

            return ToolResult(
                success=True,
                data=data,
                metadata={
                    "server_name": server_name,
                    "uri": uri
                }
            )

        except Exception as e:
            logger.error(f"access_mcp_resource 执行失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"资源访问异常: {str(e)}"
            )


class ListMcpServersHandler(BaseToolHandler):
    """
    list_mcp_servers 工具处理器

    列出所有可用的 MCP 服务器及其工具和资源
    """

    @property
    def name(self) -> str:
        return "list_mcp_servers"

    def get_spec(self) -> ToolSpec:
        """获取工具规范"""
        return ToolSpec(
            name=self.name,
            description="列出所有可用的 MCP (Model Context Protocol) 服务器。"
                      "返回每个服务器的名称、状态、可用工具和资源。",
            category="mcp",
            parameters={}
        )

    async def execute(self, parameters: Dict[str, Any], context: ToolContext) -> Any:
        """执行工具调用"""
        try:
            mcp_manager = get_mcp_server_manager()

            # 🔥 调试日志：记录配置文件读取
            logger.info(f"🔧 list_mcp_servers: 开始读取服务器配置")

            # 获取所有服务器配置
            servers_config = mcp_manager.list_servers()

            # 🔥 调试日志：显示每个服务器的 enabled 配置
            for server_name, config in servers_config.items():
                enabled = config.get("enabled", True)
                logger.info(f"🔧 list_mcp_servers 配置: {server_name} -> enabled={enabled}, config={config}")

            # 构建服务器列表
            servers_info = []

            for server_name, config in servers_config.items():
                # 获取服务器状态
                status_info = await mcp_manager.get_server_status(server_name)

                # 🔥 调试日志：显示运行时状态
                logger.info(f"🔧 list_mcp_servers 运行时: {server_name} -> status={status_info.get('status', 'unknown')}, connected={status_info.get('connected', False)}")

                server_info = {
                    "name": server_name,
                    "description": config.get("description", ""),
                    "status": status_info.get("status", "unknown"),
                    "enabled": config.get("enabled", True),
                    "transport_type": config.get("transportType", "stdio")
                }

                # 如果服务器正在运行，获取工具和资源列表
                if status_info.get("connected"):
                    try:
                        # 获取工具列表
                        tools = await mcp_manager.list_tools(server_name)
                        server_info["tools"] = [
                            {
                                "name": tool["name"],
                                "description": tool.get("description", "")
                            }
                            for tool in tools
                        ]

                        # 获取资源列表
                        resources = await mcp_manager.list_resources(server_name)
                        server_info["resources"] = [
                            {
                                "uri": resource["uri"],
                                "name": resource.get("name", ""),
                                "description": resource.get("description", "")
                            }
                            for resource in resources
                        ]

                    except Exception as e:
                        logger.warning(f"获取 {server_name} 的工具/资源列表失败: {e}")

                servers_info.append(server_info)

            return ToolResult(
                success=True,
                data=json.dumps(servers_info, ensure_ascii=False, indent=2),
                metadata={
                    "total_servers": len(servers_info),
                    "active_servers": sum(1 for s in servers_info if s["status"] == "running")
                }
            )

        except Exception as e:
            logger.error(f"list_mcp_servers 执行失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"列表获取异常: {str(e)}"
            )

"""
MCP 动态工具注册系统

参考 Cline 的实现，将 MCP 服务器的工具动态转换为独立的 AI 可调用工具

关键设计：
- 工具名称格式: server_name + "__mcp__" + tool_name (例如: drawio__mcp__create_new_diagram)
- 每个 MCP 工具成为独立的函数调用工具
- AI 可以直接调用，无需中间步骤
"""

import logging
import json
from typing import Dict, Any, List, Optional
from .base import ToolSpec, ToolParameter

from app.core.mcp_server import MCPServerManager


logger = logging.getLogger(__name__)


# MCP 工具名称分隔符（参考 Cline 的 CLINE_MCP_TOOL_IDENTIFIER）
MCP_TOOL_SEPARATOR = "__mcp__"


async def convert_mcp_tools_to_specs(
    server_name: str,
    mcp_manager: MCPServerManager
) -> List[ToolSpec]:
    """
    将 MCP 服务器的工具转换为 ToolSpec 列表

    Args:
        server_name: MCP 服务器名称
        mcp_manager: MCP 服务器管理器

    Returns:
        工具规范列表
    """
    try:
        logger.info(f"🔍 正在转换 {server_name} 的工具...")

        # 1. 获取服务器状态
        status = await mcp_manager.get_server_status(server_name)
        logger.info(f"   服务器状态: connected={status.get('connected')}, initialized={status.get('initialized')}")

        # 2. 只处理已连接的服务器
        if not status.get("connected"):
            logger.warning(f"⚠️ MCP 服务器 {server_name} 未连接，跳过工具注册")
            return []

        # 3. 获取工具列表
        tools = await mcp_manager.list_tools(server_name)

        if not tools:
            logger.info(f"⚠️ MCP 服务器 {server_name} 没有可用工具")
            return []

        logger.info(f"   发现 {len(tools)} 个工具")

        # 4. 转换每个工具为 ToolSpec
        tool_specs = []

        for tool in tools:
            try:
                spec = await _convert_single_tool(server_name, tool)
                if spec:
                    tool_specs.append(spec)
                    logger.debug(f"  ✓ 转换工具: {spec.name}")
            except Exception as e:
                logger.error(f"  ✗ 转换工具失败 {tool.get('name')}: {e}", exc_info=True)
                continue

        logger.info(f"✅ 成功转换 {server_name} 的 {len(tool_specs)} 个工具")
        return tool_specs

    except Exception as e:
        logger.error(f"❌ 转换 MCP 工具失败 {server_name}: {e}", exc_info=True)
        return []


async def _convert_single_tool(server_name: str, mcp_tool: Dict[str, Any]) -> Optional[ToolSpec]:
    """
    转换单个 MCP 工具为 ToolSpec

    Args:
        server_name: MCP 服务器名称
        mcp_tool: MCP 工具定义

    Returns:
        ToolSpec 实例
    """
    # 1. 提取工具信息
    tool_name = mcp_tool.get("name", "")
    tool_desc = mcp_tool.get("description", "")

    if not tool_name:
        logger.warning("MCP 工具缺少 name 字段")
        return None

    # 2. 生成唯一的工具名称 (参考 Cline: serverUID + "0mcp0" + toolName)
    dynamic_tool_name = f"{server_name}{MCP_TOOL_SEPARATOR}{tool_name}"

    # 3. 转换参数 schema
    parameters = _convert_input_schema(mcp_tool.get("inputSchema", {}))

    # 4. 构建工具描述（增强版）
    enhanced_description = _build_enhanced_description(server_name, tool_name, tool_desc)

    # 5. 创建 ToolSpec
    return ToolSpec(
        name=dynamic_tool_name,
        description=enhanced_description,
        parameters=parameters,
        category="mcp_dynamic"
    )


def _convert_input_schema(input_schema: Dict[str, Any]) -> Dict[str, ToolParameter]:
    """
    将 MCP input schema 转换为 ToolParameter 字典

    Args:
        input_schema: MCP 工具的 input schema

    Returns:
        ToolParameter 字典
    """
    parameters = {}

    # 提取 properties
    properties = input_schema.get("properties", {})
    required_fields = input_schema.get("required", [])

    for param_name, param_def in properties.items():
        # 转换类型
        param_type = _convert_json_type_to_tool_type(param_def.get("type", "string"))

        # 创建 ToolParameter
        parameters[param_name] = ToolParameter(
            name=param_name,
            type=param_type,
            description=param_def.get("description", ""),
            required=param_name in required_fields,
            default=param_def.get("default")
        )

    return parameters


def _convert_json_type_to_tool_type(json_type: str) -> str:
    """
    将 JSON Schema 类型转换为工具类型

    Args:
        json_type: JSON Schema 类型

    Returns:
        工具类型字符串
    """
    type_mapping = {
        "string": "string",
        "number": "number",
        "integer": "integer",
        "boolean": "boolean",
        "array": "array",
        "object": "object"
    }

    return type_mapping.get(json_type, "string")


def _build_enhanced_description(
    server_name: str,
    tool_name: str,
    original_desc: str
) -> str:
    """
    构建增强的工具描述

    Args:
        server_name: MCP 服务器名称
        tool_name: 工具名称
        original_desc: 原始描述

    Returns:
        增强的描述文本
    """
    # 如果原始描述已经包含完整信息，直接使用
    if original_desc and f"MCP 服务器 {server_name}" in original_desc:
        return original_desc

    # 否则，添加 MCP 来源信息
    enhanced = f"[MCP: {server_name}] "

    if original_desc:
        enhanced += original_desc
    else:
        enhanced += f"调用 {server_name} 服务器的 {tool_name} 工具"

    return enhanced


def parse_dynamic_tool_name(tool_name: str) -> Optional[tuple[str, str]]:
    """
    解析动态工具名称，提取服务器名和工具名

    Args:
        tool_name: 动态工具名称 (例如: "drawio__mcp__create_new_diagram")

    Returns:
        (server_name, mcp_tool_name) 元组，如果不是 MCP 工具返回 None
    """
    if MCP_TOOL_SEPARATOR in tool_name:
        parts = tool_name.split(MCP_TOOL_SEPARATOR, 1)
        if len(parts) == 2:
            return (parts[0], parts[1])

    return None


async def register_all_mcp_tools(
    tool_coordinator,
    mcp_manager: MCPServerManager
) -> int:
    """
    注册所有已启动 MCP 服务器的工具到 ToolCoordinator

    🔥 简化逻辑：只检查服务器是否实际运行（connected），不检查配置中的 enabled

    Args:
        tool_coordinator: ToolCoordinator 实例
        mcp_manager: MCP 服务器管理器（必须是已启动服务器的实例）

    Returns:
        注册的工具总数
    """
    total_registered = 0

    try:
        # 1. 获取所有已连接的服务器（实际运行中的）
        # 🔥 关键：直接检查 _active_clients，不依赖配置文件
        active_servers = mcp_manager._active_clients.keys()

        if not active_servers:
            logger.warning("⚠️ 没有运行中的 MCP 服务器")
            return 0

        logger.info(f"发现 {len(active_servers)} 个运行中的 MCP 服务器")

        # 2. 遍历每个运行中的服务器
        for server_name in active_servers:
            logger.info(f"正在注册 MCP 服务器 {server_name} 的工具...")

            try:
                # 3. 转换工具为 ToolSpec
                tool_specs = await convert_mcp_tools_to_specs(server_name, mcp_manager)

                # 4. 注册到 ToolCoordinator
                for spec in tool_specs:
                    # 创建动态处理器
                    from .handlers.mcp_dynamic_handler import DynamicMcpToolHandler
                    handler = DynamicMcpToolHandler(spec)

                    # 注册
                    tool_coordinator.register(handler)
                    total_registered += 1

                logger.info(f"✅ {server_name}: 注册了 {len(tool_specs)} 个工具")

            except Exception as e:
                logger.error(f"注册 {server_name} 工具失败: {e}", exc_info=True)
                continue

        logger.info(f"✅ MCP 动态工具注册完成，共注册 {total_registered} 个工具")
        return total_registered

    except Exception as e:
        logger.error(f"注册 MCP 工具失败: {e}", exc_info=True)
        return total_registered

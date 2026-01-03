"""
工具定义转换器 - 将内部工具定义转换为 OpenAI 函数调用格式
"""

import json
from typing import List, Dict, Any
from app.core.tools import ToolCoordinator, ToolParameter


def tools_to_openai_functions(coordinator: ToolCoordinator) -> List[Dict[str, Any]]:
    """
    将工具协调器中的工具转换为 OpenAI Functions API 格式

    OpenAI Functions 格式:
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "Tool description",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param1"]
            }
        }
    }
    """
    import logging
    logger = logging.getLogger(__name__)

    tools = coordinator.list_tools()
    openai_functions = []

    # 🔥 调试日志
    mcp_dynamic_count = sum(1 for t in tools if t.category == "mcp_dynamic")
    logger.info(f"🔧 tools_to_openai_functions: 总共 {len(tools)} 个工具 (MCP动态: {mcp_dynamic_count})")

    for tool in tools:
        function_def = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": _build_parameters_schema(tool)
            }
        }
        openai_functions.append(function_def)

    logger.info(f"🔧 转换为 OpenAI Functions 格式完成: {len(openai_functions)} 个工具")

    return openai_functions


def _build_parameters_schema(tool) -> Dict[str, Any]:
    """构建工具的参数 JSON Schema"""
    properties = {}
    required = []

    if tool.parameters:
        for param_name, param in tool.parameters.items():
            param_schema = {
                "type": _map_type(param.type),
                "description": param.description
            }

            # 添加默认值
            if param.default is not None:
                param_schema["default"] = param.default

            properties[param_name] = param_schema

            # 记录必需参数
            if param.required:
                required.append(param_name)

    schema = {
        "type": "object",
        "properties": properties
    }

    if required:
        schema["required"] = required

    return schema


def _map_type(param_type: str) -> str:
    """映射内部类型到 JSON Schema 类型"""
    type_mapping = {
        "string": "string",
        "integer": "integer",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
        "number": "number"
    }
    return type_mapping.get(param_type, "string")


def parse_tool_call_arguments(arguments: str) -> Dict[str, Any]:
    """
    解析工具调用参数(JSON 字符串 -> 字典)

    Args:
        arguments: OpenAI 返回的 JSON 字符串参数

    Returns:
        参数字典
    """
    try:
        return json.loads(arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid tool call arguments JSON: {e}")


def format_tool_call_for_ai(tool_name: str, parameters: Dict[str, Any]) -> str:
    """
    格式化工具调用为 AI 可读的文本

    用于将工具执行结果反馈给 AI
    """
    params_str = ", ".join([f"{k}={v}" for k, v in parameters.items()])
    return f"调用工具: {tool_name}({params_str})"

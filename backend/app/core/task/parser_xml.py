"""
XML 工具调用解析器 - 解析 Cline 风格的 XML 标签工具调用
"""

import re
import logging
from typing import List, Dict, Any, Optional


logger = logging.getLogger(__name__)


class XMLToolCallParser:
    """XML 格式的工具调用解析器（Cline 风格）"""

    def extract_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        从 AI 响应中提取 XML 格式的工具调用

        格式示例：
        <tool_name>
          <param1>value1</param1>
          <param2>value2</param2>
        </tool_name>
        """
        tool_calls = []

        # 常见的工具名称模式
        tool_names = [
            "read_file", "list_files", "write_to_file", "replace_in_file",
            "git_status", "git_log", "git_diff", "git_branch",
            "search_files", "list_code_definitions"
        ]

        for tool_name in tool_names:
            # 匹配 XML 标签格式的工具调用
            pattern = rf"<{tool_name}>(.*?)</{tool_name}>"
            matches = re.findall(pattern, response, re.DOTALL)

            for match in matches:
                # 提取参数
                parameters = self._parse_xml_parameters(match)

                if parameters is not None:
                    tool_calls.append({
                        "name": tool_name,
                        "parameters": parameters
                    })

        logger.info(f"提取到 {len(tool_calls)} 个 XML 工具调用")
        return tool_calls

    def _parse_xml_parameters(self, xml_content: str) -> Optional[Dict[str, Any]]:
        """解析 XML 参数内容"""
        parameters = {}

        # 匹配所有参数标签：<param_name>value</param_name>
        pattern = r"<(\w+)>([^<]+)</\1>"
        matches = re.findall(pattern, xml_content)

        for param_name, param_value in matches:
            # 清理值（去除空白字符）
            param_value = param_value.strip()

            # 尝试转换为合适的类型
            param_value = self._convert_parameter_type(param_value)

            parameters[param_name] = param_value

        return parameters if parameters else None

    def _convert_parameter_type(self, value: str) -> Any:
        """尝试将字符串值转换为合适的类型"""
        # 布尔值
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # 数字
        if value.isdigit():
            return int(value)

        # 列表/数组（空方括号）
        if value == "[]":
            return []

        # 对象（空花括号）
        if value == "{}":
            return {}

        # 保持字符串
        return value

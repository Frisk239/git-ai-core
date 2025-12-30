"""
工具调用解析器 - 从 AI 响应中提取工具调用

借鉴 Cline 的 parseAssistantMessageV2
"""

import json
import logging
import re
import ast
from typing import List, Dict, Any, Optional


logger = logging.getLogger(__name__)


class ToolCallParser:
    """工具调用解析器"""

    def extract_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        从 AI 响应中提取工具调用

        支持多种格式：
        1. ```tool ... ``` 代码块
        2. ```json ... ``` 代码块
        3. 直接的 JSON 对象
        """
        tool_calls = []

        # 方法 1: 查找 ```tool 代码块
        tool_calls.extend(self._extract_from_tool_blocks(response))

        # 方法 2: 查找 ```json 代码块（如果方法 1 没有找到）
        if not tool_calls:
            tool_calls.extend(self._extract_from_json_blocks(response))

        # 方法 3: 尝试直接解析 JSON（如果前两种方法都没有找到）
        if not tool_calls:
            tool_calls.extend(self._extract_from_direct_json(response))

        logger.info(f"提取到 {len(tool_calls)} 个工具调用")
        for i, call in enumerate(tool_calls):
            logger.debug(f"  工具 {i+1}: {call.get('name')}")

        return tool_calls

    def _extract_from_tool_blocks(self, response: str) -> List[Dict[str, Any]]:
        """从 ```tool 代码块中提取"""
        tool_calls = []

        # 匹配 ```tool ... ``` 代码块
        pattern = r'```tool\s*\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)

        for match in matches:
            tool_calls.extend(self._parse_tool_call_text(match))

        return tool_calls

    def _extract_from_json_blocks(self, response: str) -> List[Dict[str, Any]]:
        """从 ```json 代码块中提取"""
        tool_calls = []

        # 匹配 ```json ... ``` 代码块
        pattern = r'```json\s*\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)

        for match in matches:
            tool_calls.extend(self._parse_tool_call_text(match))

        return tool_calls

    def _extract_from_direct_json(self, response: str) -> List[Dict[str, Any]]:
        """直接从文本中提取 JSON 对象"""
        tool_calls = []

        # 尝试找到 JSON 对象模式
        # 匹配 { "name": "...", "parameters": {...} }
        pattern = r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{[^}]*\}\s*\}'
        matches = re.findall(pattern, response)

        for match in matches:
            try:
                tool_call = json.loads(match)
                if self._validate_tool_call(tool_call):
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue

        return tool_calls

    def _parse_tool_call_text(self, text: str) -> List[Dict[str, Any]]:
        """解析工具调用文本"""
        tool_calls = []

        # 按行分割，尝试每一行作为 JSON 对象
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 尝试解析 JSON
            tool_call = self._try_parse_json(line)
            if tool_call and self._validate_tool_call(tool_call):
                tool_calls.append(tool_call)

        return tool_calls

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """尝试解析 JSON，支持多种格式"""
        # 方法 1: 标准 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 方法 2: 处理尾随逗号
        try:
            # 移除尾随逗号
            cleaned = re.sub(r',\s*([}\]])', r'\1', text)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 方法 3: 使用 ast.literal_eval（更宽松）
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            pass

        return None

    def _validate_tool_call(self, tool_call: Dict[str, Any]) -> bool:
        """验证工具调用的结构"""
        # 必须有 name 字段
        if "name" not in tool_call:
            return False

        # name 必须是字符串
        if not isinstance(tool_call["name"], str):
            return False

        # 应该有 parameters 字段（可选）
        if "parameters" in tool_call and not isinstance(tool_call["parameters"], dict):
            return False

        return True

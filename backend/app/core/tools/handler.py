"""
工具处理器基类
借鉴 Cline 的 IToolHandler 接口设计
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from .base import ToolSpec, ToolResult, ToolContext, ToolCall


logger = logging.getLogger(__name__)


class BaseToolHandler(ABC):
    """工具处理器基类"""

    def __init__(self):
        self._spec: ToolSpec = None

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @abstractmethod
    def get_spec(self) -> ToolSpec:
        """获取工具规范"""
        pass

    @abstractmethod
    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行工具

        Args:
            parameters: 验证后的参数
            context: 工具执行上下文

        Returns:
            工具执行结果
        """
        pass

    def validate_parameters(self, parameters: Dict[str, Any]) -> Any:
        """验证参数

        默认实现：基本验证
        子类可以重写以使用 Pydantic 等进行复杂验证

        Args:
            parameters: 原始参数字典

        Returns:
            验证后的参数

        Raises:
            ValueError: 参数验证失败
        """
        spec = self.get_spec()

        # 检查必需参数
        for param_name, param_def in spec.parameters.items():
            if param_def.required and param_name not in parameters:
                raise ValueError(f"缺少必需参数: {param_name}")

            # 检查参数类型
            if param_name in parameters:
                value = parameters[param_name]
                if not self._check_type(value, param_def.type):
                    raise ValueError(
                        f"参数 {param_name} 类型错误: 期望 {param_def.type}, 实际 {type(value).__name__}"
                    )

        return parameters

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型"""
        type_mapping = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool,
            "array": list,
            "object": dict
        }

        expected_python_type = type_mapping.get(expected_type)
        if not expected_python_type:
            return True  # 未知类型，跳过检查

        return isinstance(value, expected_python_type)

    async def safe_execute(self, tool_call: ToolCall, context: ToolContext) -> ToolResult:
        """安全执行工具（带错误处理）

        Args:
            tool_call: 工具调用请求
            context: 工具执行上下文

        Returns:
            工具执行结果
        """
        try:
            logger.info(f"执行工具: {tool_call.name}")

            # 验证参数
            validated_params = self.validate_parameters(tool_call.parameters)

            # 执行工具
            result = await self.execute(validated_params, context)

            logger.info(f"工具 {tool_call.name} 执行成功")
            return ToolResult(success=True, data=result)

        except ValueError as e:
            logger.error(f"工具 {tool_call.name} 参数验证失败: {e}")
            return ToolResult(success=False, error=f"参数验证失败: {str(e)}")

        except Exception as e:
            logger.error(f"工具 {tool_call.name} 执行失败: {e}", exc_info=True)
            return ToolResult(success=False, error=f"执行失败: {str(e)}")

"""
工具协调器
借鉴 Cline 的 ToolExecutorCoordinator，统一管理所有工具的注册和执行
"""

from typing import Dict, List, Optional
import logging

from .base import ToolSpec, ToolResult, ToolContext, ToolCall
from .handler import BaseToolHandler


logger = logging.getLogger(__name__)


class ToolCoordinator:
    """工具协调器 - 管理工具的注册和执行"""

    def __init__(self):
        self.handlers: Dict[str, BaseToolHandler] = {}
        self._initialized = False

    def register(self, handler: BaseToolHandler):
        """注册工具处理器

        Args:
            handler: 工具处理器实例
        """
        tool_name = handler.name
        self.handlers[tool_name] = handler
        logger.info(f"注册工具: {tool_name}")

    def unregister(self, tool_name: str):
        """注销工具处理器

        Args:
            tool_name: 工具名称
        """
        if tool_name in self.handlers:
            del self.handlers[tool_name]
            logger.info(f"注销工具: {tool_name}")

    def has(self, tool_name: str) -> bool:
        """检查工具是否存在

        Args:
            tool_name: 工具名称

        Returns:
            是否存在
        """
        return tool_name in self.handlers

    def get_handler(self, tool_name: str) -> Optional[BaseToolHandler]:
        """获取工具处理器

        Args:
            tool_name: 工具名称

        Returns:
            工具处理器实例，不存在返回 None
        """
        return self.handlers.get(tool_name)

    async def execute(self, tool_call: ToolCall, context: ToolContext) -> ToolResult:
        """执行工具调用

        Args:
            tool_call: 工具调用请求
            context: 工具执行上下文

        Returns:
            工具执行结果
        """
        handler = self.get_handler(tool_call.name)

        if not handler:
            logger.error(f"工具不存在: {tool_call.name}")
            return ToolResult(
                success=False,
                error=f"未知工具: {tool_call.name}"
            )

        # 执行工具
        return await handler.safe_execute(tool_call, context)

    async def execute_batch(
        self,
        tool_calls: List[ToolCall],
        context: ToolContext
    ) -> List[ToolResult]:
        """批量执行工具调用

        Args:
            tool_calls: 工具调用请求列表
            context: 工具执行上下文

        Returns:
            工具执行结果列表
        """
        results = []
        for tool_call in tool_calls:
            result = await self.execute(tool_call, context)
            results.append(result)

        return results

    def list_tools(self) -> List[ToolSpec]:
        """列出所有已注册的工具

        Returns:
            工具规范列表
        """
        return [handler.get_spec() for handler in self.handlers.values()]

    def list_tools_by_category(self, category: str) -> List[ToolSpec]:
        """按类别列出工具

        Args:
            category: 工具类别

        Returns:
            该类别的工具规范列表
        """
        return [
            handler.get_spec()
            for handler in self.handlers.values()
            if handler.get_spec().category == category
        ]

    def get_tools_description(self) -> str:
        """获取工具列表的文本描述（用于系统提示词）

        Returns:
            工具列表描述文本
        """
        descriptions = []

        for spec in self.list_tools():
            descriptions.append(f"- {spec.name}: {spec.description}")

            # 添加参数说明
            if spec.parameters:
                for param_name, param_def in spec.parameters.items():
                    required = "必需" if param_def.required else "可选"
                    descriptions.append(
                        f"  - {param_name} ({param_def.type}, {required}): {param_def.description}"
                    )

            descriptions.append("")  # 空行分隔

        return "\n".join(descriptions)

    def initialize_default_tools(self):
        """初始化默认工具集（静态工具）"""
        if self._initialized:
            return

        # 导入并注册默认工具
        from .handlers.file_handler import FileReadToolHandler, FileListToolHandler
        from .handlers.git_handler import (
            GitDiffToolHandler,
            GitLogToolHandler,
            GitStatusToolHandler,
            GitBranchToolHandler
        )
        from .handlers.search_handler import SearchFilesToolHandler
        from .handlers.write_handler import WriteToFileToolHandler, ReplaceInFileToolHandler
        from .handlers.code_handler import ListCodeDefinitionsToolHandler
        from .handlers.completion_handler import AttemptCompletionToolHandler
        from .handlers.mcp_handler import (
            UseMcpToolHandler,
            AccessMcpResourceHandler,
            ListMcpServersHandler
        )

        # 注册文件工具
        self.register(FileReadToolHandler())
        self.register(FileListToolHandler())
        self.register(WriteToFileToolHandler())
        self.register(ReplaceInFileToolHandler())

        # 注册 Git 工具
        self.register(GitDiffToolHandler())
        self.register(GitLogToolHandler())
        self.register(GitStatusToolHandler())
        self.register(GitBranchToolHandler())

        # 注册搜索工具
        self.register(SearchFilesToolHandler())

        # 注册代码分析工具
        self.register(ListCodeDefinitionsToolHandler())

        # 注册任务完成工具(关键!)
        self.register(AttemptCompletionToolHandler())

        # 注册 MCP 工具（保留兼容性）
        self.register(UseMcpToolHandler())
        self.register(AccessMcpResourceHandler())
        self.register(ListMcpServersHandler())

        self._initialized = True
        logger.info(f"默认工具初始化完成，共注册 {len(self.handlers)} 个工具")

    async def initialize_mcp_tools(self, mcp_manager):
        """
        🔥 参考 Cline：动态注册所有已启动 MCP 服务器的工具

        将每个 MCP 工具转换为独立的 AI 可调用工具

        Args:
            mcp_manager: 已启动服务器的 MCP 服务器管理器实例
        """
        try:
            from .mcp_dynamic import register_all_mcp_tools

            # 注册所有 MCP 工具（传入已启动服务器的 mcp_manager）
            logger.info("🔧 开始动态注册 MCP 工具...")
            count = await register_all_mcp_tools(self, mcp_manager)

            if count > 0:
                logger.info(f"✅ 成功注册 {count} 个 MCP 动态工具")
            else:
                logger.warning("⚠️ 没有注册任何 MCP 工具（没有运行中的 MCP 服务器）")

        except Exception as e:
            logger.error(f"注册 MCP 工具失败: {e}", exc_info=True)


# 全局单例
_global_coordinator: Optional[ToolCoordinator] = None


def get_tool_coordinator() -> ToolCoordinator:
    """获取全局工具协调器单例

    Returns:
        工具协调器实例
    """
    global _global_coordinator

    if _global_coordinator is None:
        _global_coordinator = ToolCoordinator()
        _global_coordinator.initialize_default_tools()

    return _global_coordinator

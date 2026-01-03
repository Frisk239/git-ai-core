"""
任务完成工具处理器
借鉴 Cline 的 attempt_completion 工具

关键作用:
1. 明确标记任务完成 - AI 必须主动调用此工具才能结束任务
2. 防止提前退出 - 避免 AI 在不完成所有步骤的情况下就停止
3. 提供最终结果 - 总结任务完成情况
"""

from typing import Any, Dict
import logging

from ..base import ToolSpec, ToolParameter, ToolContext
from ..handler import BaseToolHandler


logger = logging.getLogger(__name__)


class AttemptCompletionToolHandler(BaseToolHandler):
    """
    任务完成工具处理器

    使用场景:
    - AI 已完成所有必要的工具调用
    - 所有文件操作、代码分析等都已完成
    - 需要向用户呈现最终结果
    """

    @property
    def name(self) -> str:
        return "attempt_completion"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="attempt_completion",
            description=(
                "在每个工具使用后,用户会响应该工具的使用结果,即成功或失败以及失败原因。"
                "一旦你收到工具使用的结果并可以确认任务已完成,使用此工具向用户展示你的工作成果。"
                "你可以选择提供一个 CLI 命令来展示你的工作成果。"
                "如果用户对结果不满意,可能会提供反馈,你可以利用这些反馈进行改进并重试。"
                "\n\n"
                "**重要提示 (CRITICAL - 必须严格遵守)**:\n"
                "此工具只能在确认所有工具使用都成功**并且所有任务都已完成**之后才能使用！\n"
                "如果未完成所有用户要求的任务就使用此工具,会导致任务失败和系统错误。\n"
                "在使用此工具之前,你必须在心中问自己:\n"
                "1. 是否已确认之前的所有工具使用都成功了?\n"
                "2. 是否已完成用户要求的所有任务?(例如:创建文件、修改代码、生成报告等)\n"
                "如果任何答案是否定的,则**绝对不要**使用此工具,而是继续执行必要的工具调用。"
            ),
            category="completion",
            parameters={
                "result": ToolParameter(
                    name="result",
                    type="string",
                    description=(
                        "任务结果的清晰、具体的描述。"
                        "这应该是对结果的简洁总结,通常 1-2 段话即可。"
                        "提供基础信息和亮点,但不要深入具体细节。"
                    ),
                    required=True
                ),
                "command": ToolParameter(
                    name="command",
                    type="string",
                    description=(
                        "用于展示工作成果的可执行 CLI 命令(可选)。"
                        "\n"
                        "**示例**:\n"
                        "- `python backend/report.py` - 运行生成的报告脚本\n"
                        "- `cat backend/report.md` - 查看生成的报告内容\n"
                        "- `open backend/report.md` - 在编辑器中打开报告\n"
                        "\n"
                        "**限制**:\n"
                        "- 不要使用仅打印文本的命令(如 echo, cat)\n"
                        "- 确保命令适用于当前操作系统\n"
                        "- 命令必须格式正确且不包含有害指令"
                    ),
                    required=False
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """标记任务完成"""
        result = parameters.get("result", "")
        command = parameters.get("command")

        logger.info(f"任务已完成: {result[:100]}...")

        response = {
            "type": "completion",
            "success": True,
            "result": result
        }

        if command:
            response["suggested_command"] = command
            logger.info(f"建议执行命令: {command}")

        return response

"""
任务执行引擎 - 借鉴 Cline 的递归任务循环架构

这是核心的任务执行器，负责：
1. 启动任务
2. 递归任务循环
3. 工具调用管理
4. 错误处理和重试
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime

from app.core.ai_manager import AIManager
from app.core.tools import (
    ToolCoordinator,
    ToolCall,
    ToolContext,
    get_tool_coordinator
)
from app.core.task.task_state import TaskState
from app.core.task.tools_converter import tools_to_openai_functions, parse_tool_call_arguments
from app.core.task.prompt_builder import PromptBuilder


logger = logging.getLogger(__name__)


class TaskEngine:
    """
    任务执行引擎 - Git AI Core 的核心

    类似 Cline 的 Task 类，实现递归任务循环
    """

    def __init__(
        self,
        ai_manager: Optional[AIManager] = None,
        tool_coordinator: Optional[ToolCoordinator] = None,
        max_iterations: int = 10,
        max_consecutive_mistakes: int = 3
    ):
        self.ai_manager = ai_manager or AIManager()
        self.tool_coordinator = tool_coordinator or get_tool_coordinator()
        self.prompt_builder = PromptBuilder(self.tool_coordinator)
        self.tools_definition = tools_to_openai_functions(self.tool_coordinator)

        # 配置
        self.max_iterations = max_iterations
        self.max_consecutive_mistakes = max_consecutive_mistakes

        # 任务状态
        self.task_state = TaskState()
        self.conversation_history = []

    async def execute_task(
        self,
        user_input: str,
        repository_path: str,
        ai_config: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        执行任务 - 主入口点

        Args:
            user_input: 用户输入
            repository_path: Git 仓库路径
            ai_config: AI 配置

        Yields:
            任务进度信息（用于流式响应）
        """
        logger.info(f"=== 开始任务 ===")
        logger.info(f"用户输入: {user_input[:100]}...")
        logger.info(f"仓库路径: {repository_path}")

        # 1. 初始化
        self.task_state.reset_for_new_task()
        context = ToolContext(
            repository_path=repository_path,
            conversation_history=[],
            metadata={"ai_config": ai_config}
        )

        # 2. 构建初始用户消息
        user_content = [{
            "type": "text",
            "text": f"<task>\n{user_input}\n</task>"
        }]

        # 3. 启动任务循环
        try:
            async for event in self._task_loop(user_content, context, ai_config):
                yield event
        except Exception as e:
            logger.error(f"任务执行失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"任务执行失败: {str(e)}"
            }

        logger.info(f"=== 任务结束 ===")

    async def _task_loop(
        self,
        initial_user_content: List[Dict[str, Any]],
        context: ToolContext,
        ai_config: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        递归任务循环 - 核心逻辑

        类似 Cline 的 initiateTaskLoop + recursivelyMakeClineRequests
        """
        next_user_content = initial_user_content
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # 检查中止标志
            if self.task_state.should_abort():
                logger.info("任务被中止")
                yield {
                    "type": "aborted",
                    "iteration": iteration
                }
                break

            # 检查错误次数
            if self.task_state.consecutive_mistake_count >= self.max_consecutive_mistakes:
                logger.error(f"达到最大连续错误次数: {self.task_state.consecutive_mistake_count}")
                yield {
                    "type": "error",
                    "message": f"达到最大连续错误次数 ({self.task_state.consecutive_mistake_count})",
                    "iteration": iteration
                }
                break

            logger.info(f"=== 迭代 {iteration} ===")

            # 执行单次请求
            did_end_loop = False
            async for event in self._execute_single_request(next_user_content, context, ai_config, iteration):
                yield event

                # 检查是否结束
                if event.get("type") == "completion":
                    did_end_loop = True
                elif event.get("type") == "error":
                    self.task_state.increment_mistake_count()

            if did_end_loop:
                logger.info("任务完成")
                break
            else:
                # 继续循环，提示 AI 使用工具
                next_user_content = [{
                    "type": "text",
                    "text": "请使用工具来完成任务，或者如果任务已完成，请明确告知。"
                }]

    async def _execute_single_request(
        self,
        user_content: List[Dict[str, Any]],
        context: ToolContext,
        ai_config: Dict[str, Any],
        iteration: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        执行单次 API 请求（使用 Tools API）

        类似 Cline 的 attemptApiRequest + 工具执行
        """
        # 1. 构建消息历史
        messages = self._build_messages(user_content)

        # 2. 生成系统提示词
        system_prompt = await self.prompt_builder.build_prompt(context)

        # 3. 调用 AI（使用 Tools API）
        self.task_state.increment_api_request_count()

        yield {
            "type": "api_request_started",
            "iteration": iteration,
            "message_count": len(messages)
        }

        try:
            response = await self._call_ai_with_tools(messages, system_prompt, ai_config)

            if not response:
                raise ValueError("AI 返回空响应")

            # 4. 解析 AI 响应
            assistant_content = response.get("content", "")
            tool_calls_api = response.get("tool_calls", [])

            yield {
                "type": "api_response",
                "content": assistant_content,
                "iteration": iteration
            }

            # 5. 保存 AI 响应到历史
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_content
            })

            # 6. 处理工具调用
            if not tool_calls_api:
                # 没有工具调用，任务可能完成
                if assistant_content:
                    yield {
                        "type": "completion",
                        "content": assistant_content,
                        "iteration": iteration
                    }
                return

            # 7. 转换工具调用格式
            tool_calls = []
            for tc in tool_calls_api:
                try:
                    arguments = parse_tool_call_arguments(tc["arguments"])
                    tool_calls.append({
                        "name": tc["name"],
                        "parameters": arguments
                    })
                except Exception as e:
                    logger.error(f"解析工具调用参数失败: {e}")

            if not tool_calls:
                logger.warning("工具调用解析失败，跳过")
                return

            # 8. 执行工具
            yield {
                "type": "tool_calls_detected",
                "tool_calls": tool_calls,
                "iteration": iteration
            }

            # 9. 执行所有工具调用
            tool_results = []

            for tool_call_dict in tool_calls:
                # 流式返回工具执行进度
                yield {
                    "type": "tool_execution_started",
                    "tool_name": tool_call_dict.get("name"),
                    "iteration": iteration
                }

                # 执行工具
                result = await self._execute_tool(tool_call_dict, context)

                yield {
                    "type": "tool_execution_completed",
                    "tool_name": tool_call_dict.get("name"),
                    "result": result,
                    "iteration": iteration
                }

                tool_results.append(result)

            # 10. 将工具结果添加到对话历史
            formatted_results = self._format_tool_results_for_ai(tool_results)
            self.conversation_history.append({
                "role": "user",
                "content": formatted_results
            })

        except Exception as e:
            logger.error(f"请求执行失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": str(e),
                "iteration": iteration
            }

    def _build_messages(self, user_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建消息列表"""
        messages = []

        # 添加历史消息（排除工具结果消息，因为它们会重新构建）
        for msg in self.conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # 添加当前用户内容
        for content in user_content:
            if content["type"] == "text":
                messages.append({
                    "role": "user",
                    "content": content["text"]
                })

        return messages

    async def _call_ai(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        ai_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """调用 AI（普通模式，不使用工具）"""
        try:
            response = await self.ai_manager.chat(
                provider=ai_config["ai_provider"],
                model=ai_config["ai_model"],
                messages=messages,
                api_key=ai_config["ai_api_key"],
                base_url=ai_config.get("ai_base_url"),
                temperature=ai_config.get("temperature", 0.7),
                max_tokens=ai_config.get("max_tokens", 4000),
                system_prompt=system_prompt
            )

            return response

        except Exception as e:
            logger.error(f"AI 调用失败: {e}", exc_info=True)
            return None

    async def _call_ai_with_tools(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        ai_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """调用 AI（使用 Tools API）"""
        try:
            response = await self.ai_manager.chat_with_tools(
                provider=ai_config["ai_provider"],
                model=ai_config["ai_model"],
                messages=messages,
                api_key=ai_config["ai_api_key"],
                tools=self.tools_definition,
                base_url=ai_config.get("ai_base_url"),
                temperature=ai_config.get("temperature", 0.7),
                max_tokens=ai_config.get("max_tokens", 4000),
                system_prompt=system_prompt
            )

            return response

        except Exception as e:
            logger.error(f"AI 调用失败: {e}", exc_info=True)
            return None

    async def _execute_tool(
        self,
        tool_call_dict: Dict[str, Any],
        context: ToolContext
    ) -> Dict[str, Any]:
        """执行单个工具"""
        tool_name = tool_call_dict.get("name")
        parameters = tool_call_dict.get("parameters", {})

        # 创建 ToolCall 对象
        tool_call = ToolCall(
            id=str(uuid.uuid4()),
            name=tool_name,
            parameters=parameters
        )

        # 执行工具
        result = await self.tool_coordinator.execute(tool_call, context)

        # 返回格式化结果
        return {
            "tool": tool_name,
            "success": result.success,
            "data": result.data,
            "error": result.error
        }

    def _format_tool_results_for_ai(self, results: List[Dict[str, Any]]) -> str:
        """格式化工具结果用于 AI 理解（使用 XML 格式）"""
        formatted = []

        for result in results:
            tool_name = result["tool"]

            if result["success"]:
                # 使用 XML 格式返回成功结果
                formatted.append(f"<response>")
                formatted.append(f"<tool>{tool_name}</tool>")
                formatted.append(f"<status>success</status>")

                # 格式化数据
                if result["data"]:
                    data_str = json.dumps(result["data"], ensure_ascii=False, indent=2)
                    formatted.append(f"<data>")
                    formatted.append(f"```json\n{data_str}\n```")
                    formatted.append(f"</data>")

                formatted.append(f"</response>")
            else:
                # 使用 XML 格式返回失败结果
                formatted.append(f"<response>")
                formatted.append(f"<tool>{tool_name}</tool>")
                formatted.append(f"<status>error</status>")
                formatted.append(f"<error>{result.get('error', 'Unknown error')}</error>")
                formatted.append(f"</response>")

            formatted.append("")  # 空行分隔

        return "\n".join(formatted)

    def abort(self):
        """中止当前任务"""
        logger.info("中止任务")
        self.task_state.abort = True

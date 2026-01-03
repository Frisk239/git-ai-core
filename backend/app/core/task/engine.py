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
from app.core.context import TokenCounter, CompressionStrategy
from app.core.context.conversation_history import ConversationHistoryManager, ToolCall
from app.core.context.task_history import TaskHistoryManager


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
        max_iterations: int = 999,  # 取消迭代限制，设置为很大的值
        max_consecutive_mistakes: int = 3
    ):
        self.ai_manager = ai_manager or AIManager()
        self.tool_coordinator = tool_coordinator or get_tool_coordinator()
        self.prompt_builder = PromptBuilder(self.tool_coordinator)
        # 🔥 移除这里的 tools_definition 初始化，改为每次执行任务时动态获取
        # self.tools_definition = tools_to_openai_functions(self.tool_coordinator)

        # 上下文管理
        self.token_counter = TokenCounter()
        self.compression_strategy = CompressionStrategy(self.ai_manager)

        # 对话历史管理器（延迟初始化）
        self.history_manager: Optional[ConversationHistoryManager] = None

        # 任务历史管理器（延迟初始化）
        self.task_history_manager: Optional[TaskHistoryManager] = None

        # 配置
        self.max_iterations = max_iterations
        self.max_consecutive_mistakes = max_consecutive_mistakes

        # 任务状态
        self.task_state = TaskState()
        self.conversation_history = []  # 兼容旧代码，后续移除

    async def execute_task(
        self,
        user_input: str,
        repository_path: str,
        ai_config: Dict[str, Any],
        task_id: Optional[str] = None,  # 支持继续现有任务
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        执行任务 - 主入口点

        Args:
            user_input: 用户输入
            repository_path: Git 仓库路径
            ai_config: AI 配置
            task_id: 可选的任务 ID,用于继续现有任务(实现记忆功能)

        Yields:
            任务进度信息（用于流式响应）
        """
        # 如果没有提供 task_id,生成新的
        is_new_task = task_id is None
        if is_new_task:
            task_id = str(uuid.uuid4())[:8]

        print("\n" + "="*80)
        if is_new_task:
            print(f"🚀 开始执行任务")
        else:
            print(f"🔄 继续任务 (记忆模式)")
        print("="*80)
        print(f"📝 用户输入: {user_input}")
        print(f"📁 仓库路径: {repository_path}")
        print(f"🆔 任务 ID: {task_id}")
        print(f"🤖 AI 配置: {ai_config.get('ai_provider')} - {ai_config.get('ai_model')}")
        print("="*80 + "\n")

        logger.info(f"=== {'开始新任务' if is_new_task else '继续任务'} (ID: {task_id}) ===")
        logger.info(f"用户输入: {user_input[:100]}...")
        logger.info(f"仓库路径: {repository_path}")

        # 1. 初始化任务历史管理器
        self.task_history_manager = TaskHistoryManager(
            workspace_path=repository_path
        )
        await self.task_history_manager.load_history()

        # 2. 初始化对话历史管理器
        self.history_manager = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=repository_path
        )

        # 尝试加载历史记录（恢复任务）
        loaded_history = await self.history_manager.load_history()
        if loaded_history:
            print(f"[INFO] 已加载任务历史: {len(self.history_manager.messages)} 条消息")
            # 🔥 关键修复：将历史消息复制到 conversation_history，这样 _build_messages 才能使用
            self.conversation_history = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in self.history_manager.messages
            ]
            print(f"[INFO] 已将 {len(self.conversation_history)} 条历史消息加载到上下文")

        # 3. 添加或更新任务到历史列表
        task_description = user_input[:100] + "..." if len(user_input) > 100 else user_input
        history_item = self.task_history_manager.add_or_update_task(
            task_id=task_id,
            task_description=task_description,
            api_provider=ai_config.get("ai_provider"),
            api_model=ai_config.get("ai_model"),
            repository_path=repository_path,
        )
        print(f"[INFO] 任务 ID: {task_id}")

        # 4. 初始化任务状态
        self.task_state.reset_for_new_task()
        context = ToolContext(
            repository_path=repository_path,
            conversation_history=[],
            metadata={"ai_config": ai_config, "task_id": task_id}
        )

        # 5. 将用户输入添加到历史
        self.history_manager.append_message(
            role="user",
            content=f"<task>\n{user_input}\n</task>"
        )
        # 🔥 同时更新 conversation_history（用于后续的 API 调用）
        self.conversation_history.append({
            "role": "user",
            "content": f"<task>\n{user_input}\n</task>"
        })

        # 6. 构建初始用户消息
        user_content = [{
            "type": "text",
            "text": f"<task>\n{user_input}\n</task>"
        }]

        # 5. 启动任务循环
        try:
            # 首先发送任务 ID 事件(让前端知道当前任务 ID)
            yield {
                "type": "task_started",
                "task_id": task_id,
                "is_new_task": is_new_task
            }

            async for event in self._task_loop(user_content, context, ai_config):
                yield event
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"❌ 任务执行失败: {e}")
            print(f"{'='*80}\n")
            logger.error(f"任务执行失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"任务执行失败: {str(e)}"
            }

        # 7. 保存对话历史和任务历史
        finally:
            # 保存对话历史
            if self.history_manager:
                success = await self.history_manager.save_history()
                if success:
                    stats = self.history_manager.get_stats()
                    print(f"\n💾 对话历史已保存:")
                    print(f"   - 总消息数: {stats['total_messages']}")
                    print(f"   - 用户消息: {stats['user_messages']}")
                    print(f"   - AI 消息: {stats['assistant_messages']}")
                    print(f"   - 总 tokens: {stats['total_tokens']}")

            # 更新并保存任务历史统计
            if self.task_history_manager:
                # 更新当前任务的统计信息
                history_item = self.task_history_manager.get_task(task_id)
                if history_item and self.history_manager:
                    # 更新 token 统计
                    stats = self.history_manager.get_stats()
                    history_item.tokens_in = stats['total_tokens'] // 2  # 估算
                    history_item.tokens_out = stats['total_tokens'] - history_item.tokens_in
                    history_item.size = stats.get('task_dir_size', 0)

                # 保存任务历史列表
                await self.task_history_manager.save_history()

        print("\n" + "="*80)
        print("✅ 任务执行完成")
        print("="*80 + "\n")

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
                print(f"\n⚠️  任务被中止")
                logger.info("任务被中止")
                yield {
                    "type": "aborted",
                    "iteration": iteration
                }
                break

            # 检查错误次数
            if self.task_state.consecutive_mistake_count >= self.max_consecutive_mistakes:
                print(f"\n❌ 达到最大连续错误次数: {self.task_state.consecutive_mistake_count}")
                logger.error(f"达到最大连续错误次数: {self.task_state.consecutive_mistake_count}")
                yield {
                    "type": "error",
                    "message": f"达到最大连续错误次数 ({self.task_state.consecutive_mistake_count})",
                    "iteration": iteration
                }
                break

            print(f"\n{'─'*80}")
            print(f"🔄 迭代 {iteration}/{self.max_iterations}")
            print(f"{'─'*80}\n")

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
                print(f"\n✅ 任务完成，退出循环")
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
        # 1. 构建消息历史（带上下文压缩）
        messages = await self._build_messages(user_content, ai_config)

        # 2. 生成系统提示词
        system_prompt = await self.prompt_builder.build_prompt(context)

        # 3. 调用 AI（使用 Tools API）
        self.task_state.increment_api_request_count()

        print(f"📤 发送 API 请求...")
        print(f"   - 消息数量: {len(messages)}")
        print(f"   - 系统提示词长度: {len(system_prompt)} 字符")

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

            print(f"📥 收到 AI 响应")
            print(f"   - 响应内容长度: {len(assistant_content)} 字符")
            print(f"   - 工具调用数量: {len(tool_calls_api)}")

            if assistant_content:
                preview = assistant_content[:100] + "..." if len(assistant_content) > 100 else assistant_content
                print(f"   - 内容预览: {preview}")

            yield {
                "type": "api_response",
                "content": assistant_content,
                "iteration": iteration
            }

            # 5. 保存 AI 响应到历史记录
            if self.history_manager:
                # 转换工具调用格式
                tool_calls_for_history = None
                if tool_calls_api:
                    tool_calls_for_history = [
                        ToolCall(
                            id=str(uuid.uuid4()),
                            name=tc["name"],
                            parameters=parse_tool_call_arguments(tc["arguments"]),
                            result=None,  # 工具结果稍后添加
                        )
                        for tc in tool_calls_api
                    ]

                self.history_manager.append_message(
                    role="assistant",
                    content=assistant_content,
                    tool_calls=tool_calls_for_history,
                    model=ai_config.get("ai_model"),
                )

            # 6. 兼容旧代码
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_content
            })

            # 7. 处理工具调用
            if not tool_calls_api:
                # 没有工具调用，任务可能完成
                print(f"\n✨ 没有检测到工具调用，任务可能已完成")
                if assistant_content:
                    print(f"📝 最终响应: {assistant_content[:200]}...")
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
            print(f"\n🔧 检测到 {len(tool_calls)} 个工具调用:")

            for i, tc in enumerate(tool_calls, 1):
                tool_name = tc["name"]
                params = tc["parameters"]
                print(f"   {i}. {tool_name}")
                if params:
                    params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                    print(f"      参数: {params_str}")

            yield {
                "type": "tool_calls_detected",
                "tool_calls": tool_calls,
                "iteration": iteration
            }

            # 9. 执行所有工具调用
            tool_results = []
            has_completion_tool = False

            for tool_call_dict in tool_calls:
                tool_name = tool_call_dict.get("name")
                print(f"\n⚙️  执行工具: {tool_name}")

                # 检查是否是 attempt_completion 工具
                if tool_name == "attempt_completion":
                    has_completion_tool = True

                # 流式返回工具执行进度
                yield {
                    "type": "tool_execution_started",
                    "tool_name": tool_name,
                    "iteration": iteration
                }

                # 执行工具
                result = await self._execute_tool(tool_call_dict, context)

                # 打印执行结果
                if result["success"]:
                    print(f"   ✅ 工具执行成功")
                    data = result.get("data")
                    if data:
                        data_str = str(data)
                        if len(data_str) > 200:
                            print(f"   📊 结果: {data_str[:200]}...")
                        else:
                            print(f"   📊 结果: {data_str}")
                else:
                    print(f"   ❌ 工具执行失败: {result.get('error', 'Unknown error')}")

                yield {
                    "type": "tool_execution_completed",
                    "tool_name": tool_name,
                    "result": result,
                    "iteration": iteration
                }

                tool_results.append(result)

                # 更新历史记录中的工具结果
                if self.history_manager and self.history_manager.messages:
                    last_message = self.history_manager.messages[-1]
                    if last_message.tool_calls and len(last_message.tool_calls) >= len(tool_results):
                        tool_call_index = len(tool_results) - 1
                        last_message.tool_calls[tool_call_index].result = result

            # 10. 检查是否调用了 attempt_completion
            if has_completion_tool:
                yield {
                    "type": "completion",
                    "result": tool_results[-1].get("data", {}),
                    "iteration": iteration
                }
                return

            # 10. 将工具结果添加到对话历史
            formatted_results = self._format_tool_results_for_ai(tool_results)
            self.conversation_history.append({
                "role": "user",
                "content": formatted_results
            })

        except Exception as e:
            print(f"\n❌ 请求执行失败: {e}")
            logger.error(f"请求执行失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": str(e),
                "iteration": iteration
            }

    async def _build_messages(
        self,
        user_content: List[Dict[str, Any]],
        ai_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        构建消息列表（带上下文压缩和字符数限制）

        参考 Cline：工具调用历史会被转换为文本格式包含在消息中
        """
        messages = []

        # 添加历史消息（包含工具调用信息）
        if self.history_manager and self.history_manager.messages:
            for msg in self.history_manager.messages:
                # 构建消息内容
                content_parts = [msg.content]

                # 🔥 关键：如果有工具调用，转换为可读的文本格式
                # 参考 Cline：工具调用会以 "tool_name: params Result: result" 的格式显示
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        # 生成工具描述（如 "read file: xxx"）
                        tool_desc = self._get_tool_description(tc)

                        # 添加工具调用信息到内容中
                        content_parts.append(f"\n\n[工具调用] {tool_desc}")

                        # 如果有结果，添加结果
                        if tc.result:
                            if tc.result.get("success"):
                                result_content = tc.result.get("data", "")
                                # 限制结果长度
                                if isinstance(result_content, str) and len(result_content) > 500:
                                    result_content = result_content[:500] + "\n...(内容过长，已截断)"
                                content_parts.append(f"\n结果: {result_content}")
                            else:
                                error_msg = tc.result.get("error", "Unknown error")
                                content_parts.append(f"\n错误: {error_msg}")

                # 合并所有内容部分
                full_content = "\n".join(content_parts)

                messages.append({
                    "role": msg.role,
                    "content": full_content
                })
        else:
            # 兼容旧代码：使用 conversation_history
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

        # 检查是否需要压缩上下文
        model = ai_config.get("ai_model", "deepseek-chat")

        # 🔥 关键修复：使用 Cline 的两阶段压缩策略
        # 1. 先优化重复文件读取（不删除消息，只替换内容）
        # 2. 如果仍然超限，再进行三明治截断
        if self.compression_strategy.must_compress(messages, model):
            print(f"\n⚠️  上下文即将溢出，触发压缩...")

            # 使用新的压缩策略（包含文件读取优化）
            compressed = await self.compression_strategy.compress_conversation_history(
                messages,
                model,
                ai_config
            )

            print(f"✅ 上下文压缩完成")

            # 返回压缩后的消息
            return compressed

        elif self.compression_strategy.should_compress(messages, model):
            print(f"\n⚡ 上下文使用量较高，建议压缩")
            info = self.token_counter.get_compression_info(messages, model)
            print(f"   - 当前使用: {info['estimated_tokens']} tokens ({info['usage_percentage']*100:.1f}%)")
            print(f"   - 最大允许: {info['max_allowed']} tokens")

        return messages

    def _get_tool_description(self, tool_call: ToolCall) -> str:
        """
        生成工具调用的友好描述

        参考 Cline 的格式：
        - read file: xxx
        - write to file: xxx
        - search_files: xxx

        Args:
            tool_call: 工具调用对象

        Returns:
            工具描述字符串
        """
        tool_name = tool_call.name
        params = tool_call.parameters

        # 根据工具名称生成描述
        if tool_name == "read_file":
            file_path = params.get("file_path", "")
            return f"读取文件: {file_path}"

        elif tool_name == "write_to_file":
            file_path = params.get("file_path", "")
            return f"写入文件: {file_path}"

        elif tool_name == "modify_file":
            file_path = params.get("file_path", "")
            return f"修改文件: {file_path}"

        elif tool_name == "list_directory":
            path = params.get("path", "")
            recursive = params.get("recursive", False)
            return f"列出目录: {path} (递归: {recursive})"

        elif tool_name == "search_files":
            path = params.get("path", "")
            pattern = params.get("pattern", "")
            return f"搜索文件: {path} (模式: {pattern})"

        elif tool_name == "list_code_definitions":
            file_path = params.get("file_path", "")
            return f"列出代码定义: {file_path}"

        elif tool_name == "git_status":
            return "查看 Git 状态"

        elif tool_name == "git_diff":
            file_path = params.get("file_path", "")
            return f"查看 Git 差异: {file_path}"

        elif tool_name == "git_log":
            return "查看 Git 提交历史"

        elif tool_name == "attempt_completion":
            return "完成任务"

        else:
            # 通用格式
            return f"{tool_name}: {params}"

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
            # 🔥 每次调用 AI 时动态获取最新的工具定义（支持运行时添加/删除 MCP 工具）
            tools_definition = tools_to_openai_functions(self.tool_coordinator)

            response = await self.ai_manager.chat_with_tools(
                provider=ai_config["ai_provider"],
                model=ai_config["ai_model"],
                messages=messages,
                api_key=ai_config["ai_api_key"],
                tools=tools_definition,  # 🔥 使用动态获取的工具定义
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
                    data = result["data"]

                    # 如果数据已经是字符串，直接使用
                    if isinstance(data, str):
                        data_str = data
                    # 如果数据是字典或列表，序列化为 JSON
                    elif isinstance(data, (dict, list)):
                        data_str = json.dumps(data, ensure_ascii=False, indent=2)
                    # 其他类型转换为字符串
                    else:
                        data_str = str(data)

                    # 🔥 关键修复：截断过大的工具结果（参考 Cline）
                    # GLM 模型有单次请求字符数限制（约 50,000 字符）
                    # 这里限制每个工具结果最多 10,000 字符
                    MAX_TOOL_RESULT_CHARS = 10_000
                    if len(data_str) > MAX_TOOL_RESULT_CHARS:
                        truncated_msg = f"\n\n[注意：结果已截断，原长度 {len(data_str)} 字符，显示前 {MAX_TOOL_RESULT_CHARS} 字符]"
                        data_str = data_str[:MAX_TOOL_RESULT_CHARS] + truncated_msg

                    formatted.append(f"<data>")
                    formatted.append(f"```\n{data_str}\n```")
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

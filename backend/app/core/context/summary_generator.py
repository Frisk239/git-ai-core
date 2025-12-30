"""
对话摘要生成器

参考 Cline 的 SummarizeTask 工具实现
"""

import logging
from typing import Dict, List, Any, Optional

from app.core.ai_manager import AIManager

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """
    对话摘要生成器

    使用 AI 生成对话历史摘要，参考 Cline 的 summarizeTask 模板
    """

    def __init__(self, ai_manager: Optional[AIManager] = None):
        self.ai_manager = ai_manager or AIManager()

    async def summarize_conversation(
        self,
        messages: List[Dict[str, Any]],
        ai_config: Dict[str, Any],
        max_length: int = 2000
    ) -> Optional[str]:
        """
        总结完整对话

        Args:
            messages: 消息列表
            ai_config: AI 配置
            max_length: 最大摘要长度

        Returns:
            摘要文本
        """
        try:
            # 构建总结提示词
            prompt = self._build_full_summary_prompt()

            # 格式化消息
            messages_text = self._format_messages(messages, max_chars=8000)

            # 调用 AI
            response = await self.ai_manager.chat(
                provider=ai_config.get("ai_provider", "deepseek"),
                model=ai_config.get("ai_model", "deepseek-chat"),
                messages=[{
                    "role": "user",
                    "content": f"{prompt}\n\n{messages_text}"
                }],
                api_key=ai_config.get("ai_api_key"),
                base_url=ai_config.get("ai_base_url"),
                temperature=0.3,
                max_tokens=max_length
            )

            if response and response.get("content"):
                return response["content"].strip()

        except Exception as e:
            logger.error(f"生成对话摘要失败: {e}")

        return None

    async def summarize_tool_result(
        self,
        tool_name: str,
        tool_result: Dict[str, Any],
        context: str,
        ai_config: Dict[str, Any]
    ) -> Optional[str]:
        """
        总结工具执行结果

        当工具结果过长时，使用 AI 提取关键信息

        Args:
            tool_name: 工具名称
            tool_result: 工具执行结果
            context: 上下文信息
            ai_config: AI 配置

        Returns:
            摘要文本
        """
        try:
            if not tool_result.get("success"):
                # 失败结果不需要摘要
                return f"工具 {tool_name} 执行失败: {tool_result.get('error', 'Unknown error')}"

            prompt = f"""请简要总结以下工具执行结果的关键信息：

工具名称: {tool_name}
任务上下文: {context}

工具结果:
{str(tool_result.get("data", ""))[:5000]}

请提取最重要的信息（例如：文件路径、关键数据、错误原因等），保持在 200 字以内。"""

            response = await self.ai_manager.chat(
                provider=ai_config.get("ai_provider", "deepseek"),
                model=ai_config.get("ai_model", "deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                api_key=ai_config.get("ai_api_key"),
                base_url=ai_config.get("ai_base_url"),
                temperature=0.3,
                max_tokens=500
            )

            if response and response.get("content"):
                return response["content"].strip()

        except Exception as e:
            logger.error(f"生成工具结果摘要失败: {e}")

        return None

    def _build_full_summary_prompt(self) -> str:
        """
        构建完整的对话摘要提示词

        参考 Cline 的 summarizeTask 模板（contextManagement.ts）
        """
        return """请详细总结之前的对话内容，包含以下部分：

## 1. 主要请求和意图
用户的核心需求是什么？是否有额外的需求或修改？

## 2. 技术概念
讨论了哪些技术概念、框架或工具？

## 3. 关键文件和代码
查看了哪些文件？修改了哪些文件？创建了哪些文件？
请列出文件路径和关键代码片段。

## 4. 问题解决
遇到了哪些问题？如何解决的？

## 5. 当前工作
在请求总结之前，正在做什么？
请详细描述最近的工作内容和进度。

## 6. 待办事项
有哪些未完成的任务？下一步需要做什么？

## 7. 重要文件
继续工作时需要访问哪些重要文件？

请确保摘要简洁但信息完整，便于 AI 能够无缝继续任务。"""

    def _format_messages(self, messages: List[Dict[str, Any]], max_chars: int = 8000) -> str:
        """将消息格式化为文本"""
        parts = []
        total_chars = 0

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # 截断过长的内容
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 0:
                    content = content[:remaining] + "...(已截断)"
                parts.append(f"{role.upper()}: {content}")
                break

            parts.append(f"{role.upper()}: {content}")
            total_chars += len(content)

        return "\n\n".join(parts)

    def extract_required_files(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        从对话历史中提取需要的文件

        参考 Cline 的 Required Files 解析逻辑
        """
        # TODO: 实现智能文件提取
        # 需要解析工具调用中的 file_path 参数
        return []

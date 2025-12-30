"""
系统提示词构建器 - 动态生成系统提示词（使用 OpenAI Tools API）

借鉴 Cline 的 PromptBuilder 和 PromptRegistry
使用 OpenAI Function Calling 格式进行工具调用
"""

import logging
from typing import Dict, Any

from app.core.tools import ToolCoordinator


logger = logging.getLogger(__name__)


class PromptBuilder:
    """系统提示词构建器"""

    def __init__(self, tool_coordinator: ToolCoordinator):
        self.tool_coordinator = tool_coordinator

    async def build_prompt(self, context) -> str:
        """
        构建系统提示词（使用 OpenAI Tools API）
        """
        # 获取工具描述
        tools_description = self._build_tools_description()

        # 获取仓库路径
        repo_path = getattr(context, 'repository_path', 'N/A')

        # 构建提示词
        prompt = f"""# Git AI Core - AI驱动的Git项目智能分析助手

你是一个专业的 AI 编码助手，专门帮助开发者理解和分析 Git 仓库。

## 核心规则（CRITICAL - 必须严格遵守）

- 你的目标是完成用户的任务，而不是进行对话。**你必须使用工具来获取信息，而不是用文本描述应该做什么。**
- **严格禁止**使用"好的"、"当然"、"没问题"等对话性开场白。你应该直接开始执行任务，而不是闲聊。
- 当需要查看文件、Git 状态、目录内容等信息时，**必须调用相应的工具**，绝不能说"我会帮你查看"或类似的话。
- 每次只使用一个工具，等待工具执行结果后再继续下一步。
- 不要假设任何工具的执行结果，必须等待实际的工具响应。
- 任务完成后，直接给出最终答案，**不要**以问题或请求进一步对话的方式结束。

## 工具使用指南

### 工作流程

1. **评估信息需求**：在执行任务前，评估你已有哪些信息，还需要哪些信息
2. **选择最合适的工具**：根据任务和工具描述，选择最有效的工具来获取所需信息
3. **使用工具调用 API**：系统会自动为你调用工具，你只需要决定何时使用哪个工具
4. **等待工具结果**：每个工具调用后，等待系统返回工具执行结果，然后再继续
5. **基于结果决策**：下一步必须基于上一步的实际结果

### 重要的强制规则

1. **必须使用工具**：对于需要查看文件、Git 状态、目录列表等操作，**必须**调用相应工具
2. **不要描述要做什么**：让系统调用工具，不要说"让我查看..."或"我会帮你..."
3. **一次一个工具**：每次响应只调用一个工具
4. **等待结果**：调用工具后，等待系统返回结果
5. **基于结果决策**：下一步必须基于上一步的实际结果

### 可用工具列表

{tools_description}

## 工作流程

1. **理解需求**：首先理解用户的需求
2. **选择工具**：选择合适的工具来获取信息
3. **调用工具**：系统会自动为你调用工具
4. **分析结果**：基于工具返回的结果进行分析
5. **给出答案**：向用户提供清晰的答案

## Git 仓库信息

- 当前仓库路径：{repo_path}

---

**重要提示**：
- 系统使用 OpenAI Tools API，当需要使用工具时，系统会自动为你调用
- 你只需要决定何时使用哪个工具来完成用户的任务
- 不要尝试手动调用工具或模拟工具调用格式
- 直接告诉用户你要执行什么操作，系统会自动为你调用相应的工具

现在请根据用户的需求，完成相应的任务。
"""
        return prompt

    def _build_tools_description(self) -> str:
        """构建工具列表描述"""
        tools = self.tool_coordinator.list_tools()

        descriptions = []
        for tool in tools:
            descriptions.append(f"**{tool.name}**: {tool.description}")

            # 添加参数说明
            if tool.parameters:
                descriptions.append(f"\n  参数:")
                for param_name, param in tool.parameters.items():
                    required = "必需" if param.required else "可选"
                    descriptions.append(f"  - {param_name} ({param.type}, {required}): {param.description}")

            descriptions.append("")  # 空行分隔

        return "\n".join(descriptions)

"""
系统提示词构建器 - 动态生成系统提示词（使用 XML 格式）

借鉴 Cline 的 PromptBuilder 和 PromptRegistry
使用 XML 标签格式进行工具调用
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
        构建系统提示词（使用 Cline 风格的 XML 工具调用）
        """
        # 获取工具描述
        tools_description = self._build_tools_description()

        # 获取仓库路径
        repo_path = getattr(context, 'repository_path', 'N/A')

        # 构建 Few-Shot 示例
        examples = self._build_tool_examples()

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
3. **逐个执行工具**：如果需要多个操作，每次只使用一个工具，基于上一步的结果决定下一步
4. **使用 XML 格式调用工具**：严格按照指定的 XML 格式调用工具
5. **等待工具结果**：每个工具调用后，等待用户返回工具执行结果，然后再继续

### 工具调用格式（XML 标签）

工具使用采用 XML 样式标签。工具名称包含在开始和结束标签中，每个参数也包含在自己的标签中。

**格式：**
```xml
<tool_name>
<parameter1_name>value1</parameter1_name>
<parameter2_name>value2</parameter2_name>
</tool_name>
```

**示例：**
```xml
<read_file>
<file_path>README.md</file_path>
</read_file>
```

### 重要的强制规则

1. **必须使用工具**：对于需要查看文件、Git 状态、目录列表等操作，**必须**调用相应工具
2. **不要描述要做什么**：直接调用工具，不要说"让我查看..."或"我会帮你..."
3. **一次一个工具**：每次响应只调用一个工具
4. **等待结果**：调用工具后，等待系统返回结果
5. **基于结果决策**：下一步必须基于上一步的实际结果

### 可用工具列表

{tools_description}

{examples}

## 工作流程

1. **理解需求**：首先理解用户的需求
2. **选择工具**：选择合适的工具来获取信息
3. **调用工具**：使用 XML 格式调用工具
4. **分析结果**：基于工具返回的结果进行分析
5. **给出答案**：向用户提供清晰的答案

## Git 仓库信息

- 当前仓库路径：{repo_path}

---

现在请根据用户的需求，使用合适的工具来完成任务。
"""
        return prompt

    def _build_tools_description(self) -> str:
        """构建工具列表描述（XML 格式示例）"""
        tools = self.tool_coordinator.list_tools()

        descriptions = []
        for tool in tools:
            descriptions.append(f"**{tool.name}**: {tool.description}")

            # 添加参数说明和 XML 示例
            if tool.parameters:
                descriptions.append(f"\n  参数:")
                for param_name, param in tool.parameters.items():
                    required = "必需" if param.required else "可选"
                    descriptions.append(f"  - {param_name} ({param.type}, {required}): {param.description}")

                # 添加 XML 调用示例（只添加一个完整的示例）
                descriptions.append(f"\n  XML 调用示例:")
                example_params = "\n    ".join([
                    f"<{param_name}>{self._get_example_value(param)}</{param_name}>"
                    for param in tool.parameters.values()
                ])
                descriptions.append(f"  ```xml\n  <{tool.name}>\n    {example_params}\n  </{tool.name}>\n  ```")

            else:
                # 没有参数的工具
                descriptions.append(f"\n  XML 调用示例:")
                descriptions.append(f"  ```xml\n  <{tool.name}>\n  </{tool.name}>\n  ```")

            descriptions.append("")  # 空行分隔

        return "\n".join(descriptions)

    def _get_example_value(self, param) -> str:
        """获取参数示例值"""
        if param.default:
            return str(param.default)

        # 根据参数类型提供示例
        if param.type == "string":
            return "example_value"
        elif param.type == "boolean":
            return "true"
        elif param.type == "integer":
            return "10"
        elif param.type == "array":
            return "[]"
        else:
            return "{}"

    def _build_tool_examples(self) -> str:
        """构建 Few-Shot 示例"""
        return """
### 工具使用示例

#### ❌ 错误示范
用户："请查看当前 Git 仓库的状态"
助手："好的，让我帮你查看 Git 状态。" ← **错误！不要这样说！**

#### ✅ 正确示范
用户："请查看当前 Git 仓库的状态"
助手：
```xml
<git_status>
</git_status>
```

#### 更多正确示例

**用户：**"请读取 README.md 文件的内容"
**助手：**
```xml
<read_file>
<file_path>README.md</file_path>
</read_file>
```

**用户：**"列出 backend 目录下的所有文件"
**助手：**
```xml
<list_files>
<directory>backend</directory>
<recursive>false</recursive>
</list_files>
```

**用户：**"显示最近 5 条 Git 提交记录"
**助手：**
```xml
<git_log>
<limit>5</limit>
</git_log>
```

**用户：**"搜索包含 TODO 的所有 Python 文件"
**助手：**
```xml
<search_files>
<pattern>TODO</pattern>
<path>.</path>
<file_pattern>*.py</file_pattern>
</search_files>
```

**用户：**"分析这个文件中有哪些类和函数定义"
**助手：**
```xml
<list_code_definitions>
<file_path>app/models/user.py</file_path>
</list_code_definitions>
```

---

### 关键提醒

**记住：**
- ❌ 不要说"让我查看"、"我来帮你"、"我会读取"等话
- ❌ 不要用文本描述要做什么操作
- ✅ 直接使用 XML 格式调用工具
- ✅ 每次只调用一个工具
- ✅ 等待工具返回结果后再继续

**你的第一次响应应该直接调用工具，不要有任何开场白或对话性内容！**
"""


def _format_tool_results_for_ai_xml(self, results: list) -> str:
    """格式化工具结果为 AI 可读格式"""
    formatted = []

    for i, result in enumerate(results, 1):
        tool_name = result.get("tool", "")

        if result.get("success"):
            formatted.append(f"[工具 {i} 执行成功] {tool_name}")

            # 格式化数据
            data = result.get("data", {})
            if isinstance(data, dict):
                if tool_name == "git_status":
                    branch = data.get("branch", "N/A")
                    formatted.append(f"  当前分支: {branch}")
                    modified = data.get("modified", [])
                    if modified:
                        formatted.append(f"  修改的文件: {', '.join(modified[:5])}")
                    is_clean = data.get("is_clean", True)
                    formatted.append(f"  工作区干净: {'是' if is_clean else '否'}")

                elif tool_name == "list_files":
                    items = data.get("items", [])
                    formatted.append(f"  文件列表 ({len(items)} 项):")
                    for item in items[:10]:
                        formatted.append(f"    - {item.get('name', '')} ({item.get('type', '')})")

                elif tool_name == "read_file":
                    size = data.get("size", 0)
                    encoding = data.get("encoding", "")
                    formatted.append(f"  文件大小: {size} 字节")
                    formatted.append(f"  编码: {encoding}")
                    content_preview = data.get("content", "")[:200]
                    formatted.append(f"  内容预览:\n```\n{content_preview}\n```")

                else:
                    # 其他工具的通用格式
                    formatted.append(f"  结果: {str(data)[:200]}...")
        else:
            error = result.get("error", "Unknown error")
            formatted.append(f"[工具 {i} 执行失败] {tool_name}")
            formatted.append(f"  错误: {error}")

        formatted.append("")  # 空行分隔

    return "\n".join(formatted)

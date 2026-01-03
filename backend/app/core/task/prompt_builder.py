"""
系统提示词构建器 - 动态生成系统提示词（使用 OpenAI Tools API）

借鉴 Cline 的 PromptBuilder 和 PromptRegistry
使用 OpenAI Function Calling 格式进行工具调用
"""

import logging
import json
from typing import Dict, Any

from app.core.tools import ToolCoordinator
from app.core.mcp_server import MCPServerManager


logger = logging.getLogger(__name__)


class PromptBuilder:
    """系统提示词构建器"""

    def __init__(self, tool_coordinator: ToolCoordinator):
        self.tool_coordinator = tool_coordinator

    async def build_prompt(self, context) -> str:
        """
        构建系统提示词（使用 OpenAI Tools API）
        """
        # 获取工具描述（排除 MCP 工具，因为会在单独的章节中说明）
        tools_description = self._build_tools_description(exclude_mcp=True)

        # 获取 MCP 服务器信息
        mcp_section = await self._build_mcp_section()

        # 获取仓库路径
        repo_path = getattr(context, 'repository_path', 'N/A')

        # 构建基础提示词
        prompt = f"""# Git AI Core - AI驱动的Git项目智能分析助手

你是一个专业的 AI 编码助手，专门帮助开发者理解和分析 Git 仓库。

## 核心规则（CRITICAL - 必须严格遵守）

- 你的目标是完成用户的任务，而不是进行对话。**你必须使用工具来获取信息，而不是用文本描述应该做什么。**
- **严格禁止**使用"好的"、"当然"、"没问题"等对话性开场白。你应该直接开始执行任务，而不是闲聊。
- 当需要查看文件、Git 状态、目录内容等信息时，**必须调用相应的工具**，绝不能说"我会帮你查看"或类似的话。
- 每次只使用一个工具，等待工具执行结果后再继续下一步。
- 不要假设任何工具的执行结果，必须等待实际的工具响应。
- **任务完成后，必须使用 attempt_completion 工具来标记任务完成并呈现最终结果**。不要以问题或请求进一步对话的方式结束。

**用户指定的要求优先级最高**:
- 如果用户明确指定了文件名、路径或操作方式，**必须严格按照用户要求执行**
- 例如：如果用户要求"创建文件 report.md 放到 backend 目录下"，你必须创建 `backend/report.md`，而不是 `backend/docs/xxx.md` 或其他名称
- **绝对不能**自作主张改变用户指定的文件名或路径
- 如果用户没有明确指定，才由你自行决定最合适的方案

**关于 attempt_completion 的关键规则**:
- 只有在**完成用户要求的所有任务**后才能调用此工具
- 例如：如果用户要求"创建一个文件"，你必须先调用 `write_to_file` 创建文件，等待成功响应后，才能调用 `attempt_completion`
- **绝对不能**只读取信息或口头描述就调用 `attempt_completion`，必须实际执行所有必要的操作
- **在使用 attempt_completion 之前，必须检查以下清单**：
  1. ✅ 用户要求的所有文件是否都已**通过工具创建**？（不是口头描述，而是实际调用 write_to_file）
  2. ✅ 用户要求的所有修改是否都已完成？
  3. ✅ 用户要求的所有操作（如分析、生成报告等）是否都已执行？
  4. ✅ 是否已收到所有工具执行的成功响应？
  - **如果任何一项是否定的，则绝对不能调用 attempt_completion！**
- **特别注意**：如果用户要求"分析并创建 report.md"，你必须：
  1. 使用 `read_file` 等工具分析文件
  2. 调用 `write_to_file` 创建 `report.md` 文件
  3. 等待文件创建成功的响应
  4. 然后才能调用 `attempt_completion`
  - **只口头分析而不创建文件就调用 attempt_completion 是错误的！**

## 文件路径规范（CRITICAL - 必须严格遵守）

所有文件操作工具（write_to_file、read_file、list_files、replace_in_file）都使用**相对于仓库根目录**的路径。

### 正确的路径格式示例

**正确**:
- `backend/config.py` - 创建/读取 backend 目录下的 config.py
- `README.md` - 在仓库根目录创建/读取 README.md
- `docs/guide.md` - 创建/读取 docs 目录下的 guide.md
- `src/api/routes.py` - 创建/读取 src/api 目录下的 routes.py

**错误**:
- `/home/user/project/backend/config.py` - 绝对路径
- `./backend/config.py` - 包含 `./` 前缀
- `../other/file.py` - 包含 `../` 前缀
- `C:\\Users\\...` - Windows 绝对路径

### 重要规则

1. **始终使用正斜杠** `/` 作为路径分隔符（即使在 Windows 上）
2. **路径相对于仓库根目录**，不要使用 `./` 或 `../` 等前缀
3. **不要使用绝对路径**
4. **目录名直接写**，如 `backend` 而不是 `./backend`

## 工作流程

### 标准任务执行流程

1. **理解需求**：首先**仔细**理解用户的需求，特别注意用户明确指定的细节（如文件名、路径、具体操作等）
2. **评估信息需求**：评估你已有哪些信息，还需要哪些信息
3. **选择工具**：根据任务和工具描述，选择最有效的工具来获取所需信息
4. **执行工具**：系统会自动为你调用工具
5. **分析结果**：基于工具返回的结果进行分析
6. **继续或完成**：
   - 如果任务未完成，继续使用工具获取更多信息或执行必要操作
   - **关键**: 如果用户要求创建文件、修改代码等，你必须**严格按照用户指定的文件名和路径**执行，不能擅自更改
   - 如果任务已完成，**必须使用 attempt_completion 工具**来呈现最终结果

### 重要的强制规则

1. **必须使用工具**：对于需要查看文件、Git 状态、目录列表等操作，**必须**调用相应工具
2. **不要描述要做什么**：让系统调用工具，不要说"让我查看..."或"我会帮你..."
3. **一次一个工具**：每次响应只调用一个工具
4. **等待结果**：调用工具后，等待系统返回结果
5. **基于结果决策**：下一步必须基于上一步的实际结果
6. **完成任务的强制检查**：在调用 `attempt_completion` 之前，必须确认：
   - 用户要求创建的所有文件都已创建成功
   - 用户要求的所有操作都已执行完成
   - 所有工具调用都返回了成功结果
   - **如果用户要求创建文件但还没有创建，绝对不能调用 attempt_completion！**
6. **完成必须调用 attempt_completion**：只有调用 attempt_completion 工具才算真正完成任务
7. **必须完成所有操作**：如果用户要求创建文件、修改代码等，必须实际执行这些操作。**只读取信息或口头总结不等于完成任务**
8. **专注单一任务**：完成用户明确要求的任务即可，不要创建额外的文件或做多余的事情。例如，如果用户要求创建 `backend/report.md`，就只创建这一个文件，不要创建其他版本或副本

### 可用工具列表

{tools_description}

## 工作流程

1. **理解需求**：首先理解用户的需求
2. **选择工具**：选择合适的工具来获取信息
3. **调用工具**：系统会自动为你调用工具
4. **分析结果**：基于工具返回的结果进行分析
5. **给出答案**：向用户提供清晰的答案

{mcp_section}

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

    def _build_tools_description(self, exclude_mcp: bool = False) -> str:
        """
        构建工具列表描述

        Args:
            exclude_mcp: 是否排除 MCP 工具（因为会在单独章节中说明）
        """
        tools = self.tool_coordinator.list_tools()

        descriptions = []
        for tool in tools:
            # 跳过 MCP 工具（会在单独章节说明）
            if exclude_mcp and tool.category == "mcp":
                continue

            descriptions.append(f"**{tool.name}**: {tool.description}")

            # 添加参数说明
            if tool.parameters:
                descriptions.append(f"\n  参数:")
                for param_name, param in tool.parameters.items():
                    required = "必需" if param.required else "可选"
                    descriptions.append(f"  - {param_name} ({param.type}, {required}): {param.description}")

            descriptions.append("")  # 空行分隔

        return "\n".join(descriptions)

    async def _build_mcp_section(self) -> str:
        """
        构建 MCP 服务器信息章节

        参考 Cline 的 components/mcp.ts 实现
        """
        try:
            # 获取 MCP 服务器管理器
            from app.core.tools.handlers.mcp_handler import get_mcp_server_manager
            mcp_manager = get_mcp_server_manager()

            # 获取所有服务器配置
            servers_config = mcp_manager.list_servers()

            # 如果没有配置 MCP 服务器，返回空字符串
            if not servers_config:
                return ""

            # 构建 MCP 章节
            mcp_servers_info = []

            for server_name, config in servers_config.items():
                # 跳过禁用的服务器
                if not config.get("enabled", True):
                    continue

                # 获取服务器状态
                status_info = await mcp_manager.get_server_status(server_name)

                # 只显示可用的服务器
                if status_info.get("status") == "not_configured":
                    continue

                server_desc = config.get("description", "")
                transport_type = config.get("transportType", "stdio")

                server_section = f"### {server_name}\n"
                if server_desc:
                    server_section += f"**描述**: {server_desc}\n\n"
                server_section += f"**传输类型**: {transport_type}\n\n"
                server_section += f"**状态**: {status_info.get('status', 'unknown')}\n\n"

                # 如果服务器正在运行，获取工具和资源列表
                if status_info.get("connected"):
                    try:
                        # 获取工具列表
                        tools = await mcp_manager.list_tools(server_name)
                        if tools:
                            server_section += "**可用工具**:\n\n"
                            for tool in tools:
                                tool_name = tool["name"]
                                tool_desc = tool.get("description", tool_name)
                                server_section += f"- `{tool_name}`: {tool_desc}\n"

                                # 添加参数 schema
                                input_schema = tool.get("input_schema", {})
                                if input_schema and "properties" in input_schema:
                                    server_section += f"  参数: {json.dumps(input_schema, ensure_ascii=False)}\n"
                                server_section += "\n"

                        # 获取资源列表
                        resources = await mcp_manager.list_resources(server_name)
                        if resources:
                            server_section += "**可用资源**:\n\n"
                            for resource in resources:
                                uri = resource["uri"]
                                res_name = resource.get("name", "")
                                res_desc = resource.get("description", "")
                                server_section += f"- `{uri}`"
                                if res_name:
                                    server_section += f" ({res_name})"
                                if res_desc:
                                    server_section += f": {res_desc}"
                                server_section += "\n"
                            server_section += "\n"

                    except Exception as e:
                        logger.warning(f"获取 {server_name} 的工具/资源列表失败: {e}")

                mcp_servers_info.append(server_section)

            # 如果没有可用的 MCP 服务器
            if not mcp_servers_info:
                return ""

            # 构建 MCP 章节
            mcp_section = """## MCP 服务器

Model Context Protocol (MCP) 服务器可以扩展你的能力，提供额外的工具和资源。

### MCP 工具使用方法

当需要使用 MCP 服务器的工具时，使用以下工具：

1. **use_mcp_tool** - 调用 MCP 服务器的工具
   - `server_name`: MCP 服务器名称
   - `tool_name`: 要调用的工具名称
   - `arguments`: 工具参数（JSON 字符串）

2. **access_mcp_resource** - 访问 MCP 服务器的资源
   - `server_name`: MCP 服务器名称
   - `uri`: 资源 URI

3. **list_mcp_servers** - 列出所有可用的 MCP 服务器及其工具/资源

### 已连接的 MCP 服务器

"""

            mcp_section += "\n".join(mcp_servers_info)

            return mcp_section

        except Exception as e:
            logger.error(f"构建 MCP 章节失败: {e}", exc_info=True)
            return ""


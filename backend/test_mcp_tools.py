"""
测试 MCP 工具是否正确加载
"""

import asyncio
import sys
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.tools import get_tool_coordinator
from app.core.tools.handlers.mcp_handler import get_mcp_server_manager


async def main():
    print("=" * 80)
    print("测试 MCP 工具集成")
    print("=" * 80)

    # 1. 测试工具协调器
    print("\n1. 测试工具协调器...")
    tc = get_tool_coordinator()
    print(f"   ✓ 工具总数: {len(tc.handlers)}")

    # 2. 列出所有工具
    print("\n2. 所有已注册工具:")
    for tool in tc.list_tools():
        category_tag = f"[{tool.category}]"
        print(f"   - {tool.name:30s} {category_tag:15s} {tool.description[:50]}")

    # 3. 列出 MCP 工具
    print("\n3. MCP 工具:")
    mcp_tools = [t for t in tc.list_tools() if t.category == "mcp"]
    for tool in mcp_tools:
        print(f"   - {tool.name}: {tool.description}")

        # 显示参数
        if tool.parameters:
            print(f"     参数:")
            for param_name, param in tool.parameters.items():
                required = "必需" if param.required else "可选"
                print(f"       - {param_name} ({param.type}, {required})")

    # 4. 测试 MCP 服务器管理器
    print("\n4. 测试 MCP 服务器管理器...")
    mcp_manager = get_mcp_server_manager()
    servers = mcp_manager.list_servers()
    print(f"   ✓ 配置的 MCP 服务器数量: {len(servers)}")

    if servers:
        print("\n5. 已配置的 MCP 服务器:")
        for server_name, config in servers.items():
            enabled = "启用" if config.get("enabled", True) else "禁用"
            transport = config.get("transportType", "stdio")
            desc = config.get("description", "无描述")
            print(f"   - {server_name}:")
            print(f"     描述: {desc}")
            print(f"     状态: {enabled}")
            print(f"     传输: {transport}")
    else:
        print("   ℹ  没有配置 MCP 服务器")

    print("\n" + "=" * 80)
    print("✓ MCP 工具集成测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

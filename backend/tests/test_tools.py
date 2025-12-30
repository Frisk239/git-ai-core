"""
工具系统测试
"""

import pytest
import asyncio
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.tools import (
    ToolCoordinator,
    ToolCall,
    ToolContext,
    get_tool_coordinator
)


class TestToolCoordinator:
    """测试工具协调器"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = ToolCoordinator()
        self.coordinator.initialize_default_tools()

    def test_tools_registered(self):
        """测试工具是否正确注册"""
        tools = self.coordinator.list_tools()

        # 检查是否注册了预期的工具
        tool_names = [tool.name for tool in tools]

        assert "read_file" in tool_names
        assert "list_files" in tool_names
        assert "git_diff" in tool_names
        assert "git_log" in tool_names
        assert "git_status" in tool_names
        assert "git_branch" in tool_names

        print(f"[OK] 已注册 {len(tools)} 个工具:")
        for tool in tools:
            print(f"  - {tool.name} ({tool.category}): {tool.description}")

    def test_get_tools_description(self):
        """测试工具描述生成"""
        description = self.coordinator.get_tools_description()

        assert "read_file" in description
        assert "git_diff" in description

        print("\n工具描述:\n")
        print(description)


class TestFileTools:
    """测试文件工具"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = get_tool_coordinator()

        # 使用当前项目作为测试仓库
        self.repo_path = os.path.join(os.path.dirname(__file__), '..', '..')

    @pytest.mark.asyncio
    async def test_read_file_tool(self):
        """测试读取文件工具"""
        # 测试读取 README.md
        tool_call = ToolCall(
            id="test-1",
            name="read_file",
            parameters={
                "file_path": "README.md"
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data is not None
        assert "content" in result.data
        assert "file_path" in result.data

        print(f"\n[OK] 成功读取文件: {result.data['file_path']}")
        print(f"  文件大小: {result.data['size']} 字节")
        print(f"  使用编码: {result.data['encoding']}")
        print(f"  内容预览: {result.data['content'][:100]}...")

    @pytest.mark.asyncio
    async def test_list_files_tool(self):
        """测试列出文件工具"""
        tool_call = ToolCall(
            id="test-2",
            name="list_files",
            parameters={
                "directory": "backend/app",
                "recursive": False
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data is not None
        assert "items" in result.data

        print(f"\n[OK] 成功列出目录: {result.data['directory']}")
        print(f"  总数: {result.data['total_count']} 项")
        print(f"  前 5 项:")
        for item in result.data['items'][:5]:
            print(f"    - {item['name']} ({item['type']})")


class TestGitTools:
    """测试 Git 工具"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = get_tool_coordinator()
        self.repo_path = os.path.join(os.path.dirname(__file__), '..', '..')

    @pytest.mark.asyncio
    async def test_git_status_tool(self):
        """测试 Git status 工具"""
        tool_call = ToolCall(
            id="test-3",
            name="git_status",
            parameters={}
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data is not None

        print(f"\n[OK] 成功获取 Git 状态")
        print(f"  仓库路径: {result.data['repo_path']}")

    @pytest.mark.asyncio
    async def test_git_log_tool(self):
        """测试 Git log 工具"""
        tool_call = ToolCall(
            id="test-4",
            name="git_log",
            parameters={
                "limit": 5
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data is not None
        assert "commits" in result.data

        print(f"\n[OK] 成功获取提交历史")
        print(f"  提交数: {result.data['total_count']}")
        if result.data['commits']:
            print(f"  最新提交: {result.data['commits'][0].get('message', 'N/A')[:50]}...")

    @pytest.mark.asyncio
    async def test_git_branch_tool(self):
        """测试 Git branch 工具"""
        tool_call = ToolCall(
            id="test-5",
            name="git_branch",
            parameters={
                "action": "current"
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data is not None

        print(f"\n[OK] 成功获取分支信息")
        print(f"  当前分支: {result.data.get('current_branch', 'N/A')}")


class TestToolCoordinatorErrors:
    """测试工具协调器错误处理"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = get_tool_coordinator()
        self.repo_path = os.path.join(os.path.dirname(__file__), '..', '..')

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """测试未知工具"""
        tool_call = ToolCall(
            id="test-error-1",
            name="unknown_tool",
            parameters={}
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is False
        assert "error" in result.to_dict()

        print(f"\n[OK] 正确处理未知工具错误: {result.error}")

    @pytest.mark.asyncio
    async def test_missing_required_parameter(self):
        """测试缺少必需参数"""
        tool_call = ToolCall(
            id="test-error-2",
            name="read_file",
            parameters={}  # 缺少 file_path
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is False
        assert "参数验证失败" in result.error

        print(f"\n[OK] 正确处理参数验证错误: {result.error}")


def run_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始测试工具系统")
    print("="*60 + "\n")

    # 运行测试
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_tests()

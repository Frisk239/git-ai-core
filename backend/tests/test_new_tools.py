"""
新工具测试 - search_files, write_to_file, replace_in_file, list_code_definitions
"""

import pytest
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.tools import (
    ToolCoordinator,
    ToolCall,
    ToolContext,
    get_tool_coordinator
)


class TestSearchFilesTool:
    """测试文件搜索工具"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = get_tool_coordinator()
        self.repo_path = os.path.join(os.path.dirname(__file__), '..', '..')

    @pytest.mark.asyncio
    async def test_search_files_basic(self):
        """测试基本文件搜索"""
        tool_call = ToolCall(
            id="test-search-1",
            name="search_files",
            parameters={
                "pattern": "class",
                "path": "backend/app/core",
                "file_pattern": "*.py"
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data is not None
        assert "results" in result.data

        print(f"\n[OK] 搜索完成: {result.data['pattern']}")
        print(f"  路径: {result.data['path']}")
        print(f"  匹配数: {result.data['total_matches']}")
        if result.data['results']:
            print(f"  前 3 个结果:")
            for match in result.data['results'][:3]:
                print(f"    - {match['file']}:{match['line']} - {match['match'][:50]}")

    @pytest.mark.asyncio
    async def test_search_files_regex(self):
        """测试正则表达式搜索"""
        tool_call = ToolCall(
            id="test-search-2",
            name="search_files",
            parameters={
                "pattern": r"def\s+\w+.*:",
                "path": "backend/app/core/tools",
                "file_pattern": "*.py"
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True

        print(f"\n[OK] 正则搜索完成")
        print(f"  找到 {result.data['total_matches']} 个函数定义")


class TestWriteToFileTool:
    """测试文件写入工具"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = get_tool_coordinator()
        self.repo_path = tempfile.mkdtemp()
        self.test_files = []

    def teardown_method(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)

    @pytest.mark.asyncio
    async def test_write_new_file(self):
        """测试写入新文件"""
        test_content = """# Test File
This is a test file created by write_to_file tool.
"""

        tool_call = ToolCall(
            id="test-write-1",
            name="write_to_file",
            parameters={
                "file_path": "test/new_file.md",
                "content": test_content
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data["action"] == "created"

        print(f"\n[OK] 创建文件成功")
        print(f"  文件: {result.data['file_path']}")
        print(f"  大小: {result.data['size']} 字节")

        # 验证文件确实创建
        full_path = os.path.join(self.repo_path, "test/new_file.md")
        assert os.path.exists(full_path)

    @pytest.mark.asyncio
    async def test_update_existing_file(self):
        """测试更新现有文件"""
        # 先创建一个文件
        os.makedirs(os.path.join(self.repo_path, "test"), exist_ok=True)
        test_file = os.path.join(self.repo_path, "test/existing.txt")
        with open(test_file, 'w') as f:
            f.write("Original content")

        # 更新文件
        tool_call = ToolCall(
            id="test-write-2",
            name="write_to_file",
            parameters={
                "file_path": "test/existing.txt",
                "content": "Updated content"
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data["action"] == "updated"

        print(f"\n[OK] 更新文件成功")
        print(f"  旧大小: {result.data['old_size']} 字节")
        print(f"  新大小: {result.data['new_size']} 字节")


class TestReplaceInFileTool:
    """测试文件内容替换工具"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = get_tool_coordinator()
        self.repo_path = tempfile.mkdtemp()

        # 创建测试文件
        self.test_file = os.path.join(self.repo_path, "test.txt")
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write("""Hello World
This is a test file.
Hello Python
Hello AI
""")

    def teardown_method(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)

    @pytest.mark.asyncio
    async def test_replace_in_file(self):
        """测试文件内容替换"""
        tool_call = ToolCall(
            id="test-replace-1",
            name="replace_in_file",
            parameters={
                "file_path": "test.txt",
                "search": "Hello World",
                "replace": "Hello Git AI Core"
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data["replacements"] == 1

        print(f"\n[OK] 替换成功")
        print(f"  替换次数: {result.data['replacements']}")
        print(f"  大小变化: {result.data['size_change']} 字节")

        # 验证替换结果
        with open(self.test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "Hello Git AI Core" in content
            assert "Hello World" not in content


class TestListCodeDefinitionsTool:
    """测试代码定义列出工具"""

    def setup_method(self):
        """测试前准备"""
        self.coordinator = get_tool_coordinator()
        self.repo_path = os.path.join(os.path.dirname(__file__), '..', '..')

    @pytest.mark.asyncio
    async def test_list_python_definitions(self):
        """测试列出 Python 代码定义"""
        tool_call = ToolCall(
            id="test-code-1",
            name="list_code_definitions",
            parameters={
                "file_path": "backend/app/core/tools/coordinator.py"
            }
        )

        context = ToolContext(
            repository_path=self.repo_path
        )

        result = await self.coordinator.execute(tool_call, context)

        assert result.success is True
        assert result.data is not None
        assert "definitions" in result.data

        print(f"\n[OK] 代码定义分析完成")
        print(f"  文件: {result.data['file_path']}")
        print(f"  语言: {result.data['language']}")
        print(f"  定义总数: {result.data['total_count']}")

        if result.data['definitions']:
            print(f"  前 5 个定义:")
            for defn in result.data['definitions'][:5]:
                decorators = f" ({', '.join(defn.get('decorators', []))})" if defn.get('decorators') else ""
                print(f"    - {defn['type']}: {defn['name']} at line {defn['line']}{decorators}")


class TestAllToolsRegistered:
    """测试所有工具是否正确注册"""

    def test_all_tools_count(self):
        """测试工具数量"""
        coordinator = ToolCoordinator()
        coordinator.initialize_default_tools()

        tools = coordinator.list_tools()
        tool_names = [tool.name for tool in tools]

        print(f"\n[OK] 所有已注册工具 ({len(tools)} 个):")

        # 按类别分组显示
        by_category = {}
        for tool in tools:
            if tool.category not in by_category:
                by_category[tool.category] = []
            by_category[tool.category].append(tool)

        for category, category_tools in sorted(by_category.items()):
            print(f"\n  {category.upper()} ({len(category_tools)} 个):")
            for tool in category_tools:
                print(f"    - {tool.name}: {tool.description}")

        # 验证关键工具存在
        assert "read_file" in tool_names
        assert "write_to_file" in tool_names
        assert "search_files" in tool_names
        assert "list_code_definitions" in tool_names
        assert "replace_in_file" in tool_names


def run_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始测试新工具")
    print("="*60 + "\n")

    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_tests()

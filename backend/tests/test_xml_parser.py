"""
快速测试 XML 工具调用解析器
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.task.parser_xml import XMLToolCallParser


def test_xml_parser():
    """测试 XML 解析器"""
    parser = XMLToolCallParser()

    # 测试用例
    test_cases = [
        {
            "name": "单个工具调用",
            "response": """让我查看 Git 状态。

<git_status>
</git_status>
"""
        },
        {
            "name": "带参数的工具调用",
            "response": """我来读取 README 文件。

<read_file>
<file_path>README.md</file_path>
</read_file>
"""
        },
        {
            "name": "多个参数的工具调用",
            "response": """列出目录文件。

<list_files>
<directory>backend</directory>
<recursive>false</recursive>
</list_files>
"""
        },
        {
            "name": "混合文本和工具调用",
            "response": """用户想要查看提交历史，我来帮他查询。

<git_log>
<limit>5</limit>
</git_log>
"""
        },
        {
            "name": "搜索文件",
            "response": """搜索包含 TODO 的文件。

<search_files>
<pattern>TODO</pattern>
<path>.</path>
<file_pattern>*.py</file_pattern>
</search_files>
"""
        }
    ]

    print("\n" + "="*60)
    print("测试 XML 工具调用解析器")
    print("="*60)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n### 测试 {i}: {test_case['name']} ###")
        print(f"响应:\n{test_case['response'][:100]}...")

        tool_calls = parser.extract_tool_calls(test_case['response'])

        print(f"\n提取结果: {len(tool_calls)} 个工具调用")
        for j, call in enumerate(tool_calls, 1):
            print(f"  工具 {j}:")
            print(f"    名称: {call.get('name')}")
            print(f"    参数: {call.get('parameters')}")


if __name__ == "__main__":
    test_xml_parser()

"""
测试 replace_in_file 工具的 SEARCH/REPLACE 块功能
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.tools.handlers.write_handler import ReplaceInFileToolHandler
from app.core.tools.base import ToolContext


async def test_replace_in_file():
    """测试 replace_in_file 工具"""

    handler = ReplaceInFileToolHandler()

    # 创建测试文件
    test_file_path = "test_sample.py"
    test_repo_path = os.path.dirname(__file__)

    # 原始内容
    original_content = '''def hello_world():
    print("Hello, World!")
    print("Welcome to Python")

def goodbye():
    print("Goodbye!")
'''

    # 写入测试文件
    full_path = os.path.join(test_repo_path, test_file_path)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(original_content)

    print("=" * 60)
    print("测试 replace_in_file 工具")
    print("=" * 60)
    print(f"\n原始文件内容:\n{original_content}")

    # 测试 1: 单个 SEARCH/REPLACE 块
    print("\n" + "=" * 60)
    print("测试 1: 单个 SEARCH/REPLACE 块")
    print("=" * 60)

    diff1 = '''------- SEARCH
def hello_world():
    print("Hello, World!")
=======
def hello_world():
    print("Hello, Python!")
+++++++ REPLACE'''

    context = ToolContext(
        repository_path=test_repo_path,
        conversation_id="test"
    )

    try:
        result = await handler.execute({
            "file_path": test_file_path,
            "diff": diff1
        }, context)

        print(f"\n[OK] 替换成功!")
        print(f"  - 处理块数: {result['stats']['blocks_processed']}")
        print(f"  - 添加行数: {result['stats']['lines_added']}")
        print(f"  - 删除行数: {result['stats']['lines_removed']}")
        print(f"  - 字节变化: {result['stats']['bytes_added'] - result['stats']['bytes_removed']}")

        # 读取新内容
        with open(full_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
        print(f"\n新文件内容:\n{new_content}")

    except Exception as e:
        print(f"\n[ERROR] 失败: {e}")

    # 测试 2: 多个 SEARCH/REPLACE 块
    print("\n" + "=" * 60)
    print("测试 2: 多个 SEARCH/REPLACE 块")
    print("=" * 60)

    # 重置文件
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(original_content)

    diff2 = '''------- SEARCH
def hello_world():
    print("Hello, World!")
=======
def hello_world():
    print("Hello, Python!")
+++++++ REPLACE

------- SEARCH
def goodbye():
    print("Goodbye!")
=======
def farewell():
    print("See you soon!")
+++++++ REPLACE'''

    try:
        result = await handler.execute({
            "file_path": test_file_path,
            "diff": diff2
        }, context)

        print(f"\n✅ 替换成功!")
        print(f"  - 处理块数: {result['stats']['blocks_processed']}")
        print(f"  - 添加行数: {result['stats']['lines_added']}")
        print(f"  - 删除行数: {result['stats']['lines_removed']}")

        with open(full_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
        print(f"\n新文件内容:\n{new_content}")

    except Exception as e:
        print(f"\n[ERROR] 失败: {e}")

    # 测试 3: 行修剪匹配（忽略空格差异）
    print("\n" + "=" * 60)
    print("测试 3: 行修剪匹配（智能匹配）")
    print("=" * 60)

    # 重置文件
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(original_content)

    # 注意：这里的搜索内容有多余的空格，但应该能匹配
    diff3 = '''------- SEARCH
    print("Hello, World!")
=======
    print("Hello, AI!")
+++++++ REPLACE'''

    try:
        result = await handler.execute({
            "file_path": test_file_path,
            "diff": diff3
        }, context)

        print(f"\n[OK] 智能匹配成功!")
        print(f"  - 添加行数: {result['stats']['lines_added']}")
        print(f"  - 删除行数: {result['stats']['lines_removed']}")

        with open(full_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
        print(f"\n新文件内容:\n{new_content}")

    except Exception as e:
        print(f"\n[ERROR] 失败: {e}")

    # 清理测试文件
    try:
        os.remove(full_path)
        print(f"\n[CLEAN] 清理测试文件: {test_file_path}")
    except:
        pass

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_replace_in_file())

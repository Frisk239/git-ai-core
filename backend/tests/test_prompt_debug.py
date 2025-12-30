"""
调试脚本 - 查看实际生成的系统提示词
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.task import PromptBuilder
from app.core.tools import get_tool_coordinator
from app.core.tools.base import ToolContext


async def main():
    """查看系统提示词"""
    coordinator = get_tool_coordinator()
    builder = PromptBuilder(coordinator)

    # 创建测试上下文
    context = ToolContext(
        repository_path="C:\\test\\repo",
        conversation_history=[],
        metadata={}
    )

    # 生成提示词
    prompt = await builder.build_prompt(context)

    # 输出到文件
    output_file = os.path.join(os.path.dirname(__file__), "debug_prompt.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    print(f"系统提示词已保存到: {output_file}")
    print(f"提示词总长度: {len(prompt)} 字符")
    print("\n前 500 字符预览:")
    print("=" * 60)
    print(prompt[:500])
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

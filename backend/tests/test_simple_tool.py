"""
简单测试 - 直接测试 AI 是否能理解 XML 格式的工具调用
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.ai_manager import AIManager


async def test_direct_ai():
    """直接测试 AI 对 XML 格式的理解"""

    # 简单的系统提示词
    system_prompt = """你是一个 AI 助手。当用户让你查看文件时，必须使用以下 XML 格式调用工具：

<read_file>
<file_path>文件路径</file_path>
</read_file>

例如：
用户：请查看 README.md
助手：
<read_file>
<file_path>README.md</file_path>
</read_file>

现在请严格按照这个格式回答用户的问题。"""

    # AI 配置
    ai_config = {
        "ai_provider": "deepseek",
        "ai_model": "deepseek-chat",
        "ai_api_key": "sk-b220ecfa259f47fbb1c2f873327933c8",
        "ai_base_url": "https://api.deepseek.com/v1",
        "temperature": 0.0,  # 降低温度使其更确定
        "max_tokens": 500
    }

    ai_manager = AIManager()

    # 测试查询
    user_query = "请查看 README.md 文件的内容"

    print("=" * 60)
    print("测试 DeepSeek 对 XML 工具格式的理解")
    print("=" * 60)
    print(f"\n用户查询: {user_query}")
    print(f"\n系统提示词:\n{system_prompt}")
    print("\n" + "=" * 60)
    print("AI 响应:")
    print("=" * 60 + "\n")

    try:
        response = await ai_manager.chat(
            provider=ai_config["ai_provider"],
            model=ai_config["ai_model"],
            messages=[{"role": "user", "content": user_query}],
            api_key=ai_config["ai_api_key"],
            base_url=ai_config["ai_base_url"],
            temperature=ai_config["temperature"],
            max_tokens=ai_config["max_tokens"],
            system_prompt=system_prompt
        )

        if response:
            content = response.get("content", "")
            print(content)
            print("\n" + "=" * 60)

            # 检查是否包含 XML 标签
            if "<read_file>" in content:
                print("✅ AI 正确使用了 XML 格式!")
            else:
                print("❌ AI 没有使用 XML 格式")
                print("\n可能的原因:")
                print("1. DeepSeek 模型可能不支持 XML 格式的工具调用")
                print("2. 需要更强的提示词工程")
                print("3. 应考虑使用 OpenAI 的 function calling 或其他工具调用机制")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_direct_ai())

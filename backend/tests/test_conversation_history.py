"""
测试对话历史持久化功能

验证 ConversationHistoryManager 的基本功能：
1. 创建和保存对话历史
2. 加载对话历史
3. 消息的增删改查
4. 序列化和反序列化
"""

import asyncio
import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.context.conversation_history import (
    ConversationHistoryManager,
    ConversationMessage,
    ToolCall
)


async def test_basic_crud():
    """测试基本的增删改查功能"""
    print("="*80)
    print("测试 1: 基本的增删改查功能")
    print("="*80)

    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 初始化管理器
        manager = ConversationHistoryManager(
            task_id="test_task_001",
            workspace_path=temp_dir
        )

        # 添加用户消息
        manager.append_message(
            role="user",
            content="分析 backend 目录"
        )

        # 添加助手消息（带工具调用）
        tool_calls = [
            ToolCall(
                id="test-tool-1",
                name="list_files",
                parameters={"directory": "backend", "recursive": True}
            )
        ]

        manager.append_message(
            role="assistant",
            content="我来帮你分析backend目录",
            tool_calls=tool_calls
        )

        # 保存历史
        success = await manager.save_history()
        assert success, "保存历史失败"

        # 验证文件存在
        assert manager.api_history_file.exists(), "历史文件不存在"

        # 打印统计信息
        stats = manager.get_stats()
        print(f"✅ 统计信息:")
        print(f"   - 总消息数: {stats['total_messages']}")
        print(f"   - 用户消息: {stats['user_messages']}")
        print(f"   - AI 消息: {stats['assistant_messages']}")

        # 验证消息内容
        assert stats['total_messages'] == 2, "消息数量不正确"
        assert stats['user_messages'] == 1, "用户消息数量不正确"
        assert stats['assistant_messages'] == 1, "AI 消息数量不正确"

        print("\n✅ 测试通过: 基本的增删改查功能\n")


async def test_save_and_load():
    """测试保存和加载功能"""
    print("="*80)
    print("测试 2: 保存和加载功能")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        task_id = "test_task_002"

        # 第一步：创建并保存历史
        print("\n📝 步骤 1: 创建并保存历史")
        manager1 = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=temp_dir
        )

        manager1.append_message(role="user", content="创建 test.md 文件")
        manager1.append_message(
            role="assistant",
            content="好的，我来创建文件",
            tool_calls=[
                ToolCall(
                    id="test-tool-2",
                    name="write_to_file",
                    parameters={"file_path": "test.md", "content": "# Test\n\nHello"}
                )
            ]
        )

        await manager1.save_history()
        print(f"✅ 已保存 {len(manager1.messages)} 条消息")

        # 第二步：加载历史到新的管理器
        print("\n📂 步骤 2: 加载历史")
        manager2 = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=temp_dir
        )

        success = await manager2.load_history()
        assert success, "加载历史失败"

        print(f"✅ 已加载 {len(manager2.messages)} 条消息")

        # 验证内容
        assert len(manager2.messages) == len(manager1.messages), "消息数量不匹配"

        for i, (msg1, msg2) in enumerate(zip(manager1.messages, manager2.messages)):
            assert msg1.role == msg2.role, f"消息 {i} 的角色不匹配"
            assert msg1.content == msg2.content, f"消息 {i} 的内容不匹配"

            if msg1.tool_calls:
                assert msg2.tool_calls is not None, f"消息 {i} 缺少工具调用"
                assert len(msg1.tool_calls) == len(msg2.tool_calls), f"消息 {i} 工具调用数量不匹配"

                for tc1, tc2 in zip(msg1.tool_calls, msg2.tool_calls):
                    assert tc1.name == tc2.name, "工具名称不匹配"
                    assert tc1.parameters == tc2.parameters, "工具参数不匹配"

        print("\n✅ 测试通过: 保存和加载功能\n")


async def test_tool_call_results():
    """测试工具调用结果的记录"""
    print("="*80)
    print("测试 3: 工具调用结果记录")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConversationHistoryManager(
            task_id="test_task_003",
            workspace_path=temp_dir
        )

        # 添加带工具调用的消息
        tool_call = ToolCall(
            id="test-tool-3",
            name="read_file",
            parameters={"file_path": "test.py"}
        )

        manager.append_message(
            role="assistant",
            content="让我读取文件",
            tool_calls=[tool_call]
        )

        # 更新工具调用结果
        manager.messages[-1].tool_calls[0].result = {
            "success": True,
            "data": {
                "file_path": "test.py",
                "content": "print('hello')"
            }
        }

        # 保存并加载
        await manager.save_history()

        manager2 = ConversationHistoryManager(
            task_id="test_task_003",
            workspace_path=temp_dir
        )
        await manager2.load_history()

        # 验证工具调用结果
        loaded_tc = manager2.messages[-1].tool_calls[0]
        assert loaded_tc.result is not None, "工具调用结果丢失"
        assert loaded_tc.result["success"] == True, "工具调用结果不正确"
        assert loaded_tc.result["data"]["content"] == "print('hello')", "文件内容不匹配"

        print("✅ 工具调用结果已正确保存和加载")
        print("\n✅ 测试通过: 工具调用结果记录\n")


async def test_api_message_conversion():
    """测试 API 消息格式转换"""
    print("="*80)
    print("测试 4: API 消息格式转换")
    print("="*80)

    manager = ConversationHistoryManager(
        task_id="test_task_004",
        workspace_path="."
    )

    # 添加不同类型的消息
    manager.append_message(role="system", content="你是一个AI助手")
    manager.append_message(role="user", content="你好")
    manager.append_message(
        role="assistant",
        content="你好！有什么我可以帮你的吗？"
    )

    # 转换为 API 格式
    api_messages = manager.to_api_messages()

    # 验证格式
    assert len(api_messages) == 3, "API 消息数量不正确"
    assert all("role" in msg for msg in api_messages), "缺少 role 字段"
    assert all("content" in msg for msg in api_messages), "缺少 content 字段"

    # 打印结果
    print("📋 API 消息格式:")
    for i, msg in enumerate(api_messages, 1):
        print(f"   {i}. {msg['role']}: {msg['content'][:50]}...")

    print("\n✅ 测试通过: API 消息格式转换\n")


async def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("[TEST] Conversation History Persistence Tests")
    print("="*80 + "\n")

    try:
        await test_basic_crud()
        await test_save_and_load()
        await test_tool_call_results()
        await test_api_message_conversion()

        print("="*80)
        print("[SUCCESS] All tests passed!")
        print("="*80 + "\n")

    except AssertionError as e:
        print(f"\n[FAILED] Test failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[ERROR] Error occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

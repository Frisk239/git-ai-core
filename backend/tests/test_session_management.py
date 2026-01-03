"""
测试会话管理功能

验证完整的会话管理工作流程：
1. 创建多个任务
2. 任务历史列表管理
3. 会话恢复功能
4. 删除和收藏功能
"""

import asyncio
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.context.task_history import TaskHistoryManager, HistoryItem
from app.core.context.conversation_history import (
    ConversationHistoryManager,
    ConversationMessage,
    ToolCall
)


async def test_task_lifecycle():
    """测试完整的任务生命周期"""
    print("="*80)
    print("测试 1: 任务生命周期管理")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        # 初始化管理器
        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        # 创建第一个任务
        print("\n步骤 1: 创建第一个任务")
        task_id_1 = "task_001"
        history_item_1 = task_manager.add_or_update_task(
            task_id=task_id_1,
            task_description="分析 backend 目录结构",
            api_provider="anthropic",
            api_model="claude-3-5-sonnet-20241022",
            repository_path=temp_dir,
        )

        # 添加对话历史
        conv_manager_1 = ConversationHistoryManager(
            task_id=task_id_1,
            workspace_path=temp_dir
        )
        conv_manager_1.append_message(role="user", content="分析 backend 目录")
        conv_manager_1.append_message(
            role="assistant",
            content="好的，我来分析目录结构",
            tool_calls=[ToolCall(id="tool-1", name="list_files", parameters={"dir": "backend"})]
        )
        await conv_manager_1.save_history()

        # 更新统计
        history_item_1.tokens_in = 100
        history_item_1.tokens_out = 200
        history_item_1.total_cost = 0.001

        # 保存任务历史
        await task_manager.save_history()

        print(f"创建任务: {task_id_1}")
        print(f"任务描述: {history_item_1.task}")
        print(f"对话消息数: {len(conv_manager_1.messages)}")

        # 创建第二个任务
        print("\n步骤 2: 创建第二个任务")
        task_id_2 = "task_002"
        history_item_2 = task_manager.add_or_update_task(
            task_id=task_id_2,
            task_description="创建新的 API 端点",
            api_provider="anthropic",
            api_model="claude-3-5-sonnet-20241022",
            repository_path=temp_dir,
        )

        conv_manager_2 = ConversationHistoryManager(
            task_id=task_id_2,
            workspace_path=temp_dir
        )
        conv_manager_2.append_message(role="user", content="创建用户认证 API")
        await conv_manager_2.save_history()

        history_item_2.tokens_in = 50
        history_item_2.tokens_out = 100
        history_item_2.total_cost = 0.0005

        await task_manager.save_history()

        print(f"创建任务: {task_id_2}")
        print(f"任务描述: {history_item_2.task}")

        # 验证文件结构
        print("\n步骤 3: 验证文件结构")
        task_dir_1 = Path(temp_dir) / ".ai" / "tasks" / task_id_1
        task_dir_2 = Path(temp_dir) / ".ai" / "tasks" / task_id_2
        history_file = Path(temp_dir) / ".ai" / "history" / "task_history.json"

        assert task_dir_1.exists(), f"任务目录不存在: {task_dir_1}"
        assert task_dir_2.exists(), f"任务目录不存在: {task_dir_2}"
        assert history_file.exists(), f"历史文件不存在: {history_file}"

        print(f"任务目录 1: {task_dir_1}")
        print(f"任务目录 2: {task_dir_2}")
        print(f"历史文件: {history_file}")

        print("\n测试通过: 任务生命周期管理\n")


async def test_search_and_filter():
    """测试搜索和过滤功能"""
    print("="*80)
    print("测试 2: 搜索和过滤功能")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        # 创建多个任务
        tasks = [
            ("task_001", "分析 backend 目录", False),
            ("task_002", "创建 API 端点", True),
            ("task_003", "修复登录 bug", False),
            ("task_004", "分析 frontend 代码", True),
        ]

        for task_id, description, is_favorite in tasks:
            item = task_manager.add_or_update_task(
                task_id=task_id,
                task_description=description,
                repository_path=temp_dir,
            )
            item.is_favorited = is_favorite

        await task_manager.save_history()

        # 测试搜索
        print("\n搜索 'API':")
        results = task_manager.search_tasks(query="API")
        for item in results:
            print(f"  - {item.id}: {item.task}")
        assert len(results) == 1, "搜索结果不正确"
        assert results[0].id == "task_002", "搜索结果不正确"

        # 测试过滤收藏
        print("\n只显示收藏:")
        results = task_manager.search_tasks(favorites_only=True)
        print(f"  找到 {len(results)} 个收藏任务")
        assert len(results) == 2, "过滤结果不正确"

        # 测试排序
        print("\n按成本排序:")
        for item in tasks:
            history_item = task_manager.get_task(item[0])
            if history_item:
                history_item.total_cost = float(item[0].split("_")[1])

        results = task_manager.search_tasks(sort_by="cost")
        print(f"  排序后第一个: {results[0].id}")
        assert results[0].id == "task_004", "排序不正确"

        print("\n测试通过: 搜索和过滤功能\n")


async def test_resume_session():
    """测试会话恢复功能"""
    print("="*80)
    print("测试 3: 会话恢复功能")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        task_id = "resume_test_001"

        # 第一步：创建并保存任务
        print("\n步骤 1: 创建原始任务")
        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        history_item = task_manager.add_or_update_task(
            task_id=task_id,
            task_description="实现用户登录功能",
            api_provider="anthropic",
            api_model="claude-3-5-sonnet-20241022",
            repository_path=temp_dir,
        )

        conv_manager = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=temp_dir
        )

        # 添加对话
        conv_manager.append_message(role="user", content="实现用户登录功能")
        conv_manager.append_message(
            role="assistant",
            content="我来实现用户登录功能",
            tool_calls=[
                ToolCall(
                    id="tool-2",
                    name="write_to_file",
                    parameters={"file": "auth.py", "content": "login code"}
                )
            ]
        )
        await conv_manager.save_history()
        await task_manager.save_history()

        print(f"保存任务: {task_id}")
        print(f"消息数: {len(conv_manager.messages)}")

        # 第二步：加载任务（模拟恢复会话）
        print("\n步骤 2: 恢复任务")
        task_manager_2 = TaskHistoryManager(workspace_path=temp_dir)
        await task_manager_2.load_history()

        loaded_item = task_manager_2.get_task(task_id)
        assert loaded_item is not None, "任务加载失败"
        assert loaded_item.task == "实现用户登录功能", "任务描述不匹配"

        print(f"加载任务: {loaded_item.id}")
        print(f"任务描述: {loaded_item.task}")

        # 加载对话历史
        conv_manager_2 = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=temp_dir
        )
        await conv_manager_2.load_history()

        assert len(conv_manager_2.messages) == 2, "消息数量不匹配"
        assert conv_manager_2.messages[0].content == "实现用户登录功能", "消息内容不匹配"

        print(f"加载消息数: {len(conv_manager_2.messages)}")

        # 验证工具调用
        assert conv_manager_2.messages[1].tool_calls is not None, "工具调用丢失"
        assert len(conv_manager_2.messages[1].tool_calls) == 1, "工具调用数量不正确"
        assert conv_manager_2.messages[1].tool_calls[0].name == "write_to_file", "工具名称不匹配"

        print("工具调用验证通过")

        print("\n测试通过: 会话恢复功能\n")


async def test_delete_and_favorite():
    """测试删除和收藏功能"""
    print("="*80)
    print("测试 4: 删除和收藏功能")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        # 创建任务
        task_id = "delete_test_001"
        item = task_manager.add_or_update_task(
            task_id=task_id,
            task_description="测试任务",
            repository_path=temp_dir,
        )

        # 创建对话历史
        conv_manager = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=temp_dir
        )
        conv_manager.append_message(role="user", content="测试消息")
        await conv_manager.save_history()
        await task_manager.save_history()

        print(f"\n创建任务: {task_id}")
        print(f"初始收藏状态: {item.is_favorited}")

        # 测试收藏
        print("\n切换收藏状态")
        new_state = task_manager.toggle_favorite(task_id)
        assert new_state == True, "收藏状态不正确"
        await task_manager.save_history()

        # 重新加载验证
        await task_manager.load_history()
        loaded_item = task_manager.get_task(task_id)
        assert loaded_item.is_favorited == True, "收藏状态未保存"
        print(f"新收藏状态: {loaded_item.is_favorited}")

        # 测试删除
        print("\n删除任务")
        # 先删除对话历史文件
        files_deleted = conv_manager.delete_history_files()
        assert files_deleted == True, "文件删除失败"

        # 再从任务历史中移除
        deleted = task_manager.delete_task(task_id)
        assert deleted == True, "任务历史删除失败"
        await task_manager.save_history()

        # 验证删除
        await task_manager.load_history()
        found_item = task_manager.get_task(task_id)
        assert found_item is None, "任务未从历史中删除"

        # 验证文件已删除
        task_dir = Path(temp_dir) / ".ai" / "tasks" / task_id
        assert not task_dir.exists(), "任务目录未删除"

        print("任务已删除")

        print("\n测试通过: 删除和收藏功能\n")


async def test_statistics():
    """测试统计功能"""
    print("="*80)
    print("测试 5: 统计功能")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        # 创建多个任务
        for i in range(5):
            item = task_manager.add_or_update_task(
                task_id=f"stats_test_{i:03d}",
                task_description=f"测试任务 {i}",
                repository_path=temp_dir,
            )
            item.tokens_in = 100 * (i + 1)
            item.tokens_out = 200 * (i + 1)
            item.total_cost = 0.001 * (i + 1)
            if i % 2 == 0:
                item.is_favorited = True

        await task_manager.save_history()

        # 获取统计信息
        stats = task_manager.get_stats()

        print(f"\n统计信息:")
        print(f"  总任务数: {stats['total_tasks']}")
        print(f"  总 Token 数: {stats['total_tokens']}")
        print(f"  总成本: ${stats['total_cost']:.4f}")
        print(f"  收藏数: {stats['favorite_count']}")

        assert stats['total_tasks'] == 5, "任务数不正确"
        assert stats['favorite_count'] == 3, "收藏数不正确"
        assert stats['total_tokens'] > 0, "Token 数不正确"
        assert stats['total_cost'] > 0, "成本不正确"

        print("\n测试通过: 统计功能\n")


async def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("[TEST] Session Management Tests")
    print("="*80 + "\n")

    try:
        await test_task_lifecycle()
        await test_search_and_filter()
        await test_resume_session()
        await test_delete_and_favorite()
        await test_statistics()

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

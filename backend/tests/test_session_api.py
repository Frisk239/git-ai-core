"""
测试会话管理 API

使用 FastAPI TestClient 验证所有 API 端点
"""

import asyncio
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_list_tasks():
    """测试获取任务列表 API"""
    print("="*80)
    print("测试 API 1: 获取任务列表")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        # 准备测试数据
        from app.core.context.task_history import TaskHistoryManager
        from app.core.context.conversation_history import ConversationHistoryManager

        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        # 创建几个测试任务
        for i in range(3):
            task_id = f"api_test_{i:03d}"
            item = task_manager.add_or_update_task(
                task_id=task_id,
                task_description=f"测试任务 {i}",
                repository_path=temp_dir,
            )
            item.tokens_in = 100 * (i + 1)
            item.tokens_out = 200 * (i + 1)
            item.total_cost = 0.001 * (i + 1)

            # 创建对话历史
            conv_manager = ConversationHistoryManager(
                task_id=task_id,
                workspace_path=temp_dir
            )
            conv_manager.append_message(role="user", content=f"任务 {i}")
            asyncio.run(conv_manager.save_history())

        asyncio.run(task_manager.save_history())

        # 调用 API
        print(f"\n调用 GET /api/sessions/list?repository_path={temp_dir}")
        response = client.get(
            f"/api/sessions/list",
            params={"repository_path": temp_dir}
        )

        print(f"状态码: {response.status_code}")
        assert response.status_code == 200, f"API 调用失败: {response.text}"

        data = response.json()
        print(f"任务数量: {data['total_count']}")
        print(f"总 Token 数: {data['total_tokens']}")
        print(f"总成本: ${data['total_cost']:.4f}")
        print(f"返回任务数: {len(data['tasks'])}")

        assert data['total_count'] == 3, "任务总数不正确"
        assert len(data['tasks']) == 3, "返回任务数不正确"
        assert data['total_tokens'] > 0, "Token 总数不正确"
        assert data['total_cost'] > 0, "总成本不正确"

        # 验证任务数据
        task = data['tasks'][0]
        assert 'id' in task, "缺少 id 字段"
        assert 'task' in task, "缺少 task 字段"
        assert 'ts' in task, "缺少 ts 字段"
        assert 'tokens_in' in task, "缺少 tokens_in 字段"
        assert 'tokens_out' in task, "缺少 tokens_out 字段"

        print("\n测试通过: 获取任务列表 API\n")


def test_api_search_and_filter():
    """测试搜索和过滤 API"""
    print("="*80)
    print("测试 API 2: 搜索和过滤")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        # 准备测试数据
        from app.core.context.task_history import TaskHistoryManager

        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        tasks = [
            ("search_001", "分析 backend 代码", True),
            ("search_002", "创建前端页面", False),
            ("search_003", "修复 API bug", True),
        ]

        for task_id, description, is_favorite in tasks:
            item = task_manager.add_or_update_task(
                task_id=task_id,
                task_description=description,
                repository_path=temp_dir,
            )
            item.is_favorited = is_favorite

        asyncio.run(task_manager.save_history())

        # 测试搜索
        print("\n测试搜索功能")
        response = client.get(
            f"/api/sessions/list",
            params={
                "repository_path": temp_dir,
                "search_query": "API"
            }
        )

        assert response.status_code == 200
        data = response.json()
        print(f"搜索 'API' 结果数: {len(data['tasks'])}")
        assert len(data['tasks']) == 1, "搜索结果不正确"
        assert data['tasks'][0]['id'] == "search_003", "搜索结果不正确"

        # 测试过滤收藏
        print("\n测试过滤收藏")
        response = client.get(
            f"/api/sessions/list",
            params={
                "repository_path": temp_dir,
                "favorites_only": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        print(f"收藏任务数: {len(data['tasks'])}")
        assert len(data['tasks']) == 2, "过滤结果不正确"

        # 测试排序
        print("\n测试排序")
        response = client.get(
            f"/api/sessions/list",
            params={
                "repository_path": temp_dir,
                "sort_by": "oldest"
            }
        )

        assert response.status_code == 200
        data = response.json()
        print(f"第一个任务: {data['tasks'][0]['id']}")
        # oldest 排序应该是最早的在前
        assert data['tasks'][0]['id'] == "search_001", "排序不正确"

        print("\n测试通过: 搜索和过滤 API\n")


def test_api_load_task():
    """测试加载任务 API"""
    print("="*80)
    print("测试 API 3: 加载任务详情")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        # 准备测试数据
        from app.core.context.task_history import TaskHistoryManager
        from app.core.context.conversation_history import ConversationHistoryManager

        task_id = "load_test_001"

        task_manager = TaskHistoryManager(workspace_path=temp_dir)
        item = task_manager.add_or_update_task(
            task_id=task_id,
            task_description="实现登录功能",
            api_provider="anthropic",
            api_model="claude-3-5-sonnet-20241022",
            repository_path=temp_dir,
        )

        conv_manager = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=temp_dir
        )
        conv_manager.append_message(role="user", content="实现登录功能")
        conv_manager.append_message(
            role="assistant",
            content="好的，我来实现",
        )

        asyncio.run(conv_manager.save_history())
        asyncio.run(task_manager.save_history())

        # 调用 API
        print(f"\n调用 GET /api/sessions/load/{task_id}")
        response = client.get(
            f"/api/sessions/load/{task_id}",
            params={"repository_path": temp_dir}
        )

        print(f"状态码: {response.status_code}")
        assert response.status_code == 200, f"API 调用失败: {response.text}"

        data = response.json()
        print(f"任务 ID: {data['task_id']}")
        print(f"任务描述: {data['task']}")
        print(f"消息数量: {data['message_count']}")
        print(f"API 提供商: {data['api_provider']}")
        print(f"API 模型: {data['api_model']}")

        assert data['task_id'] == task_id, "任务 ID 不匹配"
        assert data['task'] == "实现登录功能", "任务描述不匹配"
        assert data['message_count'] == 2, "消息数量不正确"
        assert len(data['messages']) == 2, "消息列表不正确"
        assert data['api_provider'] == "anthropic", "API 提供商不匹配"
        assert data['api_model'] == "claude-3-5-sonnet-20241022", "API 模型不匹配"

        # 验证消息格式
        msg = data['messages'][0]
        assert 'role' in msg, "消息缺少 role 字段"
        assert 'content' in msg, "消息缺少 content 字段"

        print("\n测试通过: 加载任务详情 API\n")


def test_api_toggle_favorite():
    """测试切换收藏 API"""
    print("="*80)
    print("测试 API 4: 切换收藏状态")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        # 准备测试数据
        from app.core.context.task_history import TaskHistoryManager

        task_id = "fav_test_001"
        task_manager = TaskHistoryManager(workspace_path=temp_dir)

        item = task_manager.add_or_update_task(
            task_id=task_id,
            task_description="收藏测试任务",
            repository_path=temp_dir,
        )
        assert item.is_favorited == False, "初始收藏状态应该是 False"

        asyncio.run(task_manager.save_history())

        # 调用 API 切换收藏
        print(f"\n调用 POST /api/sessions/toggle-favorite/{task_id}")
        response = client.post(
            f"/api/sessions/toggle-favorite/{task_id}",
            params={"repository_path": temp_dir}
        )

        print(f"状态码: {response.status_code}")
        assert response.status_code == 200, f"API 调用失败: {response.text}"

        data = response.json()
        print(f"操作成功: {data['success']}")
        print(f"新收藏状态: {data['is_favorited']}")

        assert data['success'] == True, "操作失败"
        assert data['is_favorited'] == True, "收藏状态未切换"

        # 验证状态已保存
        asyncio.run(task_manager.load_history())
        loaded_item = task_manager.get_task(task_id)
        assert loaded_item.is_favorited == True, "收藏状态未保存"

        print("\n测试通过: 切换收藏状态 API\n")


def test_api_delete_task():
    """测试删除任务 API"""
    print("="*80)
    print("测试 API 5: 删除任务")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        # 准备测试数据
        from app.core.context.task_history import TaskHistoryManager
        from app.core.context.conversation_history import ConversationHistoryManager

        task_id = "delete_api_test_001"

        task_manager = TaskHistoryManager(workspace_path=temp_dir)
        task_manager.add_or_update_task(
            task_id=task_id,
            task_description="待删除任务",
            repository_path=temp_dir,
        )

        conv_manager = ConversationHistoryManager(
            task_id=task_id,
            workspace_path=temp_dir
        )
        conv_manager.append_message(role="user", content="测试")

        asyncio.run(conv_manager.save_history())
        asyncio.run(task_manager.save_history())

        # 验证任务存在
        task_dir = Path(temp_dir) / ".ai" / "tasks" / task_id
        assert task_dir.exists(), "任务目录不存在"

        # 调用 API 删除
        print(f"\n调用 POST /api/sessions/delete/{task_id}")
        response = client.post(
            f"/api/sessions/delete/{task_id}",
            params={"repository_path": temp_dir}
        )

        print(f"状态码: {response.status_code}")
        assert response.status_code == 200, f"API 调用失败: {response.text}"

        data = response.json()
        print(f"操作成功: {data['success']}")
        print(f"消息: {data['message']}")

        assert data['success'] == True, "删除失败"

        # 验证已删除
        asyncio.run(task_manager.load_history())
        assert task_manager.get_task(task_id) is None, "任务未从历史中删除"
        assert not task_dir.exists(), "任务目录未删除"

        print("\n测试通过: 删除任务 API\n")


def test_api_error_handling():
    """测试 API 错误处理"""
    print("="*80)
    print("测试 API 6: 错误处理")
    print("="*80)

    with tempfile.TemporaryDirectory() as temp_dir:
        # 测试加载不存在的任务
        print("\n测试加载不存在的任务")
        response = client.get(
            f"/api/sessions/load/nonexistent_task",
            params={"repository_path": temp_dir}
        )

        print(f"状态码: {response.status_code}")
        assert response.status_code == 404, "应该返回 404"
        print("正确返回 404 错误")

        print("\n测试通过: 错误处理 API\n")


def main():
    """运行所有 API 测试"""
    print("\n" + "="*80)
    print("[TEST] Session Management API Tests")
    print("="*80 + "\n")

    try:
        test_api_list_tasks()
        test_api_search_and_filter()
        test_api_load_task()
        test_api_toggle_favorite()
        test_api_delete_task()
        test_api_error_handling()

        print("="*80)
        print("[SUCCESS] All API tests passed!")
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
    main()

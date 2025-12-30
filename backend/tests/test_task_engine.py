"""
任务引擎测试

测试完整的对话+工具调用流程
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.task import TaskEngine
from app.core.tools import get_tool_coordinator


@pytest.mark.asyncio
async def test_task_engine_basic():
    """测试任务引擎基本功能"""
    # 初始化
    coordinator = get_tool_coordinator()
    engine = TaskEngine()

    # 模拟 AI 配置
    ai_config = {
        "ai_provider": "openai",  # 或其他可用的提供商
        "ai_model": "gpt-4o-mini",
        "ai_api_key": "test-key",  # 使用测试密钥
        "temperature": 0.7,
        "max_tokens": 2000
    }

    # 获取当前项目路径作为测试仓库
    repo_path = os.path.join(os.path.dirname(__file__), '..', '..')

    print("\n" + "="*60)
    print("测试任务引擎")
    print("="*60)

    # 执行任务
    user_input = "请查看当前 Git 仓库的状态，并列出 backend/app 目录下的文件"

    print(f"\n用户输入: {user_input}")
    print(f"仓库路径: {repo_path}\n")

    events_collected = []

    try:
        async for event in engine.execute_task(
            user_input=user_input,
            repository_path=repo_path,
            ai_config=ai_config
        ):
            events_collected.append(event)

            # 打印事件
            event_type = event.get("type")
            iteration = event.get("iteration", 0)

            if event_type == "api_request_started":
                print(f"[迭代 {iteration}] 开始 API 请求...")

            elif event_type == "api_response":
                content_preview = event.get("content", "")[:100]
                print(f"[迭代 {iteration}] 收到 AI 响应: {content_preview}...")

            elif event_type == "tool_calls_detected":
                tool_calls = event.get("tool_calls", [])
                print(f"[迭代 {iteration}] 检测到 {len(tool_calls)} 个工具调用")
                for tc in tool_calls:
                    print(f"  - {tc.get('name')}")

            elif event_type == "tool_execution_started":
                print(f"[迭代 {iteration}] 执行工具: {event.get('tool_name')}")

            elif event_type == "tool_execution_completed":
                tool_name = event.get("tool_name")
                result = event.get("result")
                success = result.get("success") if result else False
                print(f"[迭代 {iteration}] 工具 {tool_name}: {'成功' if success else '失败'}")

            elif event_type == "completion":
                print(f"\n[完成] {event.get('content', '')[:200]}...")

            elif event_type == "error":
                print(f"\n[错误] {event.get('message')}")

    except Exception as e:
        print(f"\n任务执行异常: {e}")
        import traceback
        traceback.print_exc()

    # 输出统计
    print("\n" + "="*60)
    print("执行统计")
    print("="*60)
    print(f"总事件数: {len(events_collected)}")

    # 按类型统计
    event_types = {}
    for event in events_collected:
        et = event.get("type", "unknown")
        event_types[et] = event_types.get(et, 0) + 1

    print("\n事件类型分布:")
    for event_type, count in sorted(event_types.items()):
        print(f"  - {event_type}: {count}")


def test_tool_call_parser():
    """测试工具调用解析器"""
    from app.core.task import ToolCallParser

    parser = ToolCallParser()

    # 测试用例
    test_cases = [
        # 格式 1: ```tool 代码块
        '''
```tool
{"name": "read_file", "parameters": {"file_path": "README.md"}}
```
''',
        # 格式 2: 多个工具调用
        '''
```tool
{"name": "git_status", "parameters": {}}
{"name": "git_log", "parameters": {"limit": 5}}
```
''',
        # 格式 3: 直接 JSON（在代码块外）
        '{"name": "list_files", "parameters": {"directory": "backend", "recursive": false}}',
    ]

    print("\n" + "="*60)
    print("测试工具调用解析器")
    print("="*60)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"输入: {test_case[:50]}...")

        tool_calls = parser.extract_tool_calls(test_case)

        print(f"提取到 {len(tool_calls)} 个工具调用")
        for j, call in enumerate(tool_calls, 1):
            print(f"  {j}. {call.get('name')} - {call.get('parameters', {})}")


def test_prompt_builder():
    """测试提示词构建器"""
    from app.core.task import PromptBuilder
    from app.core.tools import get_tool_coordinator

    coordinator = get_tool_coordinator()
    builder = PromptBuilder(coordinator)

    print("\n" + "="*60)
    print("测试系统提示词构建")
    print("="*60)

    context = {
        "repository_path": "/path/to/repo"
    }

    # 测试提示词生成
    import asyncio

    async def test():
        prompt = await builder.build_prompt(context)

        print("\n生成的系统提示词:")
        print("="*60)
        print(prompt[:500] + "...")
        print(f"\n提示词总长度: {len(prompt)} 字符")

    asyncio.run(test())


if __name__ == "__main__":
    print("\n" + "="*60)
    print("开始测试任务引擎")
    print("="*60 + "\n")

    # 运行测试
    print("\n### 测试 1: 工具调用解析器 ###")
    test_tool_call_parser()

    print("\n### 测试 2: 系统提示词构建器 ###")
    test_prompt_builder()

    print("\n### 测试 3: 任务引擎（需要有效的 AI 配置）###")
    print("提示: 这个测试需要有效的 AI API 密钥")
    print("如果没有配置，会跳过实际 API 调用\n")

    # 只有在有有效配置时才运行完整测试
    # pytest.main([__file__, "-v", "-s", "-k", "test_task_engine_basic"])

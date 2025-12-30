"""
真实 API 测试 - 使用 DeepSeek 测试完整的工具调用流程
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.task import TaskEngine


async def test_with_real_api():
    """使用真实的 DeepSeek API 测试任务引擎"""

    # DeepSeek API 配置（使用现有的）
    ai_config = {
        "ai_provider": "deepseek",
        "ai_model": "deepseek-chat",
        "ai_api_key": "sk-b220ecfa259f47fbb1c2f873327933c8",
        "ai_base_url": "https://api.deepseek.com/v1",
        "temperature": 0.7,
        "max_tokens": 4000
    }

    # 获取当前项目路径作为测试仓库
    repo_path = os.path.join(os.path.dirname(__file__), '..', '..')

    # 创建任务引擎
    engine = TaskEngine()

    # 测试用例
    test_queries = [
        "请查看当前 Git 仓库的状态，并列出 backend/app/core 目录下的文件",
        "请读取 README.md 文件的内容，然后告诉这个项目是做什么的",
        "请分析 backend/app/core/tools/coordinator.py 文件中有哪些类定义"
    ]

    # 选择第一个测试用例
    user_input = test_queries[0]

    print("\n" + "="*80)
    print("真实 API 测试 - DeepSeek")
    print("="*80)
    print(f"\n用户输入: {user_input}")
    print(f"仓库路径: {repo_path}")
    print(f"AI 模型: {ai_config['ai_model']}")
    print("\n开始执行任务...\n")

    # 收集所有事件
    events = []
    start_time = asyncio.get_event_loop().time()

    try:
        async for event in engine.execute_task(
            user_input=user_input,
            repository_path=repo_path,
            ai_config=ai_config
        ):
            events.append(event)

            # 实时显示事件
            event_type = event.get("type")
            iteration = event.get("iteration", 0)

            if event_type == "api_request_started":
                print(f"🔄 [迭代 {iteration}] 发送 API 请求...")

            elif event_type == "api_response":
                content = event.get("content", "")
                print(f"📥 [迭代 {iteration}] 收到 AI 响应 ({len(content)} 字符)")
                # 显示响应的前 200 字符
                if len(content) > 0:
                    preview = content[:200].replace("\n", " ")
                    print(f"   预览: {preview}...")

            elif event_type == "tool_calls_detected":
                tool_calls = event.get("tool_calls", [])
                print(f"🔧 [迭代 {iteration}] 检测到 {len(tool_calls)} 个工具调用:")
                for tc in tool_calls:
                    params = tc.get("parameters", {})
                    print(f"   - {tc.get('name')}: {params}")

            elif event_type == "tool_execution_started":
                print(f"⚙️  [迭代 {iteration}] 执行工具: {event.get('tool_name')}")

            elif event_type == "tool_execution_completed":
                tool_name = event.get("tool_name")
                result = event.get("result", {})
                success = result.get("success", False)

                if success:
                    data = result.get("data", {})
                    # 根据工具类型显示不同的信息
                    if tool_name == "git_status":
                        branch = data.get("branch", "N/A")
                        is_clean = data.get("is_clean", False)
                        print(f"✅ [迭代 {iteration}] {tool_name} - 分支: {branch}, 干净: {is_clean}")
                    elif tool_name == "list_files":
                        count = data.get("total_count", 0)
                        print(f"✅ [迭代 {iteration}] {tool_name} - 找到 {count} 项")
                    elif tool_name == "read_file":
                        size = data.get("size", 0)
                        print(f"✅ [迭代 {iteration}] {tool_name} - 文件大小: {size} 字节")
                    elif tool_name == "list_code_definitions":
                        count = data.get("total_count", 0)
                        print(f"✅ [迭代 {iteration}] {tool_name} - {count} 个定义")
                    else:
                        print(f"✅ [迭代 {iteration}] {tool_name} - 执行成功")
                else:
                    error = result.get("error", "Unknown error")
                    print(f"❌ [迭代 {iteration}] {tool_name} - 失败: {error}")

            elif event_type == "completion":
                content = event.get("content", "")
                print(f"\n🎉 任务完成!")
                print(f"\n最终回答:\n{'-'*60}")
                print(content)
                print("-"*60)

            elif event_type == "error":
                print(f"\n❌ 错误: {event.get('message')}")

        # 计算耗时
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # 输出统计
        print("\n" + "="*80)
        print("执行统计")
        print("="*80)
        print(f"总耗时: {duration:.2f} 秒")
        print(f"总事件数: {len(events)}")

        # 按类型统计事件
        event_types = {}
        for event in events:
            et = event.get("type", "unknown")
            event_types[et] = event_types.get(et, 0) + 1

        print("\n事件类型分布:")
        for event_type, count in sorted(event_types.items()):
            print(f"  - {event_type}: {count}")

        # 统计工具使用情况
        tool_executions = [e for e in events if e.get("type") == "tool_execution_completed"]
        successful_tools = sum(1 for e in tool_executions if e.get("result", {}).get("success", False))
        failed_tools = len(tool_executions) - successful_tools

        print(f"\n工具执行统计:")
        print(f"  - 总工具调用: {len(tool_executions)}")
        print(f"  - 成功: {successful_tools}")
        print(f"  - 失败: {failed_tools}")

        print("\n✅ 测试完成!")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("开始真实 API 测试")
    print("="*80)

    # 运行测试
    asyncio.run(test_with_real_api())

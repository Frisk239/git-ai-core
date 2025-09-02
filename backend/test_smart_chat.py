import asyncio
import json
from app.core.advanced_smart_conversation_manager import advanced_smart_conversation_manager

async def test_smart_chat():
    """测试智能对话功能，验证文件名称显示"""
    
    # 创建一个测试项目路径（使用当前目录）
    test_project_path = "."
    
    # 启动新对话
    print("=== 启动新对话 ===")
    start_response = await advanced_smart_conversation_manager.process_smart_chat(
        conversation_id="test-conversation-123",
        project_path=test_project_path,
        user_query="请分析这个项目的README文件"
    )
    
    print(f"对话ID: {start_response['conversation_id']}")
    print(f"AI响应: {start_response['response'][:100]}...")
    
    # 检查工具调用结果
    if start_response['tool_calls']:
        print(f"\n=== 工具调用结果 ===")
        for i, tool_call in enumerate(start_response['tool_calls'], 1):
            print(f"{i}. 工具名称: {tool_call['tool_name']}")
            print(f"   文件路径: {tool_call.get('file_path', '未知')}")
            print(f"   参数文件路径: {tool_call['arguments'].get('file_path', '未知')}")
            print(f"   调用原因: {tool_call.get('reason', '无原因')}")
            print(f"   调用状态: {'成功' if tool_call['result']['success'] else '失败'}")
            print()
    
    # 检查分析上下文
    if 'analysis_context' in start_response:
        print("=== 分析上下文 ===")
        context = start_response['analysis_context']
        print(f"查询: {context['query']}")
        print(f"选择的文件数: {len(context['selected_files'])}")
        print(f"成功读取的文件数: {context['successful_reads']}")
        
        if context['selected_files']:
            print("\n选择的文件列表:")
            for file_info in context['selected_files']:
                print(f"  - {file_info['file_path']} ({file_info.get('reason', '无原因')})")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_smart_chat())

#!/usr/bin/env python3
"""
测试智能对话管理器的优化功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.advanced_smart_conversation_manager import advanced_smart_conversation_manager

async def test_smart_chat():
    """测试智能对话功能"""
    print("🤖 测试智能对话管理器优化功能")
    print("=" * 50)
    
    # 测试用例
    test_cases = [
        {
            "query": "请分析这个项目的README文档",
            "description": "文档查询测试"
        },
        {
            "query": "查看项目的依赖配置和包管理文件",
            "description": "配置查询测试"
        },
        {
            "query": "分析main.py和app.py文件",
            "description": "源代码文件查询测试"
        },
        {
            "query": "这个项目使用什么框架和技术栈",
            "description": "技术栈查询测试"
        },
        {
            "query": "项目的配置文件在哪里",
            "description": "配置文件查询测试"
        }
    ]
    
    # 使用当前目录作为测试项目路径
    project_path = os.getcwd()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试用例 {i}: {test_case['description']}")
        print(f"  查询: '{test_case['query']}'")
        
        try:
            result = await advanced_smart_conversation_manager.process_smart_chat(
                conversation_id=f"test_{i}",
                project_path=project_path,
                user_query=test_case["query"]
            )
            
            print(f"✅ 测试成功")
            print(f"  响应长度: {len(result.get('response', ''))} 字符")
            print(f"  选择的文件数: {len(result.get('tool_calls', []))}")
            
            # 显示选择的文件
            if result.get('tool_calls'):
                print("  选择的文件:")
                for tool_call in result['tool_calls']:
                    print(f"    - {tool_call.get('file_path', '未知')}: {tool_call.get('reason', '无原因')}")
            
        except Exception as e:
            print(f"❌ 测试失败: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_smart_chat())

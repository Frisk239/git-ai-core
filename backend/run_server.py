"""
FastAPI服务器启动脚本
在Windows上使用ProactorEventLoop以支持子进程
"""
import sys
import asyncio

# Windows上需要设置事件循环策略以支持子进程
# 这必须在创建事件循环之前完成
if sys.platform == 'win32':
    print("=" * 70)
    print("[INIT] Windows detected")
    print("[INIT] Setting WindowsProactorEventLoopPolicy for subprocess support")

    # 设置策略
    policy = asyncio.WindowsProactorEventLoopPolicy()
    asyncio.set_event_loop_policy(policy)

    # 立即创建并设置新的事件循环（关键步骤！）
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)

    print("[INIT] Event loop policy set successfully")
    print(f"[INIT] Created event loop: {type(loop).__name__}")
    print("=" * 70)
else:
    print("[INIT] Non-Windows platform, using default event loop policy")

import uvicorn

if __name__ == "__main__":
    print("=" * 70)
    print("[START] Starting Git AI Core backend server...")
    print(f"[START] Platform: {sys.platform}")
    print(f"[START] Python version: {sys.version}")

    # 显示当前事件循环类型
    try:
        current_loop = asyncio.get_event_loop()
        print(f"[START] Current event loop: {type(current_loop).__name__}")
    except:
        print(f"[START] No event loop yet (will be created by uvicorn)")

    print("=" * 70)

    # 在Windows上必须禁用reload，因为reload会导致事件循环在策略设置之前创建
    reload_mode = False if sys.platform == 'win32' else True

    print(f"[START] Reload mode: {'enabled' if reload_mode else 'disabled (Windows)'}")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_mode,
        log_level="info"
    )

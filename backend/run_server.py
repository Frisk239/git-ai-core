"""
FastAPI服务器启动脚本
在Windows上使用ProactorEventLoop以支持子进程
"""
import sys
import asyncio
import uvicorn

# Windows上需要设置事件循环策略以支持子进程
# 这必须在创建事件循环之前完成
if sys.platform == 'win32':
    print("=" * 70)
    print("[INIT] Windows detected")
    print("[INIT] Setting WindowsProactorEventLoopPolicy for subprocess support")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[INIT] Event loop policy set successfully")
    print("=" * 70)
else:
    print("[INIT] Non-Windows platform, using default event loop policy")

if __name__ == "__main__":
    print("=" * 70)
    print("[START] Starting Git AI Core backend server...")
    print(f"[START] Platform: {sys.platform}")
    print(f"[START] Python version: {sys.version}")
    print("=" * 70)

    # 在Windows上必须禁用reload，因为reload会导致事件循环在策略设置之前创建
    reload_mode = False if sys.platform == 'win32' else True

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_mode,
        log_level="info"
    )

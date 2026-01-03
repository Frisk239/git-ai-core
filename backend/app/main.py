from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sys
import asyncio
from contextlib import asynccontextmanager
import logging

# Windows上需要设置事件循环策略以支持子进程
# 必须在导入任何其他模块之前设置，必须在创建事件循环之前设置
if sys.platform == 'win32':
    print("[INIT] Setting WindowsProactorEventLoopPolicy for subprocess support")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[INIT] WindowsProactorEventLoopPolicy set successfully")

from app.api.routes import git, ai, mcp, projects, config, github, chat, sessions
from app.core.git_manager import GitManager
from app.core.ai_manager import AIManager
from app.core.mcp_server import MCPServerManager
from app.core.database import init_db

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Git AI Core...")
    
    # 初始化数据库
    init_db()
    logger.info("Database initialized")
    
    # 初始化管理器
    app.state.git_manager = GitManager()
    app.state.ai_manager = AIManager()
    app.state.mcp_manager = MCPServerManager()
    
    # 从数据库加载仓库
    loaded_count = app.state.git_manager.load_repositories_from_database()
    logger.info(f"Loaded {loaded_count} repositories from database")
    
    yield
    # Shutdown
    logger.info("Shutting down Git AI Core...")

app = FastAPI(
    title="Git AI Core",
    description="AI-powered Git project understanding assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(git.router, prefix="/api/git", tags=["git"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(config.router, prefix="/api", tags=["config"])
app.include_router(github.router, prefix="/api", tags=["github"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])

# 挂载静态文件目录 - 支持项目文档和图片访问
app.mount("/static", StaticFiles(directory="."), name="static")

# WebSocket endpoint for real-time communication
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
async def root():
    return {"message": "Git AI Core API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# 注意：不要直接运行此文件
# 请使用根目录的 run_server.py 启动服务器
# 这确保了在Windows上正确设置事件循环策略

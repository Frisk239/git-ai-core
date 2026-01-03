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


async def _initialize_mcp_servers(mcp_manager: MCPServerManager):
    """
    初始化并启动所有已启用的 MCP 服务器

    参考 Cline 设计：在应用启动时立即启动所有已启用的 MCP 服务器
    这样在构建系统提示词时，MCP 服务器已经准备就绪，可以直接获取工具列表
    """
    try:
        servers = mcp_manager.list_servers()
        print(f"📋 发现 {len(servers)} 个配置的 MCP 服务器")
        logger.info(f"Found {len(servers)} configured MCP servers")

        for server_name, config in servers.items():
            # 只启动已启用的服务器
            enabled = config.get("enabled", True)
            print(f"   - {server_name}: enabled={enabled}")

            if not enabled:
                logger.info(f"Skipping disabled MCP server: {server_name}")
                continue

            try:
                print(f"🚀 正在启动 MCP 服务器: {server_name}")
                logger.info(f"Starting MCP server: {server_name}")
                success = await mcp_manager.start_server(server_name)
                print(f"   启动结果: {success}")

                if success:
                    # 获取服务器状态
                    status = await mcp_manager.get_server_status(server_name)
                    connected = status.get("connected", False)
                    print(f"   连接状态: {connected}")

                    if connected:
                        # 获取工具列表
                        tools = await mcp_manager.list_tools(server_name)
                        tool_count = len(tools) if tools else 0

                        # 获取资源列表
                        resources = await mcp_manager.list_resources(server_name)
                        resource_count = len(resources) if resources else 0

                        result_msg = (
                            f"✅ MCP server '{server_name}' started successfully "
                            f"({tool_count} tools, {resource_count} resources)"
                        )
                        print(f"   {result_msg}")
                        logger.info(result_msg)
                    else:
                        warn_msg = f"⚠️ MCP server '{server_name}' started but not connected"
                        print(f"   {warn_msg}")
                        logger.warning(warn_msg)
                else:
                    error_msg = f"❌ Failed to start MCP server: {server_name}"
                    print(f"   {error_msg}")
                    logger.warning(error_msg)

            except Exception as e:
                logger.error(f"Failed to start MCP server '{server_name}': {e}", exc_info=True)

        logger.info("MCP servers initialization completed")

    except Exception as e:
        logger.error(f"Failed to initialize MCP servers: {e}", exc_info=True)


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

    # 🔥 参考 Cline：应用启动时自动启动所有已启用的 MCP 服务器
    logger.info("开始初始化 MCP 服务器...")
    print("\n" + "="*80)
    print("🔧 初始化 MCP 服务器...")
    print("="*80)
    await _initialize_mcp_servers(app.state.mcp_manager)
    print("✅ MCP 服务器初始化完成\n")
    logger.info("MCP 服务器初始化完成")

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

"""
MCP传输层实现
支持stdio和HTTP两种传输方式
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable, Any, Dict, Union
from pathlib import Path
import logging

from app.core.mcp_protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCNotification,
    JSONRPCCodec,
    JSONRPCMessage
)


logger = logging.getLogger(__name__)


class MCPTransportError(Exception):
    """传输层错误"""
    pass


class MCPTransport(ABC):
    """MCP传输层抽象基类"""

    def __init__(self):
        self._message_handler: Optional[Callable[[JSONRPCMessage], Awaitable[None]]] = None
        self._is_connected = False

    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def send_message(self, message: Union[JSONRPCRequest, JSONRPCNotification]) -> None:
        """发送消息"""
        pass

    @abstractmethod
    async def receive_message(self) -> JSONRPCMessage:
        """接收消息"""
        pass

    def set_message_handler(
        self,
        handler: Callable[[JSONRPCMessage], Awaitable[None]]
    ) -> None:
        """设置消息处理器"""
        self._message_handler = handler

    async def start_listening(self) -> None:
        """开始监听消息"""
        while self._is_connected:
            try:
                message = await self.receive_message()
                if self._message_handler:
                    await self._message_handler(message)
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                if not self._is_connected:
                    break

    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected


class MCPStdioTransport(MCPTransport):
    """stdio传输实现（通过子进程通信）"""

    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None
    ):
        super().__init__()
        self.command = command
        self.args = args
        self.env = env or {}
        self.cwd = cwd
        self.process: Optional[asyncio.subprocess.Process] = None
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """启动子进程并建立连接"""
        import os
        import traceback
        try:
            print(f"[DEBUG] Starting connect() for command: {self.command}")
            logger.info(f"[DEBUG] Starting connect() for command: {self.command}")

            # Windows 上统一使用 subprocess.Popen
            if os.name == 'nt':
                # 检查当前事件循环类型
                import asyncio
                current_loop = asyncio.get_running_loop()
                loop_type = type(current_loop).__name__
                print(f"[DEBUG] Current event loop type: {loop_type}")
                print(f"[DEBUG] Event loop policy: {type(asyncio.get_event_loop_policy()).__name__}")

                # Windows 上始终使用 subprocess.Popen
                logger.info("Using subprocess.Popen on Windows for subprocess support")
                print("[DEBUG] Using subprocess.Popen approach...")

                # 对于 Windows，使用 subprocess.Popen + asyncio 的方式
                import subprocess

                # 准备环境变量
                process_env = None
                if self.env:
                    process_env = os.environ.copy()
                    process_env.update(self.env)

                # 查找命令
                command_path = self.command
                if os.path.isfile(self.command):
                    command_path = self.command
                else:
                    import shutil
                    resolved = shutil.which(self.command)
                    if not resolved:
                        raise FileNotFoundError(f"Command not found: {self.command}")
                    command_path = resolved

                print(f"[DEBUG] Found command at: {command_path}")
                logger.info(f"Found command at: {command_path}")

                # 使用 subprocess.Popen 启动进程
                full_cmd = [command_path] + self.args
                logger.info(f"Starting MCP server with Popen: {' '.join(full_cmd)}")

                self.process = subprocess.Popen(
                    full_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=process_env,
                    cwd=self.cwd,
                    bufsize=0,  # 无缓冲
                    text=False  # 使用字节模式
                )

                # 等待一小段时间确保进程启动
                await asyncio.sleep(0.1)

                # 检查进程是否还在运行
                if self.process.poll() is not None:
                    stderr_output = self.process.stderr.read().decode('utf-8', errors='ignore')
                    error_msg = stderr_output.strip() if stderr_output else f"Process exited with code {self.process.returncode}"
                    logger.error(f"Process exited immediately: {error_msg}")
                    raise MCPTransportError(f"Process exited: {error_msg}")

                self._is_connected = True
                print(f"[DEBUG] MCP server process started successfully")
                logger.info("MCP server process started successfully")

                # 启动后台监听任务
                self._read_task = asyncio.create_task(self._read_messages())
                logger.info("Started background message listener")
                return

            # 非 Windows 系统 - 使用 asyncio subprocess
            # 准备环境变量
            process_env = None
            if self.env:
                process_env = os.environ.copy()
                process_env.update(self.env)

            # 检查命令是否存在并解析完整路径
            command_path = self.command
            if os.name == 'nt':  # Windows系统
                # 如果是完整路径且文件存在，直接使用
                if os.path.isfile(self.command):
                    command_path = self.command
                else:
                    # 尝试在PATH中查找命令
                    import shutil
                    resolved = shutil.which(self.command)
                    if not resolved:
                        raise FileNotFoundError(f"Command not found: {self.command}")
                    command_path = resolved

            print(f"[DEBUG] Found command at: {command_path}")
            logger.info(f"Found command at: {command_path}")

            # 启动子进程
            logger.info(f"Starting MCP server process: {command_path} {' '.join(self.args)}")
            logger.debug(f"Working directory: {self.cwd or 'current'}")
            logger.debug(f"Environment variables: {list(self.env.keys()) if self.env else 'none'}")

            self.process = await asyncio.create_subprocess_exec(
                command_path,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=self.cwd
            )

            print(f"[DEBUG] Process created: {self.process}")
            logger.info(f"Process created with PID: {self.process.pid}")

            # 等待一小段时间确保进程启动
            await asyncio.sleep(0.1)

            # 检查进程是否还在运行
            if self.process.returncode is not None:
                # 进程已经退出，读取stderr
                stderr_output = await self.process.stderr.read()
                error_msg = stderr_output.decode('utf-8', errors='ignore').strip()
                logger.error(f"Process exited immediately with code {self.process.returncode}")
                logger.error(f"stderr: {error_msg}")
                raise MCPTransportError(
                    f"Process exited with code {self.process.returncode}: {error_msg}"
                )

            self._is_connected = True
            print(f"[DEBUG] MCP server process started successfully")
            logger.info("MCP server process started successfully")

            # 启动后台监听任务来接收服务器的消息
            self._read_task = asyncio.create_task(self._read_messages())
            logger.info("Started background message listener")

        except FileNotFoundError as e:
            print(f"[DEBUG] FileNotFoundError: {e}")
            logger.error(f"Command not found: {e}")
            raise MCPTransportError(f"Command not found: {self.command}. Please ensure it is installed and in PATH.")
        except Exception as e:
            print(f"[DEBUG] Exception in connect(): {type(e).__name__}: {e}")
            print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
            logger.error(f"Failed to start MCP server process: {type(e).__name__}: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise MCPTransportError(f"Failed to start process: {e}")

    async def disconnect(self) -> None:
        """停止子进程"""
        self._is_connected = False

        if self.process:
            try:
                # 发送EOF信号
                if self.process.stdin:
                    self.process.stdin.close()

                # 等待进程结束（最多5秒）
                import subprocess
                if isinstance(self.process, subprocess.Popen):
                    # subprocess.Popen - 使用 executor 包装同步 wait()
                    loop = asyncio.get_event_loop()
                    try:
                        await asyncio.wait_for(
                            loop.run_in_executor(None, self.process.wait),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        # 超时则强制杀死
                        self.process.kill()
                        loop.run_in_executor(None, self.process.wait)
                else:
                    # asyncio subprocess - 直接使用 await
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        # 超时则强制杀死
                        self.process.kill()
                        await self.process.wait()

                logger.info("MCP server process stopped")
            except Exception as e:
                logger.error(f"Error stopping process: {e}")
            finally:
                self.process = None

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

    async def send_message(self, message: Union[JSONRPCRequest, JSONRPCNotification]) -> None:
        """发送消息到子进程"""
        if not self.process or not self.process.stdin:
            raise MCPTransportError("Process not connected")

        try:
            # 编码消息
            data = JSONRPCCodec.encode(message)

            # 添加换行符（MCP协议使用行分隔的JSON）
            message_data = (data + "\n").encode("utf-8")

            # 写入stdin
            self.process.stdin.write(message_data)

            # 对于 subprocess.Popen，需要 flush 但不需要 drain
            import subprocess
            if isinstance(self.process, subprocess.Popen):
                self.process.stdin.flush()
            else:
                await self.process.stdin.drain()

            logger.debug(f"Sent message: {message.method}")

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self._is_connected = False
            raise MCPTransportError(f"Failed to send message: {e}")

    async def receive_message(self) -> JSONRPCMessage:
        """从子进程接收消息"""
        if not self.process or not self.process.stdout:
            raise MCPTransportError("Process not connected")

        try:
            # 检查是否是同步 subprocess.Popen 对象
            import subprocess
            if isinstance(self.process, subprocess.Popen):
                # 使用 asyncio 来包装同步读取
                loop = asyncio.get_event_loop()
                line = await loop.run_in_executor(None, self.process.stdout.readline)

                if not line:
                    # EOF reached
                    self._is_connected = False
                    raise MCPTransportError("Process closed connection")

                # 解码并解析
                data = line.decode("utf-8").strip()
                message = JSONRPCCodec.decode(data)

                logger.debug(f"Received message: {type(message).__name__}")
                return message
            else:
                # asyncio subprocess - 使用 await
                # 读取一行（以\n分隔的JSON）
                line = await self.process.stdout.readline()

                if not line:
                    # EOF reached
                    self._is_connected = False
                    raise MCPTransportError("Process closed connection")

                # 解码并解析
                data = line.decode("utf-8").strip()
                message = JSONRPCCodec.decode(data)

                logger.debug(f"Received message: {type(message).__name__}")

                return message

        except MCPTransportError:
            raise
        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            self._is_connected = False
            raise MCPTransportError(f"Failed to receive message: {e}")

    async def read_stderr(self) -> str:
        """读取stderr输出（用于调试）"""
        if not self.process or not self.process.stderr:
            return ""

        try:
            import subprocess
            if isinstance(self.process, subprocess.Popen):
                # Windows subprocess.Popen - 使用 executor 包装同步读取
                loop = asyncio.get_event_loop()
                line = await loop.run_in_executor(None, self.process.stderr.readline)
            else:
                # asyncio subprocess - 直接使用 await
                line = await self.process.stderr.readline()

            if line:
                return line.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            logger.error(f"Error reading stderr: {e}")

        return ""

    async def _read_messages(self) -> None:
        """后台任务：持续读取服务器的消息并传递给消息处理器"""
        while self._is_connected:
            try:
                message = await self.receive_message()
                logger.debug(f"Received message from server: {type(message).__name__}")

                # 调用消息处理器
                if self._message_handler:
                    await self._message_handler(message)
            except asyncio.CancelledError:
                logger.info("Message listener cancelled")
                break
            except MCPTransportError as e:
                if self._is_connected:
                    logger.error(f"Error reading message: {e}")
                    self._is_connected = False
                break
            except Exception as e:
                logger.error(f"Unexpected error in message listener: {e}")
                if self._is_connected:
                    self._is_connected = False
                break


class MCPHttpTransport(MCPTransport):
    """HTTP传输实现（使用HTTP/WebSocket）"""

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ):
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self._client = None  # httpx.AsyncClient
        self._request_id = 0

    async def connect(self) -> None:
        """建立HTTP连接"""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=60.0  # 增加到 60 秒，与 MCPClient 保持一致
            )
            self._is_connected = True
            logger.info(f"HTTP transport connected to {self.url}")
        except ImportError:
            raise MCPTransportError("httpx is required for HTTP transport")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise MCPTransportError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """断开HTTP连接"""
        self._is_connected = False

        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("HTTP transport disconnected")

    async def send_message(self, message: Union[JSONRPCRequest, JSONRPCNotification]) -> None:
        """发送HTTP POST请求（同步等待响应）"""
        if not self._client:
            raise MCPTransportError("Not connected")

        try:
            # 编码消息
            data = JSONRPCCodec.encode(message)

            # 发送POST请求
            response = await self._client.post(
                self.url,
                content=data.encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            # 解析响应
            response_data = response.json()
            response_message = JSONRPCCodec.decode(json.dumps(response_data))

            # 将响应存储到临时属性（用于同步获取）
            self._last_response = response_message

            logger.debug(f"Sent HTTP request: {message.method}")

        except Exception as e:
            logger.error(f"Failed to send HTTP request: {e}")
            self._is_connected = False
            raise MCPTransportError(f"Failed to send HTTP request: {e}")

    async def receive_message(self) -> JSONRPCMessage:
        """获取上次请求的响应"""
        if not hasattr(self, "_last_response"):
            raise MCPTransportError("No response available")

        response = self._last_response
        delattr(self, "_last_response")
        return response


class MCPWebSocketTransport(MCPTransport):
    """WebSocket传输实现（双向通信）"""

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ):
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self._websocket = None
        self._message_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self) -> None:
        """建立WebSocket连接"""
        try:
            import websockets
            self._websocket = await websockets.connect(
                self.url,
                extra_headers=self.headers
            )
            self._is_connected = True
            logger.info(f"WebSocket connected to {self.url}")
        except ImportError:
            raise MCPTransportError("websockets is required for WebSocket transport")
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            raise MCPTransportError(f"Failed to connect WebSocket: {e}")

    async def disconnect(self) -> None:
        """断开WebSocket连接"""
        self._is_connected = False

        if self._websocket:
            await self._websocket.close()
            self._websocket = None
            logger.info("WebSocket disconnected")

    async def send_message(self, message: Union[JSONRPCRequest, JSONRPCNotification]) -> None:
        """发送WebSocket消息"""
        if not self._websocket:
            raise MCPTransportError("WebSocket not connected")

        try:
            data = JSONRPCCodec.encode(message)
            await self._websocket.send(data)
            logger.debug(f"Sent WebSocket message: {message.method}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            self._is_connected = False
            raise MCPTransportError(f"Failed to send WebSocket message: {e}")

    async def receive_message(self) -> JSONRPCMessage:
        """接收WebSocket消息"""
        if not self._websocket:
            raise MCPTransportError("WebSocket not connected")

        try:
            data = await self._websocket.recv()
            message = JSONRPCCodec.decode(data)
            logger.debug(f"Received WebSocket message: {type(message).__name__}")
            return message
        except Exception as e:
            logger.error(f"Failed to receive WebSocket message: {e}")
            self._is_connected = False
            raise MCPTransportError(f"Failed to receive WebSocket message: {e}")


def create_transport(
    transport_type: str,
    config: Dict[str, Any]
) -> MCPTransport:
    """
    工厂函数：根据配置创建传输层

    Args:
        transport_type: 传输类型 ("stdio" 或 "http" 或 "websocket")
        config: 传输配置

    Returns:
        MCPTransport实例

    Examples:
        >>> # stdio传输
        >>> transport = create_transport("stdio", {
        ...     "command": "python",
        ...     "args": ["-m", "mcp_server"],
        ...     "env": {"API_KEY": "xxx"}
        ... })

        >>> # HTTP传输
        >>> transport = create_transport("http", {
        ...     "url": "http://localhost:3000/mcp",
        ...     "headers": {"Authorization": "Bearer xxx"}
        ... })
    """
    transport_type = transport_type.lower()
    logger.info(f"Creating transport: type={transport_type}, config={config}")

    if transport_type == "stdio":
        transport = MCPStdioTransport(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env"),
            cwd=config.get("cwd")
        )
        logger.info(f"Created MCPStdioTransport")
        return transport
    elif transport_type == "http":
        transport = MCPHttpTransport(
            url=config["url"],
            headers=config.get("headers")
        )
        logger.info(f"Created MCPHttpTransport")
        return transport
    elif transport_type == "websocket":
        transport = MCPWebSocketTransport(
            url=config["url"],
            headers=config.get("headers")
        )
        logger.info(f"Created MCPWebSocketTransport")
        return transport
    else:
        logger.error(f"Unsupported transport type: {transport_type}")
        raise ValueError(f"Unsupported transport type: {transport_type}")

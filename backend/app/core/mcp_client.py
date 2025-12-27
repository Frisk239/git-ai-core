"""
MCP客户端核心实现
提供完整的MCP协议客户端功能
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from app.core.mcp_protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCNotification,
    JSONRPCCodec,
    MCPProtocolUtils,
    JSONRPCError
)
from app.core.mcp_transport import (
    MCPTransport,
    MCPTransportError,
    create_transport
)


logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPResource:
    """MCP资源定义"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class MCPPrompt:
    """MCP提示词定义"""
    name: str
    description: str
    arguments: Optional[List[Dict[str, Any]]] = None


@dataclass
class MCPServerInfo:
    """MCP服务器信息"""
    name: str
    version: str
    protocol_version: str
    capabilities: Dict[str, Any]


class MCPClientError(Exception):
    """MCP客户端错误"""
    pass


class MCPClient:
    """MCP客户端基类"""

    def __init__(
        self,
        server_name: str,
        transport: MCPTransport,
        timeout: float = 30.0
    ):
        self.server_name = server_name
        self.transport = transport
        self.timeout = timeout

        # 状态
        self._is_initialized = False
        self._server_info: Optional[MCPServerInfo] = None

        # 请求ID映射（用于异步响应）
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_lock = asyncio.Lock()

        # 设置传输层的消息处理器
        self.transport.set_message_handler(self._handle_message)

        # 缓存的工具、资源、提示词
        self._tools_cache: Optional[List[MCPTool]] = None
        self._resources_cache: Optional[List[MCPResource]] = None
        self._prompts_cache: Optional[List[MCPPrompt]] = None

    async def connect(self) -> None:
        """连接到MCP服务器"""
        try:
            await self.transport.connect()
            logger.info(f"Connected to MCP server: {self.server_name}")
        except Exception as e:
            logger.error(f"Failed to connect to {self.server_name}: {e}")
            raise MCPClientError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """断开连接"""
        self._is_initialized = False
        await self.transport.disconnect()
        logger.info(f"Disconnected from {self.server_name}")

    async def initialize(self) -> MCPServerInfo:
        """初始化MCP服务器连接"""
        if self._is_initialized:
            return self._server_info

        try:
            logger.info(f"[{self.server_name}] Starting initialization...")

            # 创建初始化请求
            request = MCPProtocolUtils.create_initialize_request(
                capabilities={
                    "roots": {"listChanged": True},
                    "sampling": {}
                }
            )

            logger.info(f"[{self.server_name}] Sending initialize request (id={request.id})...")

            # 发送请求并获取响应
            response = await self._send_request(request)

            logger.info(f"[{self.server_name}] Received initialize response")

            if not response.result:
                raise MCPClientError("Initialize response missing result")

            result = response.result
            self._server_info = MCPServerInfo(
                name=result.get("serverInfo", {}).get("name", "unknown"),
                version=result.get("serverInfo", {}).get("version", "unknown"),
                protocol_version=result.get("protocolVersion", "unknown"),
                capabilities=result.get("capabilities", {})
            )

            self._is_initialized = True

            # 发送initialized通知
            initialized_notification = JSONRPCNotification(
                method="notifications/initialized"
            )
            await self._send_notification(initialized_notification)

            logger.info(f"Initialized MCP server: {self._server_info.name} v{self._server_info.version}")
            return self._server_info

        except Exception as e:
            logger.error(f"Failed to initialize {self.server_name}: {e}")
            raise MCPClientError(f"Initialization failed: {e}")

    async def list_tools(self, use_cache: bool = True) -> List[MCPTool]:
        """列出服务器提供的所有工具"""
        if use_cache and self._tools_cache is not None:
            return self._tools_cache

        try:
            request = MCPProtocolUtils.create_tools_list_request()
            response = await self._send_request(request)

            if not response.result:
                raise MCPClientError("Tools list response missing result")

            tools_data = response.result.get("tools", [])
            self._tools_cache = [
                MCPTool(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {})
                )
                for tool in tools_data
            ]

            logger.info(f"Listed {len(self._tools_cache)} tools from {self.server_name}")
            return self._tools_cache

        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            raise MCPClientError(f"Failed to list tools: {e}")

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """调用工具"""
        try:
            request = MCPProtocolUtils.create_tools_call_request(name, arguments)
            response = await self._send_request(request)

            if response.error:
                raise MCPClientError(
                    f"Tool call error: {response.error.get('message', 'Unknown error')}"
                )

            return response.result

        except MCPClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to call tool {name}: {e}")
            raise MCPClientError(f"Failed to call tool {name}: {e}")

    async def list_resources(self, use_cache: bool = True) -> List[MCPResource]:
        """列出服务器提供的所有资源"""
        if use_cache and self._resources_cache is not None:
            return self._resources_cache

        try:
            request = MCPProtocolUtils.create_resources_list_request()
            response = await self._send_request(request)

            if not response.result:
                raise MCPClientError("Resources list response missing result")

            resources_data = response.result.get("resources", [])
            self._resources_cache = [
                MCPResource(
                    uri=resource["uri"],
                    name=resource.get("name", ""),
                    description=resource.get("description"),
                    mime_type=resource.get("mimeType")
                )
                for resource in resources_data
            ]

            logger.info(f"Listed {len(self._resources_cache)} resources from {self.server_name}")
            return self._resources_cache

        except Exception as e:
            logger.error(f"Failed to list resources: {e}")
            raise MCPClientError(f"Failed to list resources: {e}")

    async def read_resource(self, uri: str) -> Any:
        """读取资源内容"""
        try:
            request = MCPProtocolUtils.create_resources_read_request(uri)
            response = await self._send_request(request)

            if response.error:
                raise MCPClientError(
                    f"Resource read error: {response.error.get('message', 'Unknown error')}"
                )

            contents = response.result.get("contents", [])
            if not contents:
                return None

            # 返回第一个内容项
            return contents[0]

        except MCPClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to read resource {uri}: {e}")
            raise MCPClientError(f"Failed to read resource {uri}: {e}")

    async def list_prompts(self, use_cache: bool = True) -> List[MCPPrompt]:
        """列出服务器提供的所有提示词"""
        if use_cache and self._prompts_cache is not None:
            return self._prompts_cache

        try:
            request = MCPProtocolUtils.create_prompts_list_request()
            response = await self._send_request(request)

            if not response.result:
                raise MCPClientError("Prompts list response missing result")

            prompts_data = response.result.get("prompts", [])
            self._prompts_cache = [
                MCPPrompt(
                    name=prompt["name"],
                    description=prompt.get("description", ""),
                    arguments=prompt.get("arguments")
                )
                for prompt in prompts_data
            ]

            logger.info(f"Listed {len(self._prompts_cache)} prompts from {self.server_name}")
            return self._prompts_cache

        except Exception as e:
            logger.error(f"Failed to list prompts: {e}")
            raise MCPClientError(f"Failed to list prompts: {e}")

    async def get_prompt(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Any:
        """获取提示词内容"""
        try:
            request = MCPProtocolUtils.create_prompts_get_request(name, arguments)
            response = await self._send_request(request)

            if response.error:
                raise MCPClientError(
                    f"Prompt get error: {response.error.get('message', 'Unknown error')}"
                )

            return response.result

        except MCPClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to get prompt {name}: {e}")
            raise MCPClientError(f"Failed to get prompt {name}: {e}")

    def invalidate_cache(self) -> None:
        """清除缓存"""
        self._tools_cache = None
        self._resources_cache = None
        self._prompts_cache = None

    async def _send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """发送请求并等待响应"""
        async with self._request_lock:
            # 创建Future等待响应
            future: asyncio.Future[JSONRPCResponse] = asyncio.Future()
            self._pending_requests[request.id] = future

            try:
                # 发送请求
                await self.transport.send_message(request)

                # 等待响应
                response = await asyncio.wait_for(future, timeout=self.timeout)
                return response

            except asyncio.TimeoutError:
                logger.error(f"Request timeout: {request.method}")
                raise MCPClientError(f"Request timeout: {request.method}")
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise
            finally:
                # 清理pending request
                self._pending_requests.pop(request.id, None)

    async def _send_notification(self, notification: JSONRPCNotification) -> None:
        """发送通知（不需要响应）"""
        try:
            await self.transport.send_message(notification)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def _handle_message(self, message: JSONRPCResponse) -> None:
        """处理接收到的消息"""
        try:
            if isinstance(message, JSONRPCResponse):
                # 处理响应
                future = self._pending_requests.get(message.id)
                if future:
                    future.set_result(message)
                else:
                    logger.warning(f"Received response for unknown request: {message.id}")
            else:
                logger.warning(f"Received unexpected message type: {type(message)}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def is_connected(self) -> bool:
        """是否已连接"""
        return self.transport.is_connected()

    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._is_initialized

    def get_server_info(self) -> Optional[MCPServerInfo]:
        """获取服务器信息"""
        return self._server_info


class MCPClientFactory:
    """MCP客户端工厂类"""

    @staticmethod
    async def create_client(
        server_name: str,
        transport_type: str,
        transport_config: Dict[str, Any],
        auto_initialize: bool = True
    ) -> MCPClient:
        """
        创建并初始化MCP客户端

        Args:
            server_name: 服务器名称
            transport_type: 传输类型 ("stdio", "http", "websocket")
            transport_config: 传输配置
            auto_initialize: 是否自动初始化

        Returns:
            已连接的MCP客户端实例
        """
        try:
            logger.info(f"Creating MCP client: server={server_name}, transport={transport_type}")

            # 创建传输层
            transport = create_transport(transport_type, transport_config)
            logger.info("Transport created successfully")

            # 创建客户端
            client = MCPClient(server_name, transport)
            logger.info("MCPClient instance created")

            # 连接
            logger.info("Connecting to MCP server...")
            await client.connect()
            logger.info("Connected successfully")

            # 初始化
            if auto_initialize:
                logger.info("Initializing MCP server...")
                await client.initialize()
                logger.info("Initialized successfully")

            return client

        except Exception as e:
            logger.error(f"Failed to create MCP client: {type(e).__name__}: {e}")
            raise MCPClientError(f"Failed to create client: {e}")

    @staticmethod
    async def create_client_from_config(
        server_name: str,
        config: Dict[str, Any],
        auto_initialize: bool = True
    ) -> MCPClient:
        """
        从配置字典创建MCP客户端

        Args:
            server_name: 服务器名称
            config: 服务器配置（包含command, args, env, transportType等）
            auto_initialize: 是否自动初始化

        Returns:
            已连接的MCP客户端实例
        """
        transport_type = config.get("transportType", "stdio")

        transport_config = {
            "command": config.get("command", ""),
            "args": config.get("args", []),
            "env": config.get("env"),
            "url": config.get("url"),
            "headers": config.get("headers")
        }

        return await MCPClientFactory.create_client(
            server_name,
            transport_type,
            transport_config,
            auto_initialize
        )

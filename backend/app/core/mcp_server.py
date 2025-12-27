"""
MCP服务器管理器
负责管理MCP服务器的生命周期、配置和连接
"""

import json
import os
import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.core.config import settings
from app.core.mcp_client import (
    MCPClient,
    MCPClientFactory,
    MCPClientError
)


logger = logging.getLogger(__name__)


class MCPServerManager:
    """MCP服务器管理器"""

    def __init__(self):
        # 服务器配置
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.config_path = settings.mcp_servers_config_path

        # 运行中的客户端实例
        self._active_clients: Dict[str, MCPClient] = {}

        # 加载配置
        self._load_servers()

    def _load_servers(self):
        """加载MCP服务器配置"""
        if not os.path.exists(self.config_path):
            self.servers = {}
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.servers = json.load(f)
            logger.info(f"Loaded {len(self.servers)} MCP server configurations")
        except Exception as e:
            logger.error(f"Error loading MCP servers: {e}")
            self.servers = {}

    def _save_servers(self):
        """保存MCP服务器配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
            logger.debug("MCP server configurations saved")
        except Exception as e:
            logger.error(f"Error saving MCP servers: {e}")

    def add_server(self, name: str, config: Dict[str, Any]) -> bool:
        """添加MCP服务器配置"""
        try:
            # 确保配置包含必要的字段
            config.setdefault('enabled', True)
            config.setdefault('transportType', 'stdio')
            config.setdefault('args', [])
            config.setdefault('env', {})
            config.setdefault('headers', {})
            config.setdefault('description', '')

            self.servers[name] = config
            self._save_servers()
            logger.info(f"Added MCP server: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add server {name}: {e}")
            return False

    def remove_server(self, name: str) -> bool:
        """移除MCP服务器配置"""
        try:
            # 如果服务器正在运行，先停止
            if name in self._active_clients:
                asyncio.create_task(self.stop_server(name))

            if name in self.servers:
                del self.servers[name]
                self._save_servers()
                logger.info(f"Removed MCP server: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove server {name}: {e}")
            return False

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """获取服务器配置"""
        return self.servers.get(name)

    def list_servers(self) -> Dict[str, Any]:
        """列出所有服务器配置"""
        return self.servers.copy()

    def update_server(self, name: str, config: Dict[str, Any]) -> bool:
        """更新服务器配置"""
        try:
            if name in self.servers:
                # 确保配置包含必要的字段
                config.setdefault('enabled', True)
                config.setdefault('transportType', 'stdio')
                config.setdefault('args', [])
                config.setdefault('env', {})
                config.setdefault('headers', {})
                config.setdefault('description', '')

                self.servers[name] = config
                self._save_servers()
                logger.info(f"Updated MCP server: {name}")

                # 如果服务器正在运行且配置改变，需要重启
                if name in self._active_clients:
                    asyncio.create_task(self.restart_server(name))

                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update server {name}: {e}")
            return False

    def get_builtin_servers(self) -> List[Dict[str, Any]]:
        """获取内置MCP服务器配置"""
        return [
            {
                "name": "comment-server",
                "command": "python",
                "args": ["-m", "app.core.comment_mcp_server"],
                "env": {},
                "description": "内置注释生成MCP服务器，提供代码注释生成功能",
                "enabled": True,
                "transportType": "stdio",
                "url": "",
                "headers": {},
                "builtin": True
            },
            {
                "name": "project-file-server",
                "command": "python",
                "args": ["-m", "app.core.project_mcp_server"],
                "env": {},
                "description": "内置项目文件读取MCP服务器，提供文件读取和目录列表功能",
                "enabled": True,
                "transportType": "stdio",
                "url": "",
                "headers": {},
                "builtin": True
            }
        ]

    async def start_server(self, name: str) -> bool:
        """启动MCP服务器"""
        try:
            # 检查是否已经在运行
            if name in self._active_clients:
                logger.warning(f"Server {name} is already running")
                return True

            # 获取服务器配置
            config = self.get_server(name)
            if not config:
                logger.error(f"Server configuration not found: {name}")
                return False

            # 检查是否启用
            if not config.get('enabled', True):
                logger.warning(f"Server {name} is disabled")
                return False

            # 创建并连接客户端
            logger.info(f"Starting MCP server: {name}")
            client = await MCPClientFactory.create_client_from_config(
                name,
                config,
                auto_initialize=True
            )

            # 保存客户端实例
            self._active_clients[name] = client

            logger.info(f"MCP server started successfully: {name}")
            return True

        except MCPClientError as e:
            logger.error(f"Failed to start server {name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error starting server {name}: {e}")
            return False

    async def stop_server(self, name: str) -> bool:
        """停止MCP服务器"""
        try:
            client = self._active_clients.get(name)
            if not client:
                logger.warning(f"Server {name} is not running")
                return True

            # 断开连接
            await client.disconnect()

            # 移除客户端实例
            del self._active_clients[name]

            logger.info(f"Stopped MCP server: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop server {name}: {e}")
            return False

    async def restart_server(self, name: str) -> bool:
        """重启MCP服务器"""
        try:
            # 先停止
            await self.stop_server(name)
            # 等待一小段时间
            await asyncio.sleep(0.5)
            # 再启动
            return await self.start_server(name)
        except Exception as e:
            logger.error(f"Failed to restart server {name}: {e}")
            return False

    async def get_server_status(self, name: str) -> Dict[str, Any]:
        """获取服务器状态"""
        try:
            client = self._active_clients.get(name)
            config = self.get_server(name)

            if not config:
                return {
                    "name": name,
                    "status": "not_configured",
                    "connected": False,
                    "initialized": False
                }

            is_connected = client is not None and client.is_connected()
            is_initialized = client is not None and client.is_initialized()

            status = "running" if is_connected else "stopped"
            if config.get('builtin'):
                status = "builtin"

            server_info = None
            if client:
                server_info = client.get_server_info()

            return {
                "name": name,
                "status": status,
                "connected": is_connected,
                "initialized": is_initialized,
                "server_info": {
                    "name": server_info.name if server_info else None,
                    "version": server_info.version if server_info else None,
                    "protocol_version": server_info.protocol_version if server_info else None,
                } if server_info else None,
                "config": {
                    "description": config.get("description"),
                    "transportType": config.get("transportType"),
                    "enabled": config.get("enabled", True),
                    "builtin": config.get("builtin", False)
                }
            }

        except Exception as e:
            logger.error(f"Failed to get server status {name}: {e}")
            return {
                "name": name,
                "status": "error",
                "connected": False,
                "initialized": False,
                "error": str(e)
            }

    async def test_server_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """测试MCP服务器连接"""
        client = None
        try:
            # 创建临时客户端
            transport_type = config.get("transportType", "stdio")
            transport_config = {
                "command": config.get("command", ""),
                "args": config.get("args", []),
                "env": config.get("env"),
                "url": config.get("url"),
                "headers": config.get("headers")
            }

            client = await MCPClientFactory.create_client(
                "test",
                transport_type,
                transport_config,
                auto_initialize=True
            )

            # 获取服务器信息
            server_info = client.get_server_info()

            # 列出工具
            tools = await client.list_tools(use_cache=False)

            # 列出资源
            resources = await client.list_resources(use_cache=False)

            # 列出提示词
            prompts = await client.list_prompts(use_cache=False)

            return {
                "success": True,
                "message": "连接测试成功",
                "server_info": {
                    "name": server_info.name,
                    "version": server_info.version,
                    "protocol_version": server_info.protocol_version,
                },
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema
                    }
                    for tool in tools
                ],
                "resources": [
                    {
                        "uri": resource.uri,
                        "name": resource.name,
                        "description": resource.description
                    }
                    for resource in resources
                ],
                "prompts": [
                    {
                        "name": prompt.name,
                        "description": prompt.description,
                        "arguments": prompt.arguments
                    }
                    for prompt in prompts
                ]
            }

        except MCPClientError as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "success": False,
                "message": f"连接测试失败: {str(e)}",
                "tools": [],
                "resources": [],
                "prompts": []
            }
        except Exception as e:
            logger.error(f"Unexpected error during connection test: {e}")
            return {
                "success": False,
                "message": f"测试失败: {str(e)}",
                "tools": [],
                "resources": [],
                "prompts": []
            }
        finally:
            # 清理测试客户端
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def execute_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行MCP工具"""
        try:
            # 获取或启动客户端
            client = self._active_clients.get(server_name)
            if not client:
                # 尝试启动服务器
                await self.start_server(server_name)
                client = self._active_clients.get(server_name)

                if not client:
                    raise MCPClientError(f"Failed to start server: {server_name}")

            # 调用工具
            result = await client.call_tool(tool_name, arguments)

            return {
                "success": True,
                "result": result
            }

        except MCPClientError as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error executing tool: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """列出服务器的所有工具"""
        try:
            client = self._active_clients.get(server_name)
            if not client:
                raise MCPClientError(f"Server not running: {server_name}")

            tools = await client.list_tools(use_cache=True)

            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema
                }
                for tool in tools
            ]

        except MCPClientError as e:
            logger.error(f"Failed to list tools: {e}")
            return []

    async def list_resources(self, server_name: str) -> List[Dict[str, Any]]:
        """列出服务器的所有资源"""
        try:
            client = self._active_clients.get(server_name)
            if not client:
                raise MCPClientError(f"Server not running: {server_name}")

            resources = await client.list_resources(use_cache=True)

            return [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mime_type": resource.mime_type
                }
                for resource in resources
            ]

        except MCPClientError as e:
            logger.error(f"Failed to list resources: {e}")
            return []

    async def read_resource(
        self,
        server_name: str,
        uri: str
    ) -> Dict[str, Any]:
        """读取资源内容"""
        try:
            client = self._active_clients.get(server_name)
            if not client:
                raise MCPClientError(f"Server not running: {server_name}")

            content = await client.read_resource(uri)

            return {
                "success": True,
                "content": content
            }

        except MCPClientError as e:
            logger.error(f"Failed to read resource: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def list_prompts(self, server_name: str) -> List[Dict[str, Any]]:
        """列出服务器的所有提示词"""
        try:
            client = self._active_clients.get(server_name)
            if not client:
                raise MCPClientError(f"Server not running: {server_name}")

            prompts = await client.list_prompts(use_cache=True)

            return [
                {
                    "name": prompt.name,
                    "description": prompt.description,
                    "arguments": prompt.arguments
                }
                for prompt in prompts
            ]

        except MCPClientError as e:
            logger.error(f"Failed to list prompts: {e}")
            return []

    async def get_prompt(
        self,
        server_name: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """获取提示词内容"""
        try:
            client = self._active_clients.get(server_name)
            if not client:
                raise MCPClientError(f"Server not running: {server_name}")

            result = await client.get_prompt(prompt_name, arguments)

            return {
                "success": True,
                "result": result
            }

        except MCPClientError as e:
            logger.error(f"Failed to get prompt: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_all_servers_status(self) -> Dict[str, Any]:
        """获取所有服务器的状态"""
        statuses = {}
        for name in self.servers.keys():
            statuses[name] = await self.get_server_status(name)
        return statuses

    async def stop_all_servers(self) -> None:
        """停止所有运行中的服务器"""
        tasks = [
            self.stop_server(name)
            for name in list(self._active_clients.keys())
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All MCP servers stopped")

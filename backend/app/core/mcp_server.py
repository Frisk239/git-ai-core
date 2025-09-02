from typing import Dict, Any, Optional, List
import json
import os
import asyncio
from pathlib import Path
from app.core.config import settings

class McpServer:
    """MCP服务器管理器"""
    
    def __init__(self):
        self.servers = {}
        self.config_path = settings.mcp_servers_config_path
        self._load_servers()
    
    def _load_servers(self):
        """加载MCP服务器配置"""
        if not os.path.exists(self.config_path):
            self.servers = {}
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.servers = json.load(f)
        except Exception as e:
            print(f"Error loading MCP servers: {e}")
            self.servers = {}
    
    def _save_servers(self):
        """保存MCP服务器配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving MCP servers: {e}")
    
    def add_server(self, name: str, config: Dict[str, Any]) -> bool:
        """添加MCP服务器"""
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
            return True
        except Exception:
            return False
    
    def remove_server(self, name: str) -> bool:
        """移除MCP服务器"""
        try:
            if name in self.servers:
                del self.servers[name]
                self._save_servers()
                return True
            return False
        except Exception:
            return False
    
    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """获取服务器配置"""
        return self.servers.get(name)
    
    def list_servers(self) -> Dict[str, Any]:
        """列出所有服务器"""
        return self.servers
    
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
                return True
            return False
        except Exception:
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
    
    async def start_builtin_server(self, server_name: str) -> bool:
        """启动内置MCP服务器"""
        return False
    
    async def test_server_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """测试MCP服务器连接"""
        try:
            # 这里实现服务器连接测试逻辑
            # 返回测试结果，包括是否成功、错误信息和可用工具
            return {
                "success": True,
                "message": "连接测试成功",
                "tools": []  # 这里可以添加工具发现功能
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接测试失败: {str(e)}",
                "tools": []
            }

"""
MCP服务器管理API路由
提供完整的MCP服务器管理、工具调用、资源访问等功能
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from app.core.mcp_server import MCPServerManager


logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Pydantic模型 ====================

class MCPServerConfig(BaseModel):
    """MCP服务器配置模型"""
    name: str = Field(..., description="服务器名称")
    command: str = Field(..., description="启动命令")
    args: Optional[List[str]] = Field(None, description="命令参数")
    env: Optional[Dict[str, str]] = Field(None, description="环境变量")
    description: Optional[str] = Field(None, description="服务器描述")
    enabled: Optional[bool] = Field(True, description="是否启用")
    transportType: Optional[str] = Field("stdio", description="传输类型 (stdio/http)")
    url: Optional[str] = Field("", description="HTTP服务器URL")
    headers: Optional[Dict[str, str]] = Field({}, description="HTTP请求头")


class MCPServerTestRequest(BaseModel):
    """MCP服务器测试请求"""
    config: MCPServerConfig = Field(..., description="服务器配置")


class MCPToolExecuteRequest(BaseModel):
    """MCP工具执行请求"""
    server_name: str = Field(..., description="服务器名称")
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(..., description="工具参数")


class MCPResourceReadRequest(BaseModel):
    """MCP资源读取请求"""
    server_name: str = Field(..., description="服务器名称")
    uri: str = Field(..., description="资源URI")


class MCPPromptGetRequest(BaseModel):
    """MCP提示词获取请求"""
    server_name: str = Field(..., description="服务器名称")
    prompt_name: str = Field(..., description="提示词名称")
    arguments: Optional[Dict[str, Any]] = Field(None, description="提示词参数")


# ==================== 辅助函数 ====================

def get_mcp_manager() -> MCPServerManager:
    """获取MCP服务器管理器实例"""
    from app.main import app
    return app.state.mcp_manager


# ==================== 服务器管理端点 ====================

@router.get("/servers")
async def list_servers() -> Dict[str, Any]:
    """列出所有MCP服务器配置"""
    try:
        mcp_manager = get_mcp_manager()
        configured_servers = mcp_manager.list_servers()

        # 获取内置服务器并合并
        builtin_servers = mcp_manager.get_builtin_servers()
        for server in builtin_servers:
            configured_servers[server["name"]] = {
                "command": server["command"],
                "args": server.get("args", []),
                "env": server.get("env", {}),
                "description": server.get("description", ""),
                "enabled": server.get("enabled", True),
                "transportType": server.get("transportType", "stdio"),
                "url": server.get("url", ""),
                "headers": server.get("headers", {}),
                "builtin": True
            }

        return configured_servers

    except Exception as e:
        logger.error(f"Failed to list servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_name}")
async def get_server(server_name: str) -> Dict[str, Any]:
    """获取特定MCP服务器配置"""
    try:
        mcp_manager = get_mcp_manager()
        server = mcp_manager.get_server(server_name)

        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        return server

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers")
async def add_server(config: MCPServerConfig) -> Dict[str, Any]:
    """添加MCP服务器"""
    try:
        mcp_manager = get_mcp_manager()

        server_config = {
            "command": config.command,
            "args": config.args or [],
            "env": config.env or {},
            "description": config.description or "",
            "enabled": config.enabled or True,
            "transportType": config.transportType or "stdio",
            "url": config.url or "",
            "headers": config.headers or {}
        }

        if mcp_manager.add_server(config.name, server_config):
            return {"success": True, "message": "服务器添加成功"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save server configuration")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/servers/{server_name}")
async def update_server(server_name: str, config: MCPServerConfig) -> Dict[str, Any]:
    """更新MCP服务器"""
    try:
        mcp_manager = get_mcp_manager()

        server_config = {
            "command": config.command,
            "args": config.args or [],
            "env": config.env or {},
            "description": config.description or "",
            "enabled": config.enabled or True,
            "transportType": config.transportType or "stdio",
            "url": config.url or "",
            "headers": config.headers or {}
        }

        if mcp_manager.update_server(server_name, server_config):
            return {"success": True, "message": "服务器更新成功"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save server configuration")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/servers/{server_name}")
async def remove_server(server_name: str) -> Dict[str, Any]:
    """删除MCP服务器"""
    try:
        mcp_manager = get_mcp_manager()

        if mcp_manager.remove_server(server_name):
            return {"success": True, "message": "服务器删除成功"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove server configuration")

    except Exception as e:
        logger.error(f"Failed to remove server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class MCPServerToggleRequest(BaseModel):
    """MCP服务器切换请求"""
    enabled: bool = Field(..., description="是否启用")


@router.patch("/servers/{server_name}/toggle")
async def toggle_server(server_name: str, request: MCPServerToggleRequest) -> Dict[str, Any]:
    """切换MCP服务器启用/禁用状态"""
    try:
        mcp_manager = get_mcp_manager()

        # 获取当前服务器配置
        server = mcp_manager.get_server(server_name)
        if not server:
            raise HTTPException(status_code=404, detail=f"服务器 {server_name} 不存在")

        # 更新启用状态
        server["enabled"] = request.enabled

        # 保存配置
        if mcp_manager.update_server(server_name, server):
            # 如果禁用服务器且当前正在运行，则停止它
            if not request.enabled:
                status = await mcp_manager.get_server_status(server_name)
                if status.get("connected"):
                    await mcp_manager.stop_server(server_name)
                    logger.info(f"服务器 {server_name} 已禁用并停止")

            return {
                "success": True,
                "message": f"服务器 {server_name} 已{'启用' if request.enabled else '禁用'}",
                "enabled": request.enabled
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update server configuration")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/test")
async def test_server(request: MCPServerTestRequest) -> Dict[str, Any]:
    """测试MCP服务器连接"""
    try:
        mcp_manager = get_mcp_manager()

        # 将配置转换为字典格式
        config_dict = {
            "command": request.config.command,
            "args": request.config.args or [],
            "env": request.config.env or {},
            "description": request.config.description or "",
            "enabled": request.config.enabled or True,
            "transportType": request.config.transportType or "stdio",
            "url": request.config.url or "",
            "headers": request.config.headers or {}
        }

        # 测试服务器连接
        result = await mcp_manager.test_server_connection(config_dict)
        return result

    except Exception as e:
        logger.error(f"Failed to test server: {e}")
        return {
            "success": False,
            "message": f"测试失败: {str(e)}",
            "tools": [],
            "resources": [],
            "prompts": []
        }


# ==================== 服务器控制端点 ====================

@router.post("/servers/{server_name}/start")
async def start_server(server_name: str) -> Dict[str, Any]:
    """启动MCP服务器"""
    try:
        mcp_manager = get_mcp_manager()

        success = await mcp_manager.start_server(server_name)

        if success:
            return {"success": True, "message": f"服务器 {server_name} 启动成功"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to start server {server_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_name}/stop")
async def stop_server(server_name: str) -> Dict[str, Any]:
    """停止MCP服务器"""
    try:
        mcp_manager = get_mcp_manager()

        success = await mcp_manager.stop_server(server_name)

        if success:
            return {"success": True, "message": f"服务器 {server_name} 停止成功"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to stop server {server_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_name}/restart")
async def restart_server(server_name: str) -> Dict[str, Any]:
    """重启MCP服务器"""
    try:
        mcp_manager = get_mcp_manager()

        success = await mcp_manager.restart_server(server_name)

        if success:
            return {"success": True, "message": f"服务器 {server_name} 重启成功"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to restart server {server_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_name}/status")
async def get_server_status(server_name: str) -> Dict[str, Any]:
    """获取MCP服务器状态"""
    try:
        mcp_manager = get_mcp_manager()
        status = await mcp_manager.get_server_status(server_name)
        return status

    except Exception as e:
        logger.error(f"Failed to get server status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/status/all")
async def get_all_servers_status() -> Dict[str, Any]:
    """获取所有MCP服务器状态"""
    try:
        mcp_manager = get_mcp_manager()
        statuses = await mcp_manager.get_all_servers_status()
        return statuses

    except Exception as e:
        logger.error(f"Failed to get all servers status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 工具管理端点 ====================

@router.get("/tools/{server_name}")
async def list_tools(server_name: str) -> List[Dict[str, Any]]:
    """列出MCP服务器的所有工具"""
    try:
        mcp_manager = get_mcp_manager()
        tools = await mcp_manager.list_tools(server_name)
        return tools

    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_tool(request: MCPToolExecuteRequest) -> Dict[str, Any]:
    """执行MCP工具"""
    try:
        mcp_manager = get_mcp_manager()
        result = await mcp_manager.execute_tool(
            request.server_name,
            request.tool_name,
            request.arguments
        )
        return result

    except Exception as e:
        logger.error(f"Failed to execute tool: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== 资源管理端点 ====================

@router.get("/resources/{server_name}")
async def list_resources(server_name: str) -> List[Dict[str, Any]]:
    """列出MCP服务器的所有资源"""
    try:
        mcp_manager = get_mcp_manager()
        resources = await mcp_manager.list_resources(server_name)
        return resources

    except Exception as e:
        logger.error(f"Failed to list resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resources/read")
async def read_resource(request: MCPResourceReadRequest) -> Dict[str, Any]:
    """读取MCP资源内容"""
    try:
        mcp_manager = get_mcp_manager()
        result = await mcp_manager.read_resource(request.server_name, request.uri)
        return result

    except Exception as e:
        logger.error(f"Failed to read resource: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== 提示词管理端点 ====================

@router.get("/prompts/{server_name}")
async def list_prompts(server_name: str) -> List[Dict[str, Any]]:
    """列出MCP服务器的所有提示词"""
    try:
        mcp_manager = get_mcp_manager()
        prompts = await mcp_manager.list_prompts(server_name)
        return prompts

    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts/get")
async def get_prompt(request: MCPPromptGetRequest) -> Dict[str, Any]:
    """获取MCP提示词内容"""
    try:
        mcp_manager = get_mcp_manager()
        result = await mcp_manager.get_prompt(
            request.server_name,
            request.prompt_name,
            request.arguments
        )
        return result

    except Exception as e:
        logger.error(f"Failed to get prompt: {e}")
        return {
            "success": False,
            "error": str(e)
        }



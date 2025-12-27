"""
MCP协议实现
基于JSON-RPC 2.0规范
参考：https://www.jsonrpc.org/specification
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class JSONRPCMessageType(Enum):
    """JSON-RPC消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class JSONRPCError(Enum):
    """JSON-RPC预定义错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


class JSONRPCMessage:
    """JSON-RPC消息基类"""

    def __init__(self, jsonrpc: str = "2.0"):
        self.jsonrpc = jsonrpc

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        raise NotImplementedError


class JSONRPCRequest(JSONRPCMessage):
    """JSON-RPC请求"""

    def __init__(
        self,
        method: str,
        params: Optional[Union[Dict[str, Any], List[Any]]] = None,
        request_id: Optional[Union[str, int]] = None,
        jsonrpc: str = "2.0"
    ):
        super().__init__(jsonrpc)
        self.method = method
        self.params = params
        self.id = request_id or str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "id": self.id
        }
        if self.params is not None:
            result["params"] = self.params
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCRequest":
        """从字典创建请求"""
        return cls(
            method=data["method"],
            params=data.get("params"),
            request_id=data.get("id"),
            jsonrpc=data.get("jsonrpc", "2.0")
        )


class JSONRPCResponse(JSONRPCMessage):
    """JSON-RPC响应"""

    def __init__(
        self,
        result: Optional[Any] = None,
        error: Optional[Dict[str, Any]] = None,
        request_id: Optional[Union[str, int]] = None,
        jsonrpc: str = "2.0"
    ):
        super().__init__(jsonrpc)
        self.result = result
        self.error = error
        self.id = request_id

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "jsonrpc": self.jsonrpc,
            "id": self.id
        }
        if self.error is not None:
            result["error"] = self.error
        else:
            result["result"] = self.result
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCResponse":
        """从字典创建响应"""
        return cls(
            result=data.get("result"),
            error=data.get("error"),
            request_id=data.get("id"),
            jsonrpc=data.get("jsonrpc", "2.0")
        )

    def is_error(self) -> bool:
        """是否为错误响应"""
        return self.error is not None


class JSONRPCNotification(JSONRPCMessage):
    """JSON-RPC通知（无响应的单向消息）"""

    def __init__(
        self,
        method: str,
        params: Optional[Union[Dict[str, Any], List[Any]]] = None,
        jsonrpc: str = "2.0"
    ):
        super().__init__(jsonrpc)
        self.method = method
        self.params = params

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method
        }
        if self.params is not None:
            result["params"] = self.params
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCNotification":
        """从字典创建通知"""
        return cls(
            method=data["method"],
            params=data.get("params"),
            jsonrpc=data.get("jsonrpc", "2.0")
        )


class JSONRPCCodec:
    """JSON-RPC编解码器"""

    @staticmethod
    def encode(message: Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification]) -> str:
        """编码消息为JSON字符串"""
        try:
            # 检查消息类型
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Encoding message type: {type(message).__name__}")
            result = message.to_dict()
            logger.debug(f"Encoded successfully, method: {getattr(message, 'method', 'N/A')}")
            return json.dumps(result, ensure_ascii=False)
        except NotImplementedError:
            logging.error(f"NotImplementedError when encoding {type(message).__name__}")
            raise
        except Exception as e:
            raise ValueError(f"Failed to encode JSON-RPC message: {e}")

    @staticmethod
    def decode(data: str) -> Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification]:
        """解码JSON字符串为消息对象"""
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        if "jsonrpc" not in parsed:
            raise ValueError("Missing 'jsonrpc' field")

        # 判断消息类型
        if "method" in parsed:
            if "id" in parsed:
                return JSONRPCRequest.from_dict(parsed)
            else:
                return JSONRPCNotification.from_dict(parsed)
        elif "id" in parsed:
            return JSONRPCResponse.from_dict(parsed)
        else:
            raise ValueError("Unknown message type")

    @staticmethod
    def create_error_response(
        error_code: int,
        error_message: str,
        request_id: Optional[Union[str, int]] = None,
        data: Optional[Any] = None
    ) -> JSONRPCResponse:
        """创建错误响应"""
        error = {
            "code": error_code,
            "message": error_message
        }
        if data is not None:
            error["data"] = data
        return JSONRPCResponse(error=error, request_id=request_id)


class MCPProtocolMethods:
    """MCP协议方法名常量"""

    # 初始化
    INITIALIZE = "initialize"
    INITIALIZED = "notifications/initialized"

    # 工具
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"

    # 资源
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"

    # 提示词
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"

    # 服务器
    SERVER_SET_LEVEL = "server/setLevel"

    # 通用
    PING = "ping"


class MCPProtocolUtils:
    """MCP协议工具类"""

    @staticmethod
    def create_initialize_request(
        capabilities: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> JSONRPCRequest:
        """创建初始化请求"""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": capabilities,
            "clientInfo": {
                "name": "git-ai-core",
                "version": "1.0.0"
            }
        }
        return JSONRPCRequest(
            method=MCPProtocolMethods.INITIALIZE,
            params=params,
            request_id=request_id
        )

    @staticmethod
    def create_tools_list_request(request_id: Optional[str] = None) -> JSONRPCRequest:
        """创建工具列表请求"""
        return JSONRPCRequest(
            method=MCPProtocolMethods.TOOLS_LIST,
            request_id=request_id
        )

    @staticmethod
    def create_tools_call_request(
        name: str,
        arguments: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> JSONRPCRequest:
        """创建工具调用请求"""
        params = {
            "name": name,
            "arguments": arguments
        }
        return JSONRPCRequest(
            method=MCPProtocolMethods.TOOLS_CALL,
            params=params,
            request_id=request_id
        )

    @staticmethod
    def create_resources_list_request(request_id: Optional[str] = None) -> JSONRPCRequest:
        """创建资源列表请求"""
        return JSONRPCRequest(
            method=MCPProtocolMethods.RESOURCES_LIST,
            request_id=request_id
        )

    @staticmethod
    def create_resources_read_request(
        uri: str,
        request_id: Optional[str] = None
    ) -> JSONRPCRequest:
        """创建资源读取请求"""
        params = {"uri": uri}
        return JSONRPCRequest(
            method=MCPProtocolMethods.RESOURCES_READ,
            params=params,
            request_id=request_id
        )

    @staticmethod
    def create_prompts_list_request(request_id: Optional[str] = None) -> JSONRPCRequest:
        """创建提示词列表请求"""
        return JSONRPCRequest(
            method=MCPProtocolMethods.PROMPTS_LIST,
            request_id=request_id
        )

    @staticmethod
    def create_prompts_get_request(
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> JSONRPCRequest:
        """创建获取提示词请求"""
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        return JSONRPCRequest(
            method=MCPProtocolMethods.PROMPTS_GET,
            params=params,
            request_id=request_id
        )

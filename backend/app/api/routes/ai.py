from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import time
from app.core.ai_manager import AIManager
from app.core.advanced_smart_conversation_manager import advanced_smart_conversation_manager

router = APIRouter()

class ChatRequest(BaseModel):
    provider: str = Field(..., description="AI provider name")
    model: str = Field(..., description="Model name")
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    api_key: str = Field(..., description="API key")
    base_url: Optional[str] = Field(None, description="Custom base URL")
    temperature: Optional[float] = Field(None, description="Temperature for generation")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(None, description="Top-p sampling")
    frequency_penalty: Optional[float] = Field(None, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, description="Presence penalty")

class TestConnectionRequest(BaseModel):
    provider: str = Field(..., description="AI provider name")
    api_key: str = Field(..., description="API key")
    base_url: Optional[str] = Field(None, description="Custom base URL")

class GenerateCommentsRequest(BaseModel):
    file_path: str = Field(..., description="File path to generate comments for")
    file_content: str = Field(..., description="File content")
    language: str = Field(..., description="Programming language")
    comment_style: str = Field("detailed", description="Comment style: detailed, brief, documentation")
    provider: str = Field(..., description="AI provider")
    model: str = Field(..., description="AI model")
    api_key: str = Field(..., description="API key")

class AnalyzeArchitectureRequest(BaseModel):
    project_path: str = Field(..., description="Project path")
    file_tree: Dict[str, Any] = Field(..., description="Project file tree")
    project_info: Dict[str, Any] = Field(..., description="Project information")
    provider: str = Field(..., description="AI provider")
    model: str = Field(..., description="AI model")
    api_key: str = Field(..., description="API key")

class SmartConversationRequest(BaseModel):
    project_path: str = Field(..., description="Project path")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    message: Optional[str] = Field(None, description="User message")

class ProviderConfig(BaseModel):
    name: str
    icon: str
    description: str
    models: List[str]
    default_base_url: str
    requires_api_key: bool

ai_manager = AIManager()

@router.get("/providers")
async def get_providers() -> Dict[str, ProviderConfig]:
    """获取所有可用的AI供应商配置"""
    return ai_manager.get_available_providers()

@router.post("/chat")
async def chat(request: ChatRequest) -> Dict[str, Any]:
    """发送聊天消息到AI"""
    try:
        # 使用请求中的参数，如果没有则使用配置的默认值
        default_params = ai_manager.get_default_ai_params()
        
        response = await ai_manager.chat(
            provider=request.provider,
            model=request.model,
            messages=request.messages,
            api_key=request.api_key,
            base_url=request.base_url,
            temperature=request.temperature if request.temperature is not None else default_params["temperature"],
            max_tokens=request.max_tokens if request.max_tokens is not None else default_params["max_tokens"],
            top_p=request.top_p if request.top_p is not None else default_params.get("top_p", 1.0),
            frequency_penalty=request.frequency_penalty if request.frequency_penalty is not None else default_params.get("frequency_penalty", 0.0),
            presence_penalty=request.presence_penalty if request.presence_penalty is not None else default_params.get("presence_penalty", 0.0)
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest) -> Dict[str, bool]:
    """测试AI供应商连接"""
    try:
        success = await ai_manager.test_connection(
            provider=request.provider,
            api_key=request.api_key,
            base_url=request.base_url
        )
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/models/{provider}")
async def get_models(provider: str) -> List[str]:
    """获取指定供应商的可用模型"""
    config = ai_manager.get_provider_config(provider)
    if not config:
        raise HTTPException(status_code=404, detail="Provider not found")
    return config.get("models", [])

@router.post("/generate-comments")
async def generate_comments(request: GenerateCommentsRequest) -> Dict[str, Any]:
    """为代码文件生成注释"""
    try:
        # 构建AI提示词
        prompt = f"""
你是一个专业的代码文档生成器。请为以下{request.language}代码生成高质量的注释。

要求：
1. 只返回注释内容，不要修改原代码
2. 使用{request.language}的适当注释风格
3. 为函数、类、复杂逻辑添加详细注释
4. 保持注释简洁明了
5. 注释风格：{request.comment_style}

代码：
{request.file_content}
        """.strip()

        messages = [
            {"role": "system", "content": "你是一个专业的代码文档生成助手，专注于生成高质量的代码注释。"},
            {"role": "user", "content": prompt}
        ]

        response = await ai_manager.chat(
            provider=request.provider,
            model=request.model,
            messages=messages,
            api_key=request.api_key,
            temperature=0.3,  # 低温度确保注释准确性
            max_tokens=2000
        )
        
        return {
            "comments": response["content"],
            "file_path": request.file_path,
            "language": request.language,
            "usage": response.get("usage", {})
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comment generation failed: {str(e)}")

@router.post("/analyze-architecture")
async def analyze_architecture(request: AnalyzeArchitectureRequest) -> Dict[str, Any]:
    """分析项目架构并生成可视化文档"""
    try:
        # 构建AI提示词
        prompt = f"""
你是一个专业的软件架构师。请分析以下项目的架构并生成详细的架构文档。

项目信息：
- 路径: {request.project_path}
- 名称: {request.project_info.get('name', 'Unknown')}
- 分支: {request.project_info.get('current_branch', 'Unknown')}
- 提交数: {request.project_info.get('commits_count', 0)}

文件结构：
{format_file_tree_for_ai(request.file_tree)}

请生成包含以下内容的架构文档：
1. 项目概述和技术栈分析
2. 主要模块和组件说明
3. 依赖关系分析
4. 架构图（使用Mermaid语法）
5. 改进建议

请使用Markdown格式返回，包含清晰的标题和结构。
        """.strip()

        messages = [
            {"role": "system", "content": "你是一个专业的软件架构分析师，擅长分析代码架构并生成详细的文档。"},
            {"role": "user", "content": prompt}
        ]

        response = await ai_manager.chat(
            provider=request.provider,
            model=request.model,
            messages=messages,
            api_key=request.api_key,
            temperature=0.7,
            max_tokens=3000
        )
        
        return {
            "architecture_doc": response["content"],
            "project_path": request.project_path,
            "usage": response.get("usage", {})
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Architecture analysis failed: {str(e)}")

# 辅助函数
def format_file_tree_for_ai(tree: Dict[str, Any], indent: int = 0) -> str:
    """格式化文件树为AI可读的字符串"""
    if tree.get("type") == "file":
        return "  " * indent + f"📄 {tree['name']}\n"
    
    result = "  " * indent + f"📁 {tree['name']}/\n"
    for child in tree.get("children", []):
        result += format_file_tree_for_ai(child, indent + 1)
    return result

# 智能对话端点
@router.post("/smart-conversation/start")
async def start_smart_conversation(request: SmartConversationRequest) -> Dict[str, Any]:
    """开始智能对话会话"""
    try:
        # 生成会话ID
        conversation_id = f"conv_{int(time.time() * 1000)}"
        
        # 获取项目文件结构
        from app.core.git_manager import GitManager
        git_manager = GitManager()
        # 首先添加项目到管理器
        git_manager.add_project(request.project_path)
        project = git_manager.get_project(request.project_path)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        file_tree = project.get_file_tree(max_depth=2)
        
        # 构建初始系统提示词
        system_prompt = f"""你是一个专业的代码分析助手，可以帮助用户分析项目架构、代码结构和技术栈。

当前分析的项目路径: {request.project_path}
项目文件结构:
{format_file_tree_for_ai(file_tree)}

你可以使用以下工具来获取更多信息：
1. read_project_file - 读取项目文件内容
2. list_project_files - 列出项目文件结构
3. get_file_metadata - 获取文件元数据

请根据用户的问题，智能地使用这些工具来获取所需信息，然后进行分析和回答。
"""

        return {
            "conversation_id": conversation_id,
            "system_prompt": system_prompt,
            "project_path": request.project_path
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start conversation: {str(e)}")

@router.post("/smart-conversation/chat")
async def smart_chat(request: SmartConversationRequest) -> Dict[str, Any]:
    """智能对话聊天"""
    try:
        # 使用高级智能对话管理器处理请求
        result = await advanced_smart_conversation_manager.process_smart_chat(
            request.conversation_id or f"conv_{int(time.time() * 1000)}",
            request.project_path,
            request.message or ""
        )
        
        return {
            "response": result["response"],
            "conversation_id": result["conversation_id"],
            "tool_calls": result["tool_calls"],
            "analysis_context": result.get("analysis_context", {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Smart chat failed: {str(e)}")

@router.post("/smart-conversation/end")
async def end_smart_conversation(request: SmartConversationRequest) -> Dict[str, Any]:
    """结束智能对话会话"""
    return {
        "success": True,
        "message": "Conversation ended successfully",
        "conversation_id": request.conversation_id
    }

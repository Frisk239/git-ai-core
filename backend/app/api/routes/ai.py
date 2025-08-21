from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.core.ai_manager import AIManager

router = APIRouter()

class ChatRequest(BaseModel):
    provider: str = Field(..., description="AI provider name")
    model: str = Field(..., description="Model name")
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    api_key: str = Field(..., description="API key")
    base_url: Optional[str] = Field(None, description="Custom base URL")
    temperature: Optional[float] = Field(0.7, description="Temperature for generation")
    max_tokens: Optional[int] = Field(2000, description="Maximum tokens to generate")

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
        response = await ai_manager.chat(
            provider=request.provider,
            model=request.model,
            messages=request.messages,
            api_key=request.api_key,
            base_url=request.base_url,
            temperature=request.temperature,
            max_tokens=request.max_tokens
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

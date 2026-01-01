from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import json
import os

router = APIRouter()

class AIConfig(BaseModel):
    ai_provider: str = Field(..., description="AI provider name")
    ai_model: str = Field(..., description="AI model name")
    ai_api_key: str = Field(..., description="API key")
    ai_base_url: Optional[str] = Field(None, description="Base URL")
    temperature: Optional[float] = Field(0.7, description="Temperature for generation (0.0-2.0)")
    max_tokens: Optional[int] = Field(2000, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(1.0, description="Top-p sampling (0.0-1.0)")
    frequency_penalty: Optional[float] = Field(0.0, description="Frequency penalty (-2.0 to 2.0)")
    presence_penalty: Optional[float] = Field(0.0, description="Presence penalty (-2.0 to 2.0)")

def get_config_path() -> str:
    """获取配置文件路径"""
    # 从当前文件位置导航到项目根目录，然后到backend目录下的AI-Config.json
    from pathlib import Path
    current_file = Path(__file__).resolve()
    # routes目录 -> api目录 -> app目录 -> backend目录 -> 项目根目录
    project_root = current_file.parent.parent.parent.parent.parent
    config_path = project_root / 'backend' / 'AI-Config.json'
    return str(config_path)

@router.get("/config/ai")
async def get_ai_config() -> Dict[str, Any]:
    """获取AI配置"""
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        return {"exists": False, "config": {}}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return {"exists": True, "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {str(e)}")

@router.post("/config/ai")
async def save_ai_config(config: AIConfig) -> Dict[str, Any]:
    """保存AI配置"""
    config_path = get_config_path()
    
    try:
        # 创建配置目录（如果需要）
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # 保存配置
        config_data = {
            "ai_provider": config.ai_provider,
            "ai_model": config.ai_model,
            "ai_api_key": config.ai_api_key,
            "ai_base_url": config.ai_base_url,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "frequency_penalty": config.frequency_penalty,
            "presence_penalty": config.presence_penalty
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        return {"success": True, "message": "配置保存成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置文件失败: {str(e)}")

@router.delete("/config/ai")
async def delete_ai_config() -> Dict[str, Any]:
    """删除AI配置"""
    config_path = get_config_path()
    
    try:
        if os.path.exists(config_path):
            os.remove(config_path)
            return {"success": True, "message": "配置删除成功"}
        else:
            return {"success": True, "message": "配置文件不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除配置文件失败: {str(e)}")

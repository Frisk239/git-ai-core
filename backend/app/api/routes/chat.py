from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import json
import os

from app.core.chat_database import get_chat_db
from app.models.chat_models import Conversation, Message
from app.core.ai_manager import AIManager

router = APIRouter()
ai_manager = AIManager()

class MessageCreate(BaseModel):
    role: str
    content: str

class ConversationCreate(BaseModel):
    title: Optional[str] = None

class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str

@router.get("/conversations")
async def get_conversations(db: Session = Depends(get_chat_db)):
    """获取所有会话列表"""
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return conversations

@router.post("/conversations")
async def create_conversation(conversation: ConversationCreate, db: Session = Depends(get_chat_db)):
    """创建新会话"""
    # 先将所有会话标记为非活跃
    db.query(Conversation).update({Conversation.is_active: False})
    
    db_conversation = Conversation(
        title=conversation.title or "新会话",
        is_active=True
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    return db_conversation

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_chat_db)):
    """删除会话及其所有消息"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully"}

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int, db: Session = Depends(get_chat_db)):
    """获取会话的所有消息"""
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.timestamp).all()
    return messages

@router.get("/config")
async def get_ai_config():
    """实时读取AI配置文件"""
    config_path = os.path.join("app", "api", "AI-Config.json")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取AI配置失败: {str(e)}")

@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_chat_db)):
    """发送消息并获取AI回复"""
    # 1. 实时读取AI配置
    config = await get_ai_config()
    
    # 2. 获取或创建会话
    if request.conversation_id:
        conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # 创建新会话
        conversation_title = request.message[:30] + "..." if len(request.message) > 30 else request.message
        conversation = Conversation(title=conversation_title, is_active=True)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # 3. 保存用户消息
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
        model_used=config.get("ai_model"),
        provider_used=config.get("ai_provider")
    )
    db.add(user_message)
    
    # 4. 调用AI
    try:
        # 获取对话历史作为上下文
        previous_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp).all()
        
        # 构建消息历史
        messages_for_ai = []
        for msg in previous_messages:
            messages_for_ai.append({"role": msg.role, "content": msg.content})
        
        # 添加当前用户消息
        messages_for_ai.append({"role": "user", "content": request.message})
        
        # 调用AI
        response = await ai_manager.chat(
            provider=config["ai_provider"],
            model=config["ai_model"],
            messages=messages_for_ai,
            api_key=config["ai_api_key"],
            base_url=config.get("ai_base_url"),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 2000),
            top_p=config.get("top_p", 1.0),
            frequency_penalty=config.get("frequency_penalty", 0.0),
            presence_penalty=config.get("presence_penalty", 0.0)
        )
        
        # 5. 保存AI回复
        ai_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response["content"],
            token_count=response["usage"]["total_tokens"],
            model_used=config["ai_model"],
            provider_used=config["ai_provider"]
        )
        db.add(ai_message)
        
        # 6. 更新会话时间
        conversation.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "conversation_id": conversation.id,
            "response": response["content"],
            "usage": response["usage"]
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"AI调用失败: {str(e)}")

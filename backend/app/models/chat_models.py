from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.chat_database import ChatBase

class Conversation(ChatBase):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, default="新会话")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # 关系
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(ChatBase):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    token_count = Column(Integer, default=0)
    model_used = Column(String, nullable=True)
    provider_used = Column(String, nullable=True)
    
    # 关系
    conversation = relationship("Conversation", back_populates="messages")

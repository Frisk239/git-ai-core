import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 专门的AI聊天数据库路径
CHAT_DB_PATH = Path(__file__).parent.parent / "data" / "ai_chat.db"
os.makedirs(CHAT_DB_PATH.parent, exist_ok=True)

CHAT_SQLALCHEMY_DATABASE_URL = f"sqlite:///{CHAT_DB_PATH}"

# 创建专门的聊天数据库引擎
chat_engine = create_engine(
    CHAT_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

# 创建会话工厂
ChatSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=chat_engine)

# 创建基类
ChatBase = declarative_base()

# 数据库初始化
def init_chat_db():
    """初始化AI聊天数据库"""
    try:
        ChatBase.metadata.create_all(bind=chat_engine)
        logger.info("AI聊天数据库初始化成功")
    except Exception as e:
        logger.error(f"AI聊天数据库初始化失败: {e}")
        raise

# 数据库会话管理
def get_chat_db():
    """获取AI聊天数据库会话"""
    db = ChatSessionLocal()
    try:
        yield db
    finally:
        db.close()

# 数据库工具函数
def check_chat_db_health() -> bool:
    """检查AI聊天数据库健康状态"""
    try:
        with chat_engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"AI聊天数据库健康检查失败: {e}")
        return False

import uuid
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config

logger = logging.getLogger(__name__)
Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = 'user'

    id = Column(String(36), primary_key=True)
    username = Column(String(64), nullable=False, unique=True, index=True)  # 用户名
    email = Column(String(128), nullable=True, unique=True, index=True)     # 邮箱
    password_hash = Column(String(256), nullable=True)                       # 密码哈希（游客无密码）
    nickname = Column(String(64), nullable=True)                             # 昵称
    avatar = Column(String(500), nullable=True)                              # 头像URL
    is_guest = Column(Boolean, default=False, index=True)                    # 是否游客
    is_active = Column(Boolean, default=True, index=True)                    # 是否激活
    last_login = Column(DateTime, nullable=True)                             # 最后登录时间
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserSettings(Base):
    """用户设置表（大模型自定义API Key等）"""
    __tablename__ = 'user_settings'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, unique=True, index=True)    # 关联的用户ID
    
    # LLM Settings
    llm_api_key = Column(String(255), nullable=True)                         # 自定义LLM API Key
    llm_api_url = Column(String(255), nullable=True)                         # 自定义LLM API URL
    llm_model = Column(String(100), nullable=True)                           # 自定义模型名
    
    # Embedding Settings
    embedding_api_key = Column(String(255), nullable=True)
    embedding_api_url = Column(String(255), nullable=True)
    embedding_model = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Conversation(Base):
    """会话表"""
    __tablename__ = 'conversation'

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)                 # 用户ID
    title = Column(String(255), nullable=True)                               # 会话标题
    conversation_type = Column(String(32), default='chat', index=True)       # 会话类型: chat/agent/paper_reader
    pdf_object_key = Column(String(255), nullable=True)                      # MinIO 中 PDF 的 object key
    workspace_path = Column(String(500), nullable=True)                      # 会话工作目录路径
    is_deleted = Column(Boolean, default=False, index=True)                  # 是否删除
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)


class Message(Base):
    """消息表"""
    __tablename__ = 'message'

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), nullable=False, index=True)         # 会话ID
    role = Column(String(32), nullable=False, index=True)                    # 角色: user/assistant/system/tool
    content = Column(Text, nullable=False)                                   # 消息内容
    message_type = Column(String(32), default='text')                        # 消息类型: text/tool_call/tool_result
    tool_name = Column(String(64), nullable=True)                            # 工具名称（如果是工具调用）
    tool_result = Column(Text, nullable=True)                                # 工具结果
    created_at = Column(DateTime, default=datetime.now, index=True)

# 创建数据库引擎和会话
engine = create_engine(Config.get_db_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建成功")

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 

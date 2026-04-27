import logging
import os
from sqlalchemy import create_engine, text
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """初始化数据库"""
    try:
        # 创建数据库引擎
        engine = create_engine(Config.get_db_url())
        
        # 创建所有表
        create_tables(engine)
        
        logger.info("数据库初始化成功")
        return True
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False

def create_tables(engine):
    """创建表结构"""

    # 用户表
    user_table = """
    CREATE TABLE IF NOT EXISTS user (
        id VARCHAR(36) PRIMARY KEY,
        username VARCHAR(64) NOT NULL UNIQUE,
        email VARCHAR(128) UNIQUE,
        password_hash VARCHAR(256),
        nickname VARCHAR(64),
        avatar VARCHAR(500),
        is_guest BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        last_login TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 用户配置表
    user_settings_table = """
    CREATE TABLE IF NOT EXISTS user_settings (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL UNIQUE,
        llm_api_key VARCHAR(255),
        llm_api_url VARCHAR(255),
        llm_model VARCHAR(100),
        embedding_api_key VARCHAR(255),
        embedding_api_url VARCHAR(255),
        embedding_model VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 会话表
    conversation_table = """
    CREATE TABLE IF NOT EXISTS conversation (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL,
        title VARCHAR(255),
        conversation_type VARCHAR(32) DEFAULT 'paper_reader',
        pdf_object_key VARCHAR(255) DEFAULT NULL,
        workspace_path VARCHAR(500) DEFAULT NULL,
        is_deleted BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 消息表
    message_table = """
    CREATE TABLE IF NOT EXISTS message (
        id VARCHAR(36) PRIMARY KEY,
        conversation_id VARCHAR(36) NOT NULL,
        role VARCHAR(32) NOT NULL,
        content TEXT NOT NULL,
        message_type VARCHAR(32) DEFAULT 'text',
        tool_name VARCHAR(64),
        tool_result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    try:
        with engine.connect() as conn:
            conn.execute(text(user_table))
            conn.execute(text(user_settings_table))
            conn.execute(text(conversation_table))
            conn.execute(text(message_table))
            conn.commit()

            logger.info("数据库表创建成功")
            return True
    except Exception as e:
        logger.error(f"创建表失败: {e}")
        return False

if __name__ == '__main__':
    init_database()

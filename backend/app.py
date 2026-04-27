"""
FastAPI 应用入口

统一的异步 API 服务，面向论文精读工作流：
- 用户认证
- 会话管理
- PDF 上传与恢复
- 论文精读 (Multi-Agent)

运行方式:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload

或者使用 Python:
    python app.py
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.paper_routes import router as paper_router
from api.routes import (
    pdf_router,
)
from api.user_routes import router as user_router, conversation_router
from init_db import init_database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 降低 watchfiles 的日志级别，避免频繁输出
logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
logging.getLogger("watchfiles").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("FastAPI 应用启动 - Hajimi Paper Reader API 服务")

    # 初始化数据库（创建表结构）
    try:
        init_database()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化失败，应用将继续运行: {e}")

    yield

    # 关闭时
    logger.info("FastAPI 应用关闭")


app = FastAPI(
    title="Hajimi Paper Reader API",
    description="论文精读专用 API 服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(pdf_router, prefix="/api")
app.include_router(paper_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(conversation_router, prefix="/api")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "hajimi-paper-reader-api"}


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Hajimi Paper Reader API",
        "docs": "/docs",
        "redoc": "/redoc",
        "modules": [
            "/api/file/pdf-to-images - PDF 转图片",
            "/api/paper - 论文精读",
            "/api/auth - 用户认证",
            "/api/conversations - 会话管理"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=[
            "**/__pycache__/**",
            "**/*.pyc",
            "**/*.log",
            "**/uploads/**",
            "**/tmp/**",
            "**/.git/**"
        ]
    )

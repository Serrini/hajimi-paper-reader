"""
FastAPI 依赖项
处理认证、数据库连接等
"""

from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.services.user_service import UserService
from db.db_models import get_db, UserSettings
from contextvars import ContextVar
import logging

logger = logging.getLogger(__name__)

# 定义一个存储当前请求用户大模型配置的上下文变量
current_user_settings: ContextVar[dict] = ContextVar('current_user_settings', default={})


class CurrentUser(BaseModel):
    """当前用户信息"""
    user_id: Optional[str] = None
    username: Optional[str] = None
    is_guest: bool = True


def _extract_token(request: Request) -> Optional[str]:
    """从请求头提取 token"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return auth_header


def _load_user_settings(db: Session, user_id: str):
    """从数据库加载并挂载用户的 API 设置到 ContextVar"""
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if settings:
            current_user_settings.set({
                "llm_api_key": settings.llm_api_key,
                "llm_api_url": settings.llm_api_url,
                "llm_model": settings.llm_model,
                "embedding_api_key": settings.embedding_api_key,
                "embedding_api_url": settings.embedding_api_url,
                "embedding_model": settings.embedding_model,
            })
        else:
            current_user_settings.set({})
    except Exception as e:
        logger.error(f"加载用户设置失败: {e}")
        current_user_settings.set({})


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    """
    获取当前用户（必须登录）
    用于需要认证的路由
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = UserService.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("user_id")
    if user_id:
        _load_user_settings(db, user_id)

    return CurrentUser(
        user_id=user_id,
        username=payload.get("username"),
        is_guest=payload.get("is_guest", False)
    )


async def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    """
    获取当前用户（可选登录）
    用于不强制要求登录的路由
    """
    # 无用户访问时，清空上下文保障隔离安全
    current_user_settings.set({})
    
    token = _extract_token(request)
    if not token:
        return CurrentUser()

    try:
        payload = UserService.verify_token(token)
        if payload:
            user_id = payload.get("user_id")
            if user_id:
                _load_user_settings(db, user_id)
                
            return CurrentUser(
                user_id=user_id,
                username=payload.get("username"),
                is_guest=payload.get("is_guest", False)
            )
    except Exception as e:
        logger.warning(f"Token 解析失败: {e}")

    return CurrentUser()


async def get_user_id(request: Request) -> Optional[str]:
    """
    仅获取用户 ID（可选）
    简化版本，用于只需要用户 ID 的场景
    """
    token = _extract_token(request)
    if not token:
        return None

    try:
        payload = UserService.verify_token(token)
        if payload:
            return payload.get("user_id")
    except Exception:
        pass

    return None

"""
FastAPI 用户和会话路由
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db.services.user_service import UserService
from db.services.conversation_service import ConversationService, MessageService
from api.deps import get_current_user, CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["用户认证"])


# ==================== Pydantic 模型 ====================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    nickname: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ==================== 用户认证 API ====================

@router.post("/auth/register")
async def register(req: RegisterRequest):
    """用户注册"""
    try:
        result = UserService.register(
            req.username, req.password, req.email, req.nickname
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["msg"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/auth/login")
async def login(req: LoginRequest):
    """用户登录"""
    try:
        result = UserService.login(req.username, req.password)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["msg"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.post("/auth/guest")
async def guest_login():
    """游客登录"""
    try:
        result = UserService.guest_login()
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["msg"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"游客登录失败: {e}")
        raise HTTPException(status_code=500, detail=f"游客登录失败: {str(e)}")


@router.get("/auth/me")
async def get_current_user_info(user: CurrentUser = Depends(get_current_user)):
    """获取当前用户信息"""
    try:
        user_info = UserService.get_user_by_id(user.user_id)
        if not user_info:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"success": True, "data": user_info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户信息失败: {str(e)}")


# ==================== 会话管理 API ====================

conversation_router = APIRouter(tags=["会话管理"])


@conversation_router.get("/conversations")
def list_conversations(
    type: Optional[str] = Query(None, description="会话类型: chat, agent, paper_reader"),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user)
):
    """获取会话列表"""
    try:
        conversations = ConversationService.get_conversations(user.user_id, type, limit)
        return {"success": True, "data": conversations}
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@conversation_router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """获取会话详情"""
    try:
        conversation = ConversationService.get_conversation(conversation_id, user.user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")

        messages = MessageService.get_messages(conversation_id)
        return {
            "success": True,
            "data": {**conversation, "messages": messages}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@conversation_router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """删除会话"""
    try:
        result = ConversationService.delete_conversation(conversation_id, user.user_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["msg"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@conversation_router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user)
):
    """获取会话消息"""
    try:
        conversation = ConversationService.get_conversation(conversation_id, user.user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")

        messages = MessageService.get_messages(conversation_id, limit)
        return {"success": True, "data": messages}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


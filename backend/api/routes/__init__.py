"""
API 路由注册中心
"""
from fastapi import APIRouter

from . import pdf

# 创建主路由
api_router = APIRouter()

api_router.include_router(pdf.router)

pdf_router = pdf.router

__all__ = [
    'api_router',
    'pdf_router',
]

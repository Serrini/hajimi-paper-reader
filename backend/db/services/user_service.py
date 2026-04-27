"""
用户服务模块
处理用户注册、登录、认证等功能
"""
import uuid
import bcrypt
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Config
from db.db_models import User, Base

logger = logging.getLogger(__name__)

# JWT 配置
JWT_SECRET = Config.get_jwt_secret()
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 7天过期


class UserService:
    """用户服务"""

    @staticmethod
    def _get_session():
        """获取数据库会话"""
        engine = create_engine(Config.get_db_url())
        Session = sessionmaker(bind=engine)
        return Session()

    @staticmethod
    def _hash_password(password: str) -> str:
        """密码哈希"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def _generate_token(user_id: str, username: str, is_guest: bool = False) -> str:
        """生成 JWT token"""
        payload = {
            'user_id': user_id,
            'username': username,
            'is_guest': is_guest,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """验证 JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token 已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token 无效: {e}")
            return None

    @classmethod
    def register(cls, username: str, password: str, email: str = None, nickname: str = None) -> Dict[str, Any]:
        """用户注册"""
        session = cls._get_session()
        try:
            # 检查用户名是否已存在
            existing_user = session.query(User).filter(User.username == username).first()
            if existing_user:
                return {'success': False, 'msg': '用户名已存在'}

            # 检查邮箱是否已存在
            if email:
                existing_email = session.query(User).filter(User.email == email).first()
                if existing_email:
                    return {'success': False, 'msg': '邮箱已被注册'}

            # 创建用户
            user_id = uuid.uuid4().hex
            user = User(
                id=user_id,
                username=username,
                email=email,
                password_hash=cls._hash_password(password),
                nickname=nickname or username,
                is_guest=False,
                is_active=True,
                created_at=datetime.now()
            )
            session.add(user)
            session.commit()

            # 生成 token
            token = cls._generate_token(user_id, username, is_guest=False)

            return {
                'success': True,
                'msg': '注册成功',
                'data': {
                    'user_id': user_id,
                    'username': username,
                    'nickname': user.nickname,
                    'email': email,
                    'is_guest': False,
                    'token': token
                }
            }
        except Exception as e:
            session.rollback()
            logger.error(f"注册失败: {e}")
            return {'success': False, 'msg': f'注册失败: {str(e)}'}
        finally:
            session.close()

    @classmethod
    def login(cls, username: str, password: str) -> Dict[str, Any]:
        """用户登录"""
        session = cls._get_session()
        try:
            # 查找用户（支持用户名或邮箱登录）
            user = session.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()

            if not user:
                return {'success': False, 'msg': '用户不存在'}

            if user.is_guest:
                return {'success': False, 'msg': '游客账号请使用游客登录'}

            if not user.password_hash:
                return {'success': False, 'msg': '账号异常，请联系管理员'}

            if not cls._verify_password(password, user.password_hash):
                return {'success': False, 'msg': '密码错误'}

            if not user.is_active:
                return {'success': False, 'msg': '账号已被禁用'}

            # 更新最后登录时间
            user.last_login = datetime.now()
            session.commit()

            # 生成 token
            token = cls._generate_token(user.id, user.username, is_guest=False)

            return {
                'success': True,
                'msg': '登录成功',
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'nickname': user.nickname,
                    'email': user.email,
                    'avatar': user.avatar,
                    'is_guest': False,
                    'token': token
                }
            }
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return {'success': False, 'msg': f'登录失败: {str(e)}'}
        finally:
            session.close()

    @classmethod
    def guest_login(cls) -> Dict[str, Any]:
        """游客登录"""
        session = cls._get_session()
        try:
            # 生成游客用户
            user_id = uuid.uuid4().hex
            guest_name = f"游客_{user_id[:8]}"

            user = User(
                id=user_id,
                username=guest_name,
                nickname=guest_name,
                is_guest=True,
                is_active=True,
                last_login=datetime.now(),
                created_at=datetime.now()
            )
            session.add(user)
            session.commit()

            # 生成 token
            token = cls._generate_token(user_id, guest_name, is_guest=True)

            return {
                'success': True,
                'msg': '游客登录成功',
                'data': {
                    'user_id': user_id,
                    'username': guest_name,
                    'nickname': guest_name,
                    'is_guest': True,
                    'token': token
                }
            }
        except Exception as e:
            session.rollback()
            logger.error(f"游客登录失败: {e}")
            return {'success': False, 'msg': f'游客登录失败: {str(e)}'}
        finally:
            session.close()

    @classmethod
    def get_user_by_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户信息"""
        session = cls._get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            return {
                'user_id': user.id,
                'username': user.username,
                'nickname': user.nickname,
                'email': user.email,
                'avatar': user.avatar,
                'is_guest': user.is_guest,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
        finally:
            session.close()

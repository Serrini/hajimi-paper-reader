"""
会话服务模块
处理会话和消息的持久化管理
"""
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import desc

from config import Config
from db.db_models import Conversation, Message, SessionLocal
from agent.workspace_manager import workspace_manager

logger = logging.getLogger(__name__)


class ConversationService:
    """会话服务"""

    @staticmethod
    def _get_session():
        """获取数据库会话（复用全局连接池）"""
        return SessionLocal()

    @classmethod
    def create_conversation(cls, user_id: str, title: str = None, conversation_type: str = 'paper_reader', pdf_object_key: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """创建新会话"""
        session = cls._get_session()
        try:
            # 如果未提供ID，则生成新ID
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # 创建会话工作目录
            workspace_path = workspace_manager.create_workspace(conversation_id)
            
            new_conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title=title,
                conversation_type=conversation_type,
                pdf_object_key=pdf_object_key,
                workspace_path=str(workspace_path),
                is_deleted=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(new_conversation)
            session.commit()

            logger.info(f"创建会话成功: {conversation_id}, 工作目录: {workspace_path}")
            
            return {
                'success': True,
                'data': {
                    'id': conversation_id,
                    'user_id': user_id,
                    'title': new_conversation.title,
                    'conversation_type': conversation_type,
                    'workspace_path': str(workspace_path),
                    'created_at': new_conversation.created_at.isoformat()
                }
            }
        except Exception as e:
            session.rollback()
            logger.error(f"创建会话失败: {e}")
            return {'success': False, 'msg': f'创建会话失败: {str(e)}'}
        finally:
            session.close()

    @classmethod
    def get_conversations(cls, user_id: str, conversation_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的会话列表"""
        session = cls._get_session()
        try:
            query = session.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.is_deleted == False
            )

            if conversation_type:
                query = query.filter(Conversation.conversation_type == conversation_type)

            conversations = query.order_by(desc(Conversation.updated_at)).limit(limit).all()

            result = []
            for conv in conversations:
                # 获取最后一条消息
                last_message = session.query(Message).filter(
                    Message.conversation_id == conv.id
                ).order_by(desc(Message.created_at)).first()

                result.append({
                    'id': conv.id,
                    'title': conv.title,
                    'conversation_type': conv.conversation_type,
                    'created_at': conv.created_at.isoformat() if conv.created_at else None,
                    'updated_at': conv.updated_at.isoformat() if conv.updated_at else None,
                    'last_message': last_message.content[:50] + '...' if last_message and len(last_message.content) > 50 else (last_message.content if last_message else None)
                })

            return result
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return []
        finally:
            session.close()

    @classmethod
    def get_conversation(cls, conversation_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """获取单个会话详情"""
        session = cls._get_session()
        try:
            query = session.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.is_deleted == False
            )

            if user_id:
                query = query.filter(Conversation.user_id == user_id)

            conversation = query.first()
            if not conversation:
                return None

            return {
                'id': conversation.id,
                'user_id': conversation.user_id,
                'title': conversation.title,
                'conversation_type': conversation.conversation_type,
                'pdf_object_key': conversation.pdf_object_key,
                'created_at': conversation.created_at.isoformat() if conversation.created_at else None,
                'updated_at': conversation.updated_at.isoformat() if conversation.updated_at else None
            }
        except Exception as e:
            logger.error(f"获取会话详情失败: {e}")
            return None
        finally:
            session.close()

    @classmethod
    def update_pdf_object_key(cls, conversation_id: str, user_id: str, pdf_object_key: str) -> Dict[str, Any]:
        """更新会话的 PDF object key"""
        session = cls._get_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.is_deleted == False
            ).first()

            if not conversation:
                return {'success': False, 'msg': '会话不存在'}

            conversation.pdf_object_key = pdf_object_key
            conversation.updated_at = datetime.now()
            session.commit()

            return {
                'success': True,
                'msg': '更新成功',
                'data': {
                    'id': conversation.id,
                    'pdf_object_key': pdf_object_key
                }
            }
        except Exception as e:
            session.rollback()
            logger.error(f"更新 PDF object key 失败: {e}")
            return {'success': False, 'msg': f'更新失败: {str(e)}'}
        finally:
            session.close()

    @classmethod
    def delete_conversation(cls, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """删除会话（软删除）"""
        session = cls._get_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            ).first()

            if not conversation:
                return {'success': False, 'msg': '会话不存在'}

            conversation.is_deleted = True
            conversation.updated_at = datetime.now()
            session.commit()

            return {'success': True, 'msg': '删除成功'}
        except Exception as e:
            session.rollback()
            logger.error(f"删除会话失败: {e}")
            return {'success': False, 'msg': f'删除失败: {str(e)}'}
        finally:
            session.close()


class MessageService:
    """消息服务"""

    @staticmethod
    def _get_session():
        """获取数据库会话（复用全局连接池）"""
        return SessionLocal()

    @classmethod
    def add_message(cls, conversation_id: str, role: str, content: str,
                    message_type: str = 'text', tool_name: str = None, tool_result: str = None) -> Dict[str, Any]:
        """添加消息"""
        session = cls._get_session()
        try:
            message_id = uuid.uuid4().hex
            message = Message(
                id=message_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                message_type=message_type,
                tool_name=tool_name,
                tool_result=tool_result,
                created_at=datetime.now()
            )
            session.add(message)

            # 更新会话的更新时间
            conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conversation:
                conversation.updated_at = datetime.now()
                # 如果是第一条用户消息且会话标题是默认的，自动更新标题
                if role == 'user' and conversation.title == '新对话':
                    conversation.title = content[:30] + '...' if len(content) > 30 else content

            session.commit()

            return {
                'success': True,
                'data': {
                    'id': message_id,
                    'conversation_id': conversation_id,
                    'role': role,
                    'content': content,
                    'created_at': message.created_at.isoformat()
                }
            }
        except Exception as e:
            session.rollback()
            logger.error(f"添加消息失败: {e}")
            return {'success': False, 'msg': f'添加消息失败: {str(e)}'}
        finally:
            session.close()

    @classmethod
    def get_messages(cls, conversation_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话的消息列表"""
        session = cls._get_session()
        try:
            messages = session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).limit(limit).all()

            return [
                {
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'tool_name': msg.tool_name,
                    'tool_result': msg.tool_result,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"获取消息列表失败: {e}")
            return []
        finally:
            session.close()

    @classmethod
    def get_recent_messages(cls, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的消息（用于上下文）"""
        session = cls._get_session()
        try:
            messages = session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(desc(Message.created_at)).limit(limit).all()

            # 反转顺序，让最早的消息在前面
            messages = list(reversed(messages))

            return [
                {
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"获取最近消息失败: {e}")
            return []
        finally:
            session.close()

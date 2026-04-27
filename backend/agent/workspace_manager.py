"""
会话工作目录管理器
提供会话级工作目录的创建、管理和路径验证功能
"""
import os
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SessionWorkspaceManager:
    """会话工作目录管理器"""
    
    def __init__(self, base_dir: str = None):
        """
        初始化工作目录管理器
        
        Args:
            base_dir: 工作目录的根目录. 默认为项目根目录下的 session_workspaces
        """
        if base_dir is None:
            # backend/agent/workspace_manager.py -> backend/agent -> backend -> imem_studio
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            base_dir = project_root / "session_workspaces"

        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"会话工作目录管理器初始化: {self.base_dir}")
    
    def create_workspace(self, conversation_id: str) -> Path:
        """
        为会话创建独立工作目录
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            工作目录的绝对路径
        """
        workspace = self.base_dir / conversation_id
        workspace.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建会话工作目录: {workspace}")
        return workspace
    
    def get_workspace(self, conversation_id: str) -> Path:
        """
        获取会话工作目录
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            工作目录的绝对路径
        """
        workspace = self.base_dir / conversation_id
        if not workspace.exists():
            logger.warning(f"会话工作目录不存在,自动创建: {workspace}")
            workspace.mkdir(parents=True, exist_ok=True)
        return workspace
    
    def delete_workspace(self, conversation_id: str) -> bool:
        """
        删除会话工作目录
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            是否删除成功
        """
        workspace = self.base_dir / conversation_id
        if workspace.exists():
            try:
                shutil.rmtree(workspace)
                logger.info(f"删除会话工作目录: {workspace}")
                return True
            except Exception as e:
                logger.error(f"删除会话工作目录失败: {e}")
                return False
        return False
    
    def get_workspace_size(self, conversation_id: str) -> int:
        """
        获取会话工作目录的总大小(字节)
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            目录大小(字节)
        """
        workspace = self.base_dir / conversation_id
        if not workspace.exists():
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(workspace):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                try:
                    total_size += filepath.stat().st_size
                except Exception as e:
                    logger.warning(f"无法获取文件大小: {filepath}, {e}")
        
        return total_size


def validate_path(user_path: str, workspace_root: Path) -> Path:
    """
    验证路径必须在工作目录内,防止路径穿越攻击
    
    Args:
        user_path: 用户提供的路径
        workspace_root: 会话工作目录的根路径
        
    Returns:
        验证通过的绝对路径
        
    Raises:
        PermissionError: 如果路径在工作目录外
    """
    # 处理相对路径
    if not Path(user_path).is_absolute():
        full_path = workspace_root / user_path
    else:
        # 绝对路径直接使用
        full_path = Path(user_path)
    
    # 解析为绝对路径(处理 .. 等符号)
    try:
        resolved_path = full_path.resolve()
    except Exception as e:
        raise PermissionError(f"无效的路径: {user_path}, 错误: {e}")
    
    workspace_resolved = workspace_root.resolve()
    
    # 检查是否在工作目录内
    try:
        # 使用 relative_to 检查是否在工作目录内
        resolved_path.relative_to(workspace_resolved)
    except ValueError:
        raise PermissionError(
            f"安全错误: 禁止访问工作目录外的路径\n"
            f"请求路径: {user_path}\n"
            f"解析路径: {resolved_path}\n"
            f"允许范围: {workspace_root}"
        )
    
    return resolved_path


# 全局单例
workspace_manager = SessionWorkspaceManager()

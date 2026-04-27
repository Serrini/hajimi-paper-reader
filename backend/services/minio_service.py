"""
本地文件存储服务（替代 MinIO）
"""
import logging
import os
import shutil
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)


class LocalFileService:
    """基于本地文件系统的文件存储服务，与 MinIOService 接口兼容"""

    PAPERS_DIR = "papers"

    def __init__(self):
        self.storage_root = Config.LOCAL_STORAGE_DIR
        self.papers_dir = os.path.join(self.storage_root, self.PAPERS_DIR)
        os.makedirs(self.papers_dir, exist_ok=True)

    def _get_paper_path(self, user_id: str, conversation_id: str) -> str:
        """生成论文 PDF 的本地路径"""
        user_dir = os.path.join(self.papers_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, f"{conversation_id}.pdf")

    def upload_paper_pdf(self, user_id: str, conversation_id: str, pdf_data: bytes) -> str:
        """保存论文 PDF 到本地，返回相对路径作为 object_key"""
        file_path = self._get_paper_path(user_id, conversation_id)
        with open(file_path, 'wb') as f:
            f.write(pdf_data)
        # 返回相对 storage_root 的相对路径，与 MinIO object_key 等价
        object_key = f"{self.PAPERS_DIR}/{user_id}/{conversation_id}.pdf"
        logger.info(f"PDF 已保存到本地: {file_path}")
        return object_key

    def download_paper_pdf(self, user_id: str, conversation_id: str) -> Optional[bytes]:
        """从本地读取论文 PDF"""
        file_path = self._get_paper_path(user_id, conversation_id)
        if not os.path.exists(file_path):
            logger.warning(f"PDF 文件不存在: {file_path}")
            return None
        with open(file_path, 'rb') as f:
            data = f.read()
        logger.info(f"PDF 已从本地读取: {file_path}")
        return data

    def delete_paper_pdf(self, user_id: str, conversation_id: str) -> bool:
        """删除本地论文 PDF"""
        file_path = self._get_paper_path(user_id, conversation_id)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"PDF 已删除: {file_path}")
            return True
        except Exception as e:
            logger.error(f"PDF 删除失败: {e}")
            return False

    def paper_pdf_exists(self, user_id: str, conversation_id: str) -> bool:
        """检查论文 PDF 是否存在"""
        return os.path.exists(self._get_paper_path(user_id, conversation_id))


# 全局单例
_local_file_service: Optional[LocalFileService] = None


def get_minio_service() -> LocalFileService:
    """获取文件存储服务实例（与原 MinIO 接口兼容的单例入口）"""
    global _local_file_service
    if _local_file_service is None:
        _local_file_service = LocalFileService()
    return _local_file_service

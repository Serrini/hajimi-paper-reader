"""
PDF 处理路由
"""
import base64
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends

from db.services.conversation_service import ConversationService
from api.deps import get_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/file", tags=["PDF处理"])


@router.post("/pdf-to-images")
async def pdf_to_images(
    file: UploadFile = File(...),
    max_pages: Optional[int] = Form(None),
    dpi: int = Form(150),
    conversation_id: str = Form(""),
    user_id: Optional[str] = Depends(get_user_id)
):
    """将 PDF 转换为图片"""
    import fitz

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        total_pages = len(doc)
        page_count = total_pages if max_pages is None else min(total_pages, max_pages)

        images = []
        for page_num in range(page_count):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode()

            images.append({
                "page": page_num + 1,
                "base64": f"data:image/png;base64,{img_base64}",
                "width": pix.width,
                "height": pix.height
            })

        doc.close()

        # 保存到 MinIO
        pdf_object_key = None
        if user_id and conversation_id:
            try:
                from services.minio_service import get_minio_service
                minio_service = get_minio_service()
                pdf_object_key = minio_service.upload_paper_pdf(user_id, conversation_id, pdf_bytes)
                ConversationService.update_pdf_object_key(conversation_id, user_id, pdf_object_key)
                logger.info(f"PDF 已保存到 MinIO: {pdf_object_key}")
            except Exception as e:
                logger.error(f"保存 PDF 到 MinIO 失败: {e}")

        logger.info(f"PDF 转图片成功: {file.filename}, 共 {page_count}/{total_pages} 页")

        return {
            "success": True,
            "data": {
                "images": images,
                "total_pages": total_pages,
                "converted_pages": page_count,
                "filename": file.filename,
                "pdf_object_key": pdf_object_key
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 转换失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 转换失败: {str(e)}")

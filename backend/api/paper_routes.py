"""
论文精读 FastAPI 路由 (异步版本)

使用 LangGraph 原生 astream_events 实现真正的动态路由 + Token级流式输出
"""

import logging
import json
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from db.services.conversation_service import ConversationService, MessageService
from agent.paper_reader import get_paper_reader_multi_agent
from api.deps import get_current_user, get_current_user_optional, CurrentUser

import fitz
from services.minio_service import get_minio_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper", tags=["论文精读"])

DISPLAY_TO_INTERNAL_AGENT = {
    "Planner": "planner",
    "Extractor": "extractor",
    "Analyzer": "analyzer",
    "Critic": "critic",
    "Summarizer": "summarizer",
}


def _normalize_agent_name(agent_name: Optional[str]) -> Optional[str]:
    if not agent_name:
        return None
    return DISPLAY_TO_INTERNAL_AGENT.get(agent_name, agent_name.lower())


def _fallback_paper_title(paper_name: str) -> str:
    return Path(paper_name).stem if paper_name else "未解析标题"


def _parse_planner_output(content: str, paper_name: str) -> Dict[str, Any]:
    metadata = {
        "title": _fallback_paper_title(paper_name),
        "authors": [],
        "abstract": (content or "")[:500]
    }
    if not content:
        return metadata

    try:
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            parsed = json.loads(content[json_start:json_end])
            if isinstance(parsed, dict):
                metadata.update(parsed)
    except json.JSONDecodeError:
        pass

    title = str(metadata.get("title") or "").strip()
    if not title or title == "解析失败":
        metadata["title"] = _fallback_paper_title(paper_name)
    metadata.setdefault("authors", [])
    if not metadata.get("abstract"):
        metadata["abstract"] = (content or "")[:500]
    return metadata


def _rebuild_saved_state(messages: List[Dict[str, Any]], paper_name: str) -> Dict[str, Any]:
    saved_state: Dict[str, Any] = {}
    completed_agents: List[str] = []

    for msg in messages:
        if msg.get("message_type") != "agent_output":
            continue

        internal_name = _normalize_agent_name(msg.get("tool_name"))
        if not internal_name:
            continue

        content = msg.get("content") or ""
        if internal_name == "planner":
            saved_state["paper_metadata"] = _parse_planner_output(content, paper_name)
        elif internal_name == "extractor":
            saved_state["structure"] = {"raw_content": content}
        elif internal_name == "analyzer":
            saved_state["methodology"] = {"raw_content": content}
        elif internal_name == "critic":
            saved_state["critique"] = {"raw_content": content}
        elif internal_name == "summarizer":
            saved_state["summary"] = content
            saved_state["final_output"] = content
        else:
            continue

        if internal_name not in completed_agents:
            completed_agents.append(internal_name)

    for msg in reversed(messages):
        if msg.get("message_type") != "paper_result":
            continue
        try:
            result = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue

        if isinstance(result, dict):
            if result.get("paper_metadata") and "paper_metadata" not in saved_state:
                saved_state["paper_metadata"] = result["paper_metadata"]
            if result.get("final_output") and "final_output" not in saved_state:
                saved_state["final_output"] = result["final_output"]
            if result.get("final_output") and "summary" not in saved_state:
                saved_state["summary"] = result["final_output"]
        break

    if "paper_metadata" in saved_state:
        title = str(saved_state["paper_metadata"].get("title") or "").strip()
        if not title or title == "解析失败":
            saved_state["paper_metadata"]["title"] = _fallback_paper_title(paper_name)

    return {"saved_state": saved_state, "completed_agents": completed_agents}


# ==================== Pydantic 模型 ====================

class PaperReadRequest(BaseModel):
    images: List[str]
    paper_name: str = ""
    conversation_id: str = ""


class PaperContinueRequest(BaseModel):
    images: List[str]
    paper_name: str = ""
    conversation_id: str


class PaperChatRequest(BaseModel):
    question: str
    images: List[str] = []
    paper_metadata: Dict[str, Any] = {}
    context: Dict[str, Any] = {}
    conversation_id: str = ""


# ==================== 论文精读路由 ====================

@router.post("/read/stream")
async def paper_read_stream(
    req: PaperReadRequest,
    user: CurrentUser = Depends(get_current_user_optional)
):
    """
    论文精读 - 流式执行 Multi-Agent (异步版本)

    使用 LangGraph 原生 astream_events 实现:
    - 动态路由: Planner 根据论文内容决定下一个 Agent
    - Token级流式: 每个 Token 实时推送到前端
    """
    if not req.images:
        raise HTTPException(status_code=400, detail="请上传论文图片")

    conversation_id = req.conversation_id

    # 如果用户已登录且没有会话ID，创建新会话
    if user.user_id and not conversation_id:
        title = req.paper_name if req.paper_name else "论文精读"
        conv_result = ConversationService.create_conversation(
            user.user_id, title=title, conversation_type="paper_reader"
        )
        if conv_result["success"]:
            conversation_id = conv_result["data"]["id"]

    multi_agent = get_paper_reader_multi_agent()

    async def event_generator():
        final_result = {}
        current_agent = None
        current_agent_content = ""

        try:
            # 先发送 conversation_id
            if conversation_id:
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "conversation_id", "conversation_id": conversation_id})
                }

            # 直接使用异步生成器，无需线程桥接
            async for event in multi_agent.run_stream_async(
                req.images, req.paper_name, conversation_id
            ):
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False)
                }

                event_type = event.get("type")

                # 跟踪当前 Agent
                if event_type == "agent_start":
                    current_agent = event.get("agent")
                    current_agent_content = ""

                # 收集 Agent 输出内容
                elif event_type == "agent_output_chunk":
                    current_agent_content += event.get("content", "")

                # Agent 输出结束，保存到数据库
                elif event_type == "agent_output_end":
                    if user.user_id and conversation_id and current_agent and current_agent_content:
                        MessageService.add_message(
                            conversation_id, "assistant", current_agent_content,
                            message_type="agent_output", tool_name=current_agent
                        )

                # 收集最终结果
                elif event_type == "reading_complete":
                    final_result = {
                        "final_output": event.get("final_output", ""),
                        "paper_metadata": event.get("paper_metadata", {}),
                        "structure": event.get("structure", {}),
                        "methodology": event.get("methodology", {}),
                        "critique": event.get("critique", {}),
                        "elapsed_time": event.get("elapsed_time", 0)
                    }

            # 保存精读结果到数据库
            if user.user_id and conversation_id and final_result:
                MessageService.add_message(
                    conversation_id, "assistant", json.dumps(final_result, ensure_ascii=False),
                    message_type="paper_result"
                )

            yield {"event": "message", "data": json.dumps({"type": "done"})}

        except Exception as e:
            logger.error(f"论文精读流式处理错误: {e}", exc_info=True)
            yield {"event": "message", "data": json.dumps({"type": "error", "error": str(e)})}

    return EventSourceResponse(event_generator())


@router.post("/read/continue")
async def paper_read_continue(
    req: PaperContinueRequest,
    user: CurrentUser = Depends(get_current_user_optional)
):
    """
    论文精读 - 从断点继续执行 (异步版本)
    """
    if not req.images:
        raise HTTPException(status_code=400, detail="请上传论文图片")

    if not req.conversation_id:
        raise HTTPException(status_code=400, detail="缺少会话ID")

    conversation_id = req.conversation_id

    # 查询已完成的 Agent
    existing_messages = MessageService.get_messages(conversation_id)
    restored = _rebuild_saved_state(existing_messages, req.paper_name)
    completed_agents = restored["completed_agents"]
    saved_state = restored["saved_state"]

    multi_agent = get_paper_reader_multi_agent()

    async def event_generator():
        final_result = {}
        current_agent = None
        current_agent_content = ""

        try:
            # 发送已完成的 Agent 列表
            yield {
                "event": "message",
                "data": json.dumps({"type": "continue_info", "completed_agents": completed_agents})
            }

            async for event in multi_agent.run_stream_continue_async(
                req.images, req.paper_name, conversation_id, completed_agents, saved_state
            ):
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False)
                }

                event_type = event.get("type")

                # 跟踪当前 Agent
                if event_type == "agent_start":
                    current_agent = event.get("agent")
                    current_agent_content = ""

                # 收集 Agent 输出内容
                elif event_type == "agent_output_chunk":
                    current_agent_content += event.get("content", "")

                # Agent 输出结束，保存到数据库
                elif event_type == "agent_output_end":
                    if user.user_id and conversation_id and current_agent and current_agent_content:
                        MessageService.add_message(
                            conversation_id, "assistant", current_agent_content,
                            message_type="agent_output", tool_name=current_agent
                        )

                # 收集最终结果
                elif event_type == "reading_complete":
                    final_result = {
                        "final_output": event.get("final_output", ""),
                        "paper_metadata": event.get("paper_metadata", {}),
                        "structure": event.get("structure", {}),
                        "methodology": event.get("methodology", {}),
                        "critique": event.get("critique", {}),
                        "elapsed_time": event.get("elapsed_time", 0)
                    }

            # 保存精读结果到数据库（如果之前没有）
            if user.user_id and conversation_id and final_result:
                existing = MessageService.get_messages(conversation_id)
                has_paper_result = any(m.get("message_type") == "paper_result" for m in existing)
                if not has_paper_result:
                    MessageService.add_message(
                        conversation_id, "assistant", json.dumps(final_result, ensure_ascii=False),
                        message_type="paper_result"
                    )

            yield {"event": "message", "data": json.dumps({"type": "done"})}

        except Exception as e:
            logger.error(f"论文精读继续执行错误: {e}", exc_info=True)
            yield {"event": "message", "data": json.dumps({"type": "error", "error": str(e)})}

    return EventSourceResponse(event_generator())


@router.post("/chat/stream")
async def paper_chat_stream(
    req: PaperChatRequest,
    user: CurrentUser = Depends(get_current_user_optional)
):
    """
    论文问答 - 精读完成后的多轮对话 (异步版本)
    """
    if not req.question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    conversation_id = req.conversation_id

    # 保存用户问题
    if user.user_id and conversation_id:
        MessageService.add_message(conversation_id, "user", req.question)

    multi_agent = get_paper_reader_multi_agent()

    async def event_generator():
        final_response = ""

        try:
            async for event in multi_agent.chat_stream_async(
                req.question, req.images, req.paper_metadata, req.context
            ):
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False)
                }

                # 收集完整回复
                if event.get("type") == "chat_response_chunk":
                    final_response += event.get("content", "")

            # 保存AI回复
            if user.user_id and conversation_id and final_response:
                MessageService.add_message(conversation_id, "assistant", final_response)

            yield {"event": "message", "data": json.dumps({"type": "done"})}

        except Exception as e:
            logger.error(f"论文问答错误: {e}", exc_info=True)
            yield {"event": "message", "data": json.dumps({"type": "error", "error": str(e)})}

    return EventSourceResponse(event_generator())


@router.get("/pdf/images/{conversation_id}")
async def get_paper_pdf_images(
    conversation_id: str,
    max_pages: Optional[int] = Query(default=None, ge=1, le=500),
    dpi: int = Query(default=150, ge=72, le=300),
    user: CurrentUser = Depends(get_current_user)
):
    """从 MinIO 获取论文 PDF 并转换为图片

    用于恢复会话时加载之前上传的论文
    """

    # 获取会话信息，验证权限
    conversation = ConversationService.get_conversation(conversation_id, user.user_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在或无权限")

    if not conversation.get('pdf_object_key'):
        raise HTTPException(status_code=404, detail="该会话没有关联的 PDF 文件")

    try:
        minio_service = get_minio_service()

        # 从 MinIO 下载 PDF
        pdf_bytes = minio_service.download_paper_pdf(user.user_id, conversation_id)
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail="PDF 文件不存在")

        # 转换为图片
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        page_count = total_pages if max_pages is None else min(total_pages, max_pages)

        images = []
        for page_num in range(page_count):
            page = doc[page_num]
            mat = fitz.Matrix(dpi/72, dpi/72)
            pix = page.get_pixmap(matrix=mat)

            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode()

            images.append({
                'page': page_num + 1,
                'base64': f"data:image/png;base64,{img_base64}",
                'width': pix.width,
                'height': pix.height
            })

        doc.close()

        logger.info(f"从 MinIO 加载 PDF 成功: {conversation_id}, 共 {page_count}/{total_pages} 页")

        return {
            'success': True,
            'data': {
                'conversation_id': conversation_id,
                'total_pages': total_pages,
                'converted_pages': page_count,
                'images': images
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从 MinIO 加载 PDF 失败: {e}")
        raise HTTPException(status_code=500, detail=f"加载失败: {str(e)}")

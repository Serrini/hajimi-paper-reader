"""
论文精读 Multi-Agent 共享状态定义

支持特性：
- Annotated + operator.add 实现自动合并
- worker_outputs 累加模式
- completed_agents 追踪已完成 Agent
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
import operator


class WorkerOutput(TypedDict):
    """Worker 输出结构"""
    source: str           # Agent 名称
    content: str          # 输出内容
    metadata: Dict[str, Any]


class PaperReaderState(TypedDict, total=False):
    """论文精读 Multi-Agent 共享状态"""

    # 消息历史（累加模式）
    messages: Annotated[List[BaseMessage], operator.add]

    # 论文信息
    paper_images: List[str]           # PDF 转换后的图片 (base64)
    paper_name: str                   # 论文文件名
    paper_metadata: Dict[str, Any]    # 标题、作者等元信息

    # 会话 ID（用于持久化）
    conversation_id: str

    # 用户追加请求队列
    user_requests: List[str]

    # Supervisor 决策
    next_steps: List[str]             # Supervisor 决定的下一步 (支持多个并行)

    # Worker 输出（累加模式，支持并行结果自动合并）
    worker_outputs: Annotated[List[WorkerOutput], operator.add]

    # 已完成的 Agent（累加模式）
    completed_agents: Annotated[List[str], operator.add]

    # Agent 输出结果
    structure: Dict[str, Any]         # Extractor: 论文结构
    methodology: Dict[str, Any]       # Analyzer: 方法论分析
    critique: Dict[str, Any]          # Critic: 创新点/局限性
    summary: str                      # Summarizer: 精读总结

    # 执行轨迹（用于前端展示）
    execution_trace: List[Dict[str, Any]]

    # 最终输出
    final_output: str

    # 迭代计数（防止无限循环）
    iteration: int

    # 精读是否完成
    is_reading_complete: bool

    # 是否处于问答模式
    is_qa_mode: bool


def create_initial_state(
    paper_images: List[str],
    paper_name: str = "",
    conversation_id: str = ""
) -> PaperReaderState:
    """创建初始状态"""
    return PaperReaderState(
        messages=[],
        paper_images=paper_images,
        paper_name=paper_name,
        paper_metadata={},
        conversation_id=conversation_id,
        user_requests=[],
        next_steps=[],
        worker_outputs=[],
        completed_agents=[],
        structure={},
        methodology={},
        critique={},
        summary="",
        execution_trace=[],
        final_output="",
        iteration=0,
        is_reading_complete=False,
        is_qa_mode=False
    )

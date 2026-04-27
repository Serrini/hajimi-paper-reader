"""
论文精读 LangGraph 图定义

核心特性：
1. Send API 实现真正的并行
2. astream_events 实现 Token 级流式输出
3. Supervisor 动态路由
4. 自动状态合并（Annotated + operator.add）
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, AsyncGenerator, Literal, Generator

from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from config import Config
from .state import PaperReaderState, create_initial_state
from .supervisor import supervisor_node, get_supervisor
from .agents.base import get_llm, build_messages

logger = logging.getLogger(__name__)


def _fallback_paper_title(paper_name: str) -> str:
    """Use the filename stem as a stable fallback title instead of '解析失败'."""
    if not paper_name:
        return "未解析标题"
    return Path(paper_name).stem or paper_name


# ==================== Worker 节点定义 ====================

SYSTEM_PROMPTS = {
    "planner": """你是一个论文元信息提取专家。
从论文图片中提取基本信息，以 JSON 格式输出：
{
    "title": "论文标题",
    "authors": ["作者1", "作者2"],
    "affiliations": ["机构1", "机构2"],
    "abstract": "摘要内容（翻译成中文）",
    "keywords": ["关键词1", "关键词2"],
    "paper_type": "论文类型"
}""",

    "extractor": """你是一位专业的学术论文阅读助手，擅长分析论文结构。
请用简洁清晰的中文输出，使用 Markdown 格式组织内容。""",

    "analyzer": """你是一位资深的技术方法论分析专家。
请深入分析论文的核心方法和技术细节，用中文输出，使用 Markdown 格式。""",

    "critic": """你是一位严谨的学术论文审稿人，擅长批判性分析论文。
请客观评价论文的创新点和局限性，用中文输出，使用 Markdown 格式。""",

    "summarizer": """你是一位专业的学术论文总结专家。
请整合所有分析结果，生成一份全面的论文精读总结，用中文输出，使用 Markdown 格式。"""
}


async def planner_node(state: PaperReaderState, config: RunnableConfig = None) -> Dict[str, Any]:
    """Planner 节点 - 提取论文元信息"""
    images = state.get("paper_images", [])
    paper_name = state.get("paper_name", "")

    logger.info(f"[Planner] 开始提取元信息，共 {len(images)} 页")

    llm = get_llm(streaming=True)
    messages = build_messages(
        system_prompt=SYSTEM_PROMPTS["planner"],
        user_prompt=f"请仔细查看这篇论文的前几页，提取论文的基本信息。\n论文名称（参考）: {paper_name}",
        images=images[:4]
    )

    full_response = ""
    async for chunk in llm.astream(messages, config=config):
        if chunk.content:
            full_response += chunk.content

    # 解析 JSON
    paper_metadata = {"title": _fallback_paper_title(paper_name), "authors": [], "abstract": full_response[:500]}
    try:
        json_start = full_response.find('{')
        json_end = full_response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            paper_metadata = json.loads(full_response[json_start:json_end])
    except json.JSONDecodeError:
        pass

    if not isinstance(paper_metadata, dict):
        paper_metadata = {}

    paper_metadata.setdefault("authors", [])
    if not paper_metadata.get("abstract"):
        paper_metadata["abstract"] = full_response[:500]

    title = str(paper_metadata.get("title") or "").strip()
    if not title or title == "解析失败":
        paper_metadata["title"] = _fallback_paper_title(paper_name)

    logger.info(f"[Planner] 完成，论文: {paper_metadata.get('title', '未知')[:50]}")

    return {
        "paper_metadata": paper_metadata,
        "worker_outputs": [{"source": "planner", "content": full_response, "metadata": {}}],
        "completed_agents": ["planner"]
    }


async def extractor_node(state: PaperReaderState, config: RunnableConfig = None) -> Dict[str, Any]:
    """Extractor 节点 - 提取论文结构"""
    images = state.get("paper_images", [])
    metadata = state.get("paper_metadata", {})

    title = metadata.get("title", "未知")
    abstract = metadata.get("abstract", "")[:500]

    logger.info(f"[Extractor] 开始提取结构")

    llm = get_llm(streaming=True)
    user_prompt = f"""请仔细阅读这篇论文，提取结构化内容。

**论文**: {title}
**摘要**: {abstract}

提取以下内容：
## 1. 引言
## 2. 相关工作
## 3. 方法
## 4. 实验
## 5. 结论"""

    messages = build_messages(SYSTEM_PROMPTS["extractor"], user_prompt, images)

    full_response = ""
    async for chunk in llm.astream(messages, config=config):
        if chunk.content:
            full_response += chunk.content

    logger.info(f"[Extractor] 完成，输出 {len(full_response)} 字符")

    return {
        "structure": {"raw_content": full_response},
        "worker_outputs": [{"source": "extractor", "content": full_response, "metadata": {}}],
        "completed_agents": ["extractor"]
    }


async def analyzer_node(state: PaperReaderState, config: RunnableConfig = None) -> Dict[str, Any]:
    """Analyzer 节点 - 深度方法论分析"""
    images = state.get("paper_images", [])
    metadata = state.get("paper_metadata", {})

    title = metadata.get("title", "未知")
    abstract = metadata.get("abstract", "")[:500]

    logger.info(f"[Analyzer] 开始方法论分析")

    llm = get_llm(streaming=True)
    user_prompt = f"""请深度分析这篇论文的方法论。

**论文**: {title}
**摘要**: {abstract}

分析以下内容：
## 核心方法概述
## 技术架构
## 关键算法
## 创新设计
## 理论基础"""

    messages = build_messages(SYSTEM_PROMPTS["analyzer"], user_prompt, images)

    full_response = ""
    async for chunk in llm.astream(messages, config=config):
        if chunk.content:
            full_response += chunk.content

    logger.info(f"[Analyzer] 完成，输出 {len(full_response)} 字符")

    return {
        "methodology": {"raw_content": full_response},
        "worker_outputs": [{"source": "analyzer", "content": full_response, "metadata": {}}],
        "completed_agents": ["analyzer"]
    }


async def critic_node(state: PaperReaderState, config: RunnableConfig = None) -> Dict[str, Any]:
    """Critic 节点 - 创新点与局限性分析"""
    images = state.get("paper_images", [])
    metadata = state.get("paper_metadata", {})

    title = metadata.get("title", "未知")
    abstract = metadata.get("abstract", "")[:500]

    logger.info(f"[Critic] 开始批判性分析")

    llm = get_llm(streaming=True)
    user_prompt = f"""请对这篇论文进行批判性分析。

**论文**: {title}
**摘要**: {abstract}

分析以下内容：
## 创新贡献
## 实验评价
## 局限性
## 与相关工作对比
## 改进建议"""

    messages = build_messages(SYSTEM_PROMPTS["critic"], user_prompt, images)

    full_response = ""
    async for chunk in llm.astream(messages, config=config):
        if chunk.content:
            full_response += chunk.content

    logger.info(f"[Critic] 完成，输出 {len(full_response)} 字符")

    return {
        "critique": {"raw_content": full_response},
        "worker_outputs": [{"source": "critic", "content": full_response, "metadata": {}}],
        "completed_agents": ["critic"]
    }


async def summarizer_node(state: PaperReaderState, config: RunnableConfig = None) -> Dict[str, Any]:
    """Summarizer 节点 - 生成精读总结"""
    images = state.get("paper_images", [])
    metadata = state.get("paper_metadata", {})
    structure = state.get("structure", {})
    methodology = state.get("methodology", {})
    critique = state.get("critique", {})

    title = metadata.get("title", "未知")
    authors = ", ".join(metadata.get("authors", []))
    abstract = metadata.get("abstract", "")[:500]

    logger.info(f"[Summarizer] 开始生成总结")

    # 构建上下文
    context_parts = []
    if structure.get("raw_content"):
        context_parts.append(f"**结构分析**:\n{structure['raw_content'][:1500]}...")
    if methodology.get("raw_content"):
        context_parts.append(f"**方法论分析**:\n{methodology['raw_content'][:1500]}...")
    if critique.get("raw_content"):
        context_parts.append(f"**批判性分析**:\n{critique['raw_content'][:1500]}...")

    llm = get_llm(streaming=True)
    user_prompt = f"""请为这篇论文生成一份综合精读总结。

**论文**: {title}
**作者**: {authors}
**摘要**: {abstract}

**已有分析**:
{chr(10).join(context_parts)}

请生成精读总结，包括：
## 一句话总结
## 研究背景与动机
## 核心方法
## 主要贡献
## 实验结论
## 优缺点分析
## 适合谁读
## 相关论文推荐"""

    messages = build_messages(SYSTEM_PROMPTS["summarizer"], user_prompt, images[:5])

    full_response = ""
    async for chunk in llm.astream(messages, config=config):
        if chunk.content:
            full_response += chunk.content

    logger.info(f"[Summarizer] 完成，输出 {len(full_response)} 字符")

    return {
        "summary": full_response,
        "worker_outputs": [{"source": "summarizer", "content": full_response, "metadata": {}}],
        "completed_agents": ["summarizer"]
    }


async def finalize_node(state: PaperReaderState) -> Dict[str, Any]:
    """完成节点 - 汇总所有结果"""
    summary = state.get("summary", "")

    if not summary:
        outputs = state.get("worker_outputs", [])
        summary = "\n\n---\n\n".join([
            f"## {o['source']}\n\n{o['content']}" for o in outputs
        ])

    return {"summary": summary, "final_output": summary}


# ==================== 路由器 ====================

def parallel_router(state: PaperReaderState) -> List[Send] | Literal["finalize"]:
    """
    动态并行路由器

    根据 Supervisor 的 next_steps 决策，使用 Send 实现并行
    """
    steps = state.get("next_steps", [])

    if not steps or "FINISH" in steps:
        return "finalize"

    routes = []
    node_map = {
        "planner": "planner",
        "extractor": "extractor",
        "analyzer": "analyzer",
        "critic": "critic",
        "summarizer": "summarizer"
    }

    for step in steps:
        if step in node_map:
            routes.append(Send(node_map[step], state))

    if not routes:
        return "finalize"

    logger.info(f"[Router] 并行执行: {steps}")
    return routes


# ==================== 构建图 ====================

def build_graph(checkpointer=None) -> StateGraph:
    """
    构建 LangGraph 图

    结构：
        supervisor → router → [workers 并行] → supervisor → ... → finalize
    """
    workflow = StateGraph(PaperReaderState)

    # 添加节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("finalize", finalize_node)

    # 入口
    workflow.set_entry_point("supervisor")

    # Supervisor → Router (条件边)
    workflow.add_conditional_edges(
        "supervisor",
        parallel_router,
        ["planner", "extractor", "analyzer", "critic", "summarizer", "finalize"]
    )

    # Workers → Supervisor (回环)
    workflow.add_edge("planner", "supervisor")
    workflow.add_edge("extractor", "supervisor")
    workflow.add_edge("analyzer", "supervisor")
    workflow.add_edge("critic", "supervisor")
    workflow.add_edge("summarizer", "supervisor")

    # Finalize → END
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer or MemorySaver())


# ==================== 事件流处理 ====================

# Worker 显示名称
WORKER_DISPLAY_NAMES = {
    "planner": "Planner",
    "extractor": "Extractor",
    "analyzer": "Analyzer",
    "critic": "Critic",
    "summarizer": "Summarizer",
    "supervisor": "Supervisor",
    "finalize": "Finalize"
}

WORKER_DESCRIPTIONS = {
    "planner": "论文解析与元信息提取",
    "extractor": "论文结构提取",
    "analyzer": "方法论深度分析",
    "critic": "创新点与局限性分析",
    "summarizer": "生成精读总结",
    "supervisor": "任务调度决策",
    "finalize": "汇总结果"
}


async def stream_graph_events(
    graph,
    input_state: PaperReaderState,
    config: RunnableConfig = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    流式输出（V1 兼容格式）

    输出格式：
    - {"type": "agent_start", "agent": "Planner", "description": "..."}
    - {"type": "agent_output_chunk", "agent": "Planner", "content": "方"}
    - {"type": "agent_output_end", "agent": "Planner"}
    - {"type": "reading_complete", ...}

    特性：
    - 单节点异常不会中断整个事件流
    - 并行执行时事件正确分发
    """
    config = config or RunnableConfig(tags=["paper_reader"], recursion_limit=50)

    start_time = time.time()
    final_state = input_state.copy()

    active_nodes = set()
    node_contents = {}  # 追踪每个节点的累积内容 {node_name: content}
    skip_nodes = {"__start__", "", "supervisor", "finalize"}
    error_occurred = False
    error_message = ""

    try:
        async for event in graph.astream_events(input_state, config=config, version="v2"):
            try:
                kind = event.get("event")
                metadata = event.get("metadata", {})
                data = event.get("data", {})

                node_name = metadata.get("langgraph_node", "")

                # Worker 节点开始
                if kind == "on_chain_start":
                    if node_name and node_name not in skip_nodes:
                        if node_name not in active_nodes:
                            active_nodes.add(node_name)
                            node_contents[node_name] = ""
                            display_name = WORKER_DISPLAY_NAMES.get(node_name, node_name)
                            description = WORKER_DESCRIPTIONS.get(node_name, "")

                            yield {"type": "agent_start", "agent": display_name, "description": description}
                            yield {"type": "agent_output_start", "agent": display_name}

                # LLM 流式输出
                elif kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        if node_name and node_name not in skip_nodes:
                            display_name = WORKER_DISPLAY_NAMES.get(node_name, node_name)
                            # 追踪内容
                            if node_name in node_contents:
                                node_contents[node_name] += chunk.content
                            yield {"type": "agent_output_chunk", "agent": display_name, "content": chunk.content}

                # Worker 节点结束
                elif kind == "on_chain_end":
                    if node_name and node_name in active_nodes:
                        active_nodes.discard(node_name)
                        display_name = WORKER_DISPLAY_NAMES.get(node_name, node_name)

                        yield {"type": "agent_output_end", "agent": display_name}

                        # 提取结果
                        output = data.get("output")
                        if isinstance(output, dict):
                            for key in ["paper_metadata", "structure", "methodology", "critique", "summary"]:
                                if key in output and output[key]:
                                    final_state[key] = output[key]

                            # 发送 agent_complete
                            result = {}
                            if node_name == "planner" and output.get("paper_metadata"):
                                result = {"paper_metadata": output["paper_metadata"]}
                            elif node_name == "extractor" and output.get("structure"):
                                result = {"structure": output["structure"]}
                            elif node_name == "analyzer" and output.get("methodology"):
                                result = {"methodology": output["methodology"]}
                            elif node_name == "critic" and output.get("critique"):
                                result = {"critique": output["critique"]}
                            elif node_name == "summarizer" and output.get("summary"):
                                result = {"summary": output["summary"]}

                            yield {"type": "agent_complete", "agent": display_name, "result": result}

                        yield {"type": "agent_end", "agent": display_name}
                        # 清理追踪
                        node_contents.pop(node_name, None)

            except Exception as e:
                # 单个事件处理错误，记录但继续
                logger.warning(f"[stream_graph_events] 事件处理错误: {e}")
                continue

    except Exception as e:
        error_occurred = True
        error_message = str(e)
        logger.error(f"[stream_graph_events] 图执行错误: {e}", exc_info=True)

        # 为未完成的节点发送错误结束事件
        for node_name in list(active_nodes):
            display_name = WORKER_DISPLAY_NAMES.get(node_name, node_name)
            yield {"type": "agent_error", "agent": display_name, "error": str(e)}
            yield {"type": "agent_end", "agent": display_name}

    # 发送完成事件（即使有错误也发送，确保前端收到结束信号）
    elapsed_time = time.time() - start_time
    complete_event = {
        "type": "reading_complete",
        "final_output": final_state.get("summary", ""),
        "paper_metadata": final_state.get("paper_metadata", {}),
        "structure": final_state.get("structure", {}),
        "methodology": final_state.get("methodology", {}),
        "critique": final_state.get("critique", {}),
        "elapsed_time": elapsed_time
    }
    if error_occurred:
        complete_event["error"] = error_message
        complete_event["partial"] = True  # 标记为部分完成

    yield complete_event


# ==================== 主执行器 ====================

class PaperReaderMultiAgent:
    """
    论文精读 Multi-Agent 系统

    整合 Supervisor 动态路由 + Send API 并行执行
    """

    def __init__(self, checkpointer=None):
        self.graph = build_graph(checkpointer)
        self.checkpointer = checkpointer

    async def run_stream_async(
        self,
        paper_images: List[str],
        paper_name: str = "",
        conversation_id: str = ""
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式执行论文精读

        使用 Supervisor 动态路由 + Send API 并行执行
        异常处理：单节点失败不会中断整个流程
        """
        initial_state = create_initial_state(
            paper_images=paper_images,
            paper_name=paper_name,
            conversation_id=conversation_id
        )

        config = RunnableConfig(
            tags=["paper_reader"],
            configurable={"thread_id": conversation_id}
        )

        yield {
            "type": "reading_start",
            "paper_name": paper_name,
            "agents": ["Planner", "Extractor", "Analyzer", "Critic", "Summarizer"]
        }

        # stream_graph_events 内部已处理异常，会确保发送 reading_complete
        async for event in stream_graph_events(self.graph, initial_state, config):
            yield event

    def run_stream(
        self,
        paper_images: List[str],
        paper_name: str = "",
        conversation_id: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """
        同步流式执行（兼容旧代码）
        """
        import asyncio

        async def collect_events():
            events = []
            async for event in self.run_stream_async(paper_images, paper_name, conversation_id):
                events.append(event)
            return events

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, collect_events())
                    events = future.result()
            else:
                events = loop.run_until_complete(collect_events())
        except RuntimeError:
            events = asyncio.run(collect_events())

        for event in events:
            yield event

    async def run_stream_continue_async(
        self,
        paper_images: List[str],
        paper_name: str = "",
        conversation_id: str = "",
        completed_agents: List[str] = None,
        saved_state: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """从断点继续执行（异步版本）"""
        resumed_state = create_initial_state(
            paper_images=paper_images,
            paper_name=paper_name,
            conversation_id=conversation_id
        )

        if saved_state:
            for key in ["paper_metadata", "structure", "methodology", "critique", "summary", "final_output"]:
                value = saved_state.get(key)
                if value:
                    resumed_state[key] = value

        if completed_agents:
            resumed_state["completed_agents"] = completed_agents

        config = RunnableConfig(
            tags=["paper_reader"],
            configurable={"thread_id": conversation_id}
        )

        yield {
            "type": "reading_start",
            "paper_name": paper_name,
            "agents": ["Planner", "Extractor", "Analyzer", "Critic", "Summarizer"],
            "resume": True
        }

        async for event in stream_graph_events(self.graph, resumed_state, config):
            yield event

    def run_stream_continue(
        self,
        paper_images: List[str],
        paper_name: str = "",
        conversation_id: str = "",
        completed_agents: List[str] = None,
        saved_state: Dict[str, Any] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """从断点继续执行"""
        for event in self.run_stream(paper_images, paper_name, conversation_id):
            yield event

    async def chat_stream_async(
        self,
        question: str,
        paper_images: List[str],
        paper_metadata: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """异步论文问答"""
        llm = get_llm(streaming=True)

        system_prompt = f"""你是一个论文阅读助手，正在帮助用户理解一篇论文。

论文信息：
- 标题：{paper_metadata.get('title', '未知')}
- 作者：{', '.join(paper_metadata.get('authors', []))}
- 摘要：{paper_metadata.get('abstract', '未知')}

已有的分析结果：
{context.get('summary', '')[:2000]}

请根据论文内容和已有分析，回答用户的问题。如果问题超出论文范围，请明确告知。"""

        messages = build_messages(
            system_prompt=system_prompt,
            user_prompt=f"用户问题：{question}",
            images=paper_images[:3]
        )

        yield {"type": "chat_response_start"}

        async for chunk in llm.astream(messages):
            if chunk.content:
                yield {"type": "chat_response_chunk", "content": chunk.content}

        yield {"type": "chat_response_end"}

    def chat_stream(
        self,
        question: str,
        paper_images: List[str],
        paper_metadata: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Generator[Dict[str, Any], None, None]:
        """同步论文问答"""
        llm_config = Config.get_llm_config()
        llm = ChatOpenAI(
            model=llm_config.get('model', 'gpt-4o'),
            api_key=llm_config.get('api_key', ''),
            base_url=llm_config.get('api_url', 'https://api.openai.com/v1'),
            temperature=0.3,
            timeout=300,
            max_retries=2,
            streaming=True
        )

        system_prompt = f"""你是一个论文阅读助手，正在帮助用户理解一篇论文。

论文信息：
- 标题：{paper_metadata.get('title', '未知')}
- 作者：{', '.join(paper_metadata.get('authors', []))}
- 摘要：{paper_metadata.get('abstract', '未知')}

已有的分析结果：
{context.get('summary', '')[:2000]}

请根据论文内容和已有分析，回答用户的问题。如果问题超出论文范围，请明确告知。"""

        messages = build_messages(
            system_prompt=system_prompt,
            user_prompt=f"用户问题：{question}",
            images=paper_images[:3]
        )

        yield {"type": "chat_response_start"}

        for chunk in llm.stream(messages):
            if chunk.content:
                yield {"type": "chat_response_chunk", "content": chunk.content}

        yield {"type": "chat_response_end"}


# ==================== 全局实例 ====================

_paper_reader_multi_agent = None


def get_paper_reader_multi_agent() -> PaperReaderMultiAgent:
    """获取Multi-Agent实例（单例）"""
    global _paper_reader_multi_agent
    if _paper_reader_multi_agent is None:
        _paper_reader_multi_agent = PaperReaderMultiAgent()
    return _paper_reader_multi_agent

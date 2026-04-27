"""
Paper Agent 基类

支持同步和异步 LLM 调用
"""
from typing import Dict, Any, Generator, List, AsyncGenerator
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
import logging
from config import Config

logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================

def get_llm(streaming: bool = True, temperature: float = 0.3) -> ChatOpenAI:
    """
    获取 LLM 实例

    Args:
        streaming: 是否启用流式
        temperature: 温度参数
    """
    llm_config = Config.get_llm_config()

    return ChatOpenAI(
        model=llm_config.get('model'),
        api_key=llm_config.get('api_key'),
        base_url=llm_config.get('api_url'),
        temperature=temperature,
        timeout=600,  # 10分钟超时，论文分析涉及大量图片
        max_retries=3,
        streaming=streaming
    )


def build_image_content(images: List[str], max_images: int = 20) -> List[Dict[str, Any]]:
    """
    构建多模态图片内容

    Args:
        images: Base64 图片列表
        max_images: 最大图片数
    """
    content = []
    for img in images[:max_images]:
        if not img.startswith('data:'):
            img = f"data:image/png;base64,{img}"
        content.append({
            "type": "image_url",
            "image_url": {"url": img, "detail": "high"}
        })
    return content


def is_minimax_provider() -> bool:
    """Detect whether the configured chat endpoint is MiniMax."""
    llm_config = Config.get_llm_config()
    api_url = (llm_config.get("api_url") or "").strip()
    if not api_url:
        return False

    hostname = (urlparse(api_url).hostname or "").lower()
    return "minimaxi.com" in hostname


def build_minimax_image_prompt(images: List[str], max_images: int = 20) -> str:
    """
    Build MiniMax-friendly image input.

    MiniMax's official visual-understanding example sends image base64 inside
    the user text instead of OpenAI-style image_url content blocks.
    """
    image_lines = []
    for img in images[:max_images]:
        normalized = img
        if normalized.startswith("data:"):
            _, _, normalized = normalized.partition(",")
        image_lines.append(f"[图片base64:{normalized}]")
    return "\n".join(image_lines)


def build_messages(
    system_prompt: str,
    user_prompt: str,
    images: List[str] = None
) -> List[Dict[str, Any]]:
    """
    构建消息列表

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        images: 可选的图片列表
    """
    if images:
        if is_minimax_provider():
            minimax_prompt = build_minimax_image_prompt(images)
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{user_prompt}\n\n{minimax_prompt}"}
            ]

        user_content = [{"type": "text", "text": user_prompt}]
        user_content.extend(build_image_content(images))

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def get_worker_config(node_name: str) -> RunnableConfig:
    """
    获取 Worker 节点配置

    添加 tags 用于 astream_events 过滤
    """
    return RunnableConfig(
        tags=["worker_node", node_name],
        metadata={"worker_name": node_name}
    )


# ==================== 基类定义 ====================

class BasePaperAgent(ABC):
    """Paper Agent 基类（保持向后兼容）"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._init_llm()

    def _init_llm(self):
        llm_config = Config.get_llm_config()

        self.llm = ChatOpenAI(
            model=llm_config.get('model'),
            api_key=llm_config.get('api_key'),
            base_url=llm_config.get('api_url'),
            temperature=0.3,
            timeout=600,  # 10分钟超时
            max_retries=3,
            streaming=True
        )

    @abstractmethod
    def get_system_prompt(self) -> str:
        pass

    def _build_image_content(self, images: List[str]) -> List[Dict[str, Any]]:
        """构建图片内容"""
        return build_image_content(images)

    def _invoke_llm_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        images: List[str]
    ) -> str:
        """调用LLM（带图片）"""
        messages = build_messages(system_prompt, user_prompt, images)
        response = self.llm.invoke(messages)
        return response.content

    def _invoke_llm_with_images_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        images: List[str]
    ) -> Generator[str, None, None]:
        """流式调用LLM（带图片）"""
        messages = build_messages(system_prompt, user_prompt, images)

        for chunk in self.llm.stream(messages):
            if chunk.content:
                yield chunk.content

    async def _invoke_llm_with_images_astream(
        self,
        system_prompt: str,
        user_prompt: str,
        images: List[str],
        config: RunnableConfig = None
    ) -> AsyncGenerator[str, None]:
        """异步流式调用LLM（带图片）"""
        messages = build_messages(system_prompt, user_prompt, images)

        async for chunk in self.llm.astream(messages, config=config):
            if chunk.content:
                yield chunk.content

    def _invoke_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用LLM（纯文本）"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = self.llm.invoke(messages)
        return response.content

    def _invoke_llm_stream(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> Generator[str, None, None]:
        """流式调用LLM（纯文本）"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        for chunk in self.llm.stream(messages):
            if chunk.content:
                yield chunk.content

    async def _invoke_llm_astream(
        self,
        system_prompt: str,
        user_prompt: str,
        config: RunnableConfig = None
    ) -> AsyncGenerator[str, None]:
        """异步流式调用LLM（纯文本）"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        async for chunk in self.llm.astream(messages, config=config):
            if chunk.content:
                yield chunk.content

    @abstractmethod
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行Agent逻辑"""
        pass

    @abstractmethod
    def run_stream(self, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """流式执行Agent逻辑"""
        pass

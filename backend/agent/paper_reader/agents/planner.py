"""
Planner Agent - 任务规划和用户请求处理
"""
from typing import Dict, Any, Generator
from .base import BasePaperAgent
import logging
import json

logger = logging.getLogger(__name__)


class PlannerAgent(BasePaperAgent):
    """任务规划Agent - 解析论文、规划任务、处理追加请求"""

    def __init__(self):
        super().__init__(
            name="Planner",
            description="任务规划者，负责解析论文基本信息、规划精读任务、处理用户追加请求"
        )

    def get_system_prompt(self) -> str:
        return """你是一个论文精读助手的任务规划者。

你的职责：
1. 识别论文的基本信息（标题、作者、摘要等）
2. 规划论文精读的执行流程
3. 处理用户的追加请求

输出要求：
- 以JSON格式输出论文元信息
- 清晰说明将要执行的分析步骤

请用中文输出。"""

    def _extract_metadata(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """从论文图片中提取元信息"""
        images = state.get("paper_images", [])
        if not images:
            return {"error": "没有论文图片"}

        # 只使用前几页来提取元信息
        first_pages = images[:2] if len(images) > 2 else images

        prompt = """请仔细查看这篇论文的前几页，提取以下信息：

1. 论文标题 (title)
2. 作者列表 (authors)
3. 发表机构/单位 (affiliations)
4. 摘要 (abstract)
5. 关键词 (keywords)
6. 论文类型 (type): 如 Conference Paper, Journal Article, Preprint 等

请以JSON格式输出：
{
    "title": "论文标题",
    "authors": ["作者1", "作者2"],
    "affiliations": ["机构1", "机构2"],
    "abstract": "摘要内容",
    "keywords": ["关键词1", "关键词2"],
    "type": "论文类型"
}

如果某些信息无法识别，请填写 "未识别"。"""

        response = self._invoke_llm_with_images(
            self.get_system_prompt(),
            prompt,
            first_pages
        )

        # 解析JSON
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            pass

        return {
            "title": "未能解析",
            "authors": [],
            "abstract": response,
            "keywords": []
        }

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Planner主逻辑"""
        iteration = state.get("iteration", 0)

        logger.info(f"[Planner] 第{iteration}轮规划")

        # 首次运行，提取元信息
        if iteration == 0:
            metadata = self._extract_metadata(state)
            logger.info(f"[Planner] 提取论文元信息: {metadata.get('title', '未知')}")

            return {
                "paper_metadata": metadata,
                "next_agent": "extractor",
                "iteration": 1,
                "execution_trace": [{
                    "agent": self.name,
                    "action": "论文解析",
                    "summary": f"论文：{metadata.get('title', '未知')}",
                    "output_preview": metadata.get("abstract", "")[:200]
                }]
            }

        # 检查是否有用户追加请求
        user_requests = state.get("user_requests", [])
        if user_requests:
            # 处理第一个请求
            current_request = user_requests[0]
            remaining_requests = user_requests[1:]

            logger.info(f"[Planner] 处理用户请求: {current_request}")

            return {
                "user_requests": remaining_requests,
                "next_agent": "qa_handler",  # 转到问答处理
                "current_request": current_request,
                "iteration": iteration + 1
            }

        # 正常流程，决定下一步
        structure = state.get("structure", {})
        methodology = state.get("methodology", {})
        critique = state.get("critique", {})
        summary = state.get("summary", "")

        if not structure:
            return {"next_agent": "extractor", "iteration": iteration + 1}
        elif not methodology:
            return {"next_agent": "analyzer", "iteration": iteration + 1}
        elif not critique:
            return {"next_agent": "critic", "iteration": iteration + 1}
        elif not summary:
            return {"next_agent": "summarizer", "iteration": iteration + 1}
        else:
            return {"next_agent": "finish", "is_reading_complete": True}

    def run_stream(self, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """流式执行Planner逻辑"""
        iteration = state.get("iteration", 0)

        if iteration == 0:
            yield {"type": "agent_thinking", "agent": self.name, "content": "正在解析论文基本信息..."}

            # 提取元信息
            images = state.get("paper_images", [])
            first_pages = images[:2] if len(images) > 2 else images

            prompt = """请仔细查看这篇论文，提取基本信息并以JSON格式输出：
{
    "title": "论文标题",
    "authors": ["作者列表"],
    "abstract": "摘要",
    "keywords": ["关键词"]
}"""

            yield {"type": "agent_output_start", "agent": self.name}

            full_response = ""
            for chunk in self._invoke_llm_with_images_stream(
                self.get_system_prompt(),
                prompt,
                first_pages
            ):
                full_response += chunk
                yield {"type": "agent_output_chunk", "agent": self.name, "content": chunk}

            yield {"type": "agent_output_end", "agent": self.name}

            # 解析元信息
            metadata = {"title": "未能解析", "authors": [], "abstract": ""}
            try:
                json_start = full_response.find('{')
                json_end = full_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    metadata = json.loads(full_response[json_start:json_end])
            except:
                pass

            yield {
                "type": "planner_decision",
                "paper_metadata": metadata,
                "plan": ["extractor", "analyzer", "critic", "summarizer"]
            }

            yield {
                "type": "agent_complete",
                "agent": self.name,
                "result": {
                    "paper_metadata": metadata,
                    "next_agent": "extractor",
                    "iteration": 1
                }
            }

        else:
            # 决定下一步
            result = self.run(state)
            next_agent = result.get("next_agent", "finish")

            yield {
                "type": "planner_routing",
                "next_agent": next_agent
            }

            yield {
                "type": "agent_complete",
                "agent": self.name,
                "result": result
            }

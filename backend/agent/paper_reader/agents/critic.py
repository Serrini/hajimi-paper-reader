"""
Critic Agent - 创新点与局限性分析
"""
from typing import Dict, Any, Generator
from .base import BasePaperAgent
from config import Config
import logging

logger = logging.getLogger(__name__)


class CriticAgent(BasePaperAgent):
    """批判分析Agent - 评价创新点、发现局限性"""

    def __init__(self):
        super().__init__(
            name="Critic",
            description="批判性分析专家，负责评价论文的创新点、发现潜在局限性、提出改进建议"
        )
        # Critic使用稍高的temperature以获得更多视角
        llm_config = Config.get_llm_config()
        from langchain_openai import ChatOpenAI
        self.llm = ChatOpenAI(
            model=llm_config.get('model'),
            api_key=llm_config.get('api_key'),
            base_url=llm_config.get('api_url'),
            temperature=0.5,
            timeout=120,
            streaming=True
        )

    def get_system_prompt(self) -> str:
        return """你是一位严谨的学术论文评审专家，擅长批判性分析。

你的分析应该客观、专业、有建设性：

1. **创新点评价**
   - 论文声称的创新点是什么？
   - 这些创新是否真正有意义？
   - 创新的程度如何（增量式/突破式）？

2. **技术局限性**
   - 方法上有哪些局限？
   - 假设是否过强？
   - 适用范围如何？

3. **实验不足**
   - 实验设置有哪些不足？
   - 缺少哪些必要的对比或分析？
   - 结论是否过度泛化？

4. **潜在问题**
   - 可能的failure case？
   - 可扩展性问题？
   - 实际应用中的挑战？

5. **改进建议**
   - 如何改进现有方法？
   - 可能的研究方向？

请保持批判性但建设性的态度，用中文输出。"""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行批判分析"""
        images = state.get("paper_images", [])
        metadata = state.get("paper_metadata", {})
        structure = state.get("structure", {})
        methodology = state.get("methodology", {})

        logger.info(f"[Critic] 开始批判性分析")

        prompt = f"""请对这篇论文进行批判性分析。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 摘要：{metadata.get('abstract', '未知')}

方法分析摘要：
{methodology.get('analysis', '')[:1500]}

请从以下方面进行批判性评价：
1. 创新点是否真正有意义？
2. 方法有哪些局限性？
3. 实验设计有哪些不足？
4. 潜在问题和挑战？
5. 改进建议"""

        response = self._invoke_llm_with_images(
            self.get_system_prompt(),
            prompt,
            images
        )

        return {
            "critique": {
                "analysis": response,
                "innovations": self._extract_section(response, "创新"),
                "limitations": self._extract_section(response, "局限"),
                "suggestions": self._extract_section(response, "建议")
            },
            "execution_trace": [{
                "agent": self.name,
                "action": "批判分析",
                "summary": "完成创新点与局限性分析",
                "output_preview": response[:200]
            }]
        }

    def _extract_section(self, content: str, keyword: str) -> str:
        """提取特定章节内容"""
        lines = content.split('\n')
        result = []
        in_section = False

        for line in lines:
            if keyword in line and ('#' in line or '**' in line):
                in_section = True
                result.append(line)
            elif in_section:
                if line.startswith('#') or (line.startswith('**') and '**' in line[2:]):
                    break
                result.append(line)

        return '\n'.join(result)

    def run_stream(self, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """流式执行批判分析"""
        images = state.get("paper_images", [])
        metadata = state.get("paper_metadata", {})
        methodology = state.get("methodology", {})

        yield {"type": "agent_thinking", "agent": self.name, "content": "正在进行批判性分析..."}

        prompt = f"""请对这篇论文进行全面的批判性分析。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 摘要：{metadata.get('abstract', '未知')}

请从以下维度进行深入分析：

## 1. 创新点评价
- 论文声称的创新点是什么？
- 这些创新是否真正有意义？
- 创新程度如何？

## 2. 技术局限性
- 方法上有哪些局限？
- 假设条件是否过强？
- 适用范围如何？

## 3. 实验不足
- 实验设置有哪些问题？
- 缺少哪些必要的对比？
- 结论是否有过度泛化？

## 4. 潜在问题
- 可能的失败场景？
- 可扩展性问题？
- 实际应用挑战？

## 5. 改进建议
- 如何改进现有方法？
- 未来可能的研究方向？

请保持客观和建设性。"""

        yield {"type": "agent_output_start", "agent": self.name}

        full_response = ""
        for chunk in self._invoke_llm_with_images_stream(
            self.get_system_prompt(),
            prompt,
            images
        ):
            full_response += chunk
            yield {"type": "agent_output_chunk", "agent": self.name, "content": chunk}

        yield {"type": "agent_output_end", "agent": self.name}

        critique = {
            "analysis": full_response,
            "innovations": self._extract_section(full_response, "创新"),
            "limitations": self._extract_section(full_response, "局限"),
            "suggestions": self._extract_section(full_response, "建议")
        }

        yield {
            "type": "agent_complete",
            "agent": self.name,
            "result": {"critique": critique}
        }

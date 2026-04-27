"""
Analyzer Agent - 方法论深度分析
"""
from typing import Dict, Any, Generator
from .base import BasePaperAgent
import logging

logger = logging.getLogger(__name__)


class AnalyzerAgent(BasePaperAgent):
    """方法分析Agent - 深入分析研究方法和技术细节"""

    def __init__(self):
        super().__init__(
            name="Analyzer",
            description="方法论分析专家，负责深入分析论文的研究方法、技术细节和实验设计"
        )

    def get_system_prompt(self) -> str:
        return """你是一位资深的学术研究员，擅长深入分析论文的方法论。

你的分析应该包括：

1. **核心方法分析**
   - 方法的核心思想是什么？
   - 与现有方法有什么本质区别？
   - 技术创新点在哪里？

2. **算法/模型细节**
   - 关键组件和模块
   - 数学原理和公式
   - 实现细节

3. **实验设计评估**
   - 实验设置是否合理？
   - 基线对比是否充分？
   - 消融实验是否完整？

4. **结果分析**
   - 主要实验结果说明了什么？
   - 性能提升的原因是什么？
   - 结果的可信度如何？

请用专业但易懂的中文进行分析，使用Markdown格式。"""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行方法分析"""
        images = state.get("paper_images", [])
        metadata = state.get("paper_metadata", {})
        structure = state.get("structure", {})

        logger.info(f"[Analyzer] 开始分析方法论")

        prompt = f"""请深入分析这篇论文的研究方法。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 摘要：{metadata.get('abstract', '未知')}

已提取的结构信息：
{structure.get('raw_content', '')[:2000]}

请重点分析：
1. 核心方法的思想和创新
2. 技术实现的关键细节
3. 实验设计的合理性
4. 结果分析和可信度评估"""

        response = self._invoke_llm_with_images(
            self.get_system_prompt(),
            prompt,
            images
        )

        return {
            "methodology": {
                "analysis": response,
                "key_techniques": self._extract_key_points(response)
            },
            "execution_trace": [{
                "agent": self.name,
                "action": "方法分析",
                "summary": "完成方法论深度分析",
                "output_preview": response[:200]
            }]
        }

    def _extract_key_points(self, content: str) -> list:
        """提取关键技术点"""
        points = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                points.append(line[2:])
            elif line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                points.append(line[2:].strip())
        return points[:10]  # 最多10个

    def run_stream(self, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """流式执行方法分析"""
        images = state.get("paper_images", [])
        metadata = state.get("paper_metadata", {})
        structure = state.get("structure", {})

        yield {"type": "agent_thinking", "agent": self.name, "content": "正在深入分析研究方法..."}

        prompt = f"""请深入分析这篇论文的研究方法。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 摘要：{metadata.get('abstract', '未知')}

请从以下维度进行详细分析：

## 1. 核心方法分析
- 方法的核心思想是什么？
- 与现有方法的本质区别？
- 技术创新点在哪里？

## 2. 算法/模型细节
- 关键组件和模块是什么？
- 涉及的数学原理？
- 重要的实现细节？

## 3. 实验设计评估
- 实验设置是否合理？
- 基线方法对比是否充分？
- 消融实验设计如何？

## 4. 结果分析
- 主要实验结果说明了什么？
- 性能提升的关键因素？
- 结果的可靠性如何？"""

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

        methodology = {
            "analysis": full_response,
            "key_techniques": self._extract_key_points(full_response)
        }

        yield {
            "type": "agent_complete",
            "agent": self.name,
            "result": {"methodology": methodology}
        }

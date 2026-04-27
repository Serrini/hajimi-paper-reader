"""
Summarizer Agent - 生成精读总结
"""
from typing import Dict, Any, Generator
from .base import BasePaperAgent
import logging

logger = logging.getLogger(__name__)


class SummarizerAgent(BasePaperAgent):
    """总结Agent - 生成精读笔记和阅读报告"""

    def __init__(self):
        super().__init__(
            name="Summarizer",
            description="论文总结专家，负责生成精读笔记、提炼关键要点、给出阅读建议"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的学术论文阅读导师，擅长帮助学生高效理解论文。

你的总结应该：
1. 简洁明了，突出重点
2. 结构清晰，便于复习
3. 包含个人见解和阅读建议
4. 帮助读者快速掌握论文核心

输出格式：
## 📌 一句话总结
[用一句话概括论文核心贡献]

## 🎯 核心要点
[3-5个最重要的点]

## 💡 关键创新
[主要创新点]

## ⚠️ 注意事项
[阅读时需要注意的问题]

## 📖 阅读建议
[如何更好地理解这篇论文]

## 🔗 延伸阅读
[相关的研究方向或论文]

请用中文输出，使用emoji使内容更易读。"""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成精读总结"""
        metadata = state.get("paper_metadata", {})
        structure = state.get("structure", {})
        methodology = state.get("methodology", {})
        critique = state.get("critique", {})

        logger.info(f"[Summarizer] 生成精读总结")

        prompt = f"""请为这篇论文生成一份精读总结报告。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 作者：{', '.join(metadata.get('authors', []))}
- 摘要：{metadata.get('abstract', '未知')}

结构分析：
{structure.get('raw_content', '')[:1000]}

方法分析：
{methodology.get('analysis', '')[:1000]}

批判分析：
{critique.get('analysis', '')[:1000]}

请生成一份完整的精读报告，包括：
1. 一句话总结
2. 核心要点（3-5个）
3. 关键创新
4. 注意事项
5. 阅读建议
6. 延伸阅读建议"""

        response = self._invoke_llm(
            self.get_system_prompt(),
            prompt
        )

        return {
            "summary": response,
            "final_output": self._build_final_report(metadata, response),
            "is_reading_complete": True,
            "execution_trace": [{
                "agent": self.name,
                "action": "生成总结",
                "summary": "完成精读报告",
                "output_preview": response[:200]
            }]
        }

    def _build_final_report(self, metadata: Dict, summary: str) -> str:
        """构建最终报告"""
        title = metadata.get('title', '未知论文')
        authors = ', '.join(metadata.get('authors', ['未知作者']))

        return f"""# 📚 论文精读报告

## 论文信息
- **标题**：{title}
- **作者**：{authors}

---

{summary}

---
*本报告由AI论文精读助手自动生成*
"""

    def run_stream(self, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """流式生成精读总结"""
        metadata = state.get("paper_metadata", {})
        structure = state.get("structure", {})
        methodology = state.get("methodology", {})
        critique = state.get("critique", {})

        yield {"type": "agent_thinking", "agent": self.name, "content": "正在生成精读总结..."}

        prompt = f"""请为这篇论文生成一份精读总结报告。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 作者：{', '.join(metadata.get('authors', []))}
- 摘要：{metadata.get('abstract', '未知')}

请生成一份完整的精读报告，包括以下部分：

## 📌 一句话总结
[用一句话概括论文核心贡献]

## 🎯 核心要点
[列出3-5个最重要的点]

## 💡 关键创新
[主要创新点是什么]

## ⚠️ 注意事项
[阅读时需要注意的问题和局限性]

## 📖 阅读建议
[如何更好地理解这篇论文，建议先读哪些部分]

## 🔗 延伸阅读
[相关的研究方向或推荐论文]"""

        yield {"type": "agent_output_start", "agent": self.name}

        full_response = ""
        for chunk in self._invoke_llm_stream(
            self.get_system_prompt(),
            prompt
        ):
            full_response += chunk
            yield {"type": "agent_output_chunk", "agent": self.name, "content": chunk}

        yield {"type": "agent_output_end", "agent": self.name}

        final_report = self._build_final_report(metadata, full_response)

        yield {
            "type": "agent_complete",
            "agent": self.name,
            "result": {
                "summary": full_response,
                "final_output": final_report,
                "is_reading_complete": True
            }
        }

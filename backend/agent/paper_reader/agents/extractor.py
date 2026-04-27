"""
Extractor Agent - 论文结构提取
"""
from typing import Dict, Any, Generator
from .base import BasePaperAgent
import logging

logger = logging.getLogger(__name__)


class ExtractorAgent(BasePaperAgent):
    """结构提取Agent - 提取论文的各个部分"""

    def __init__(self):
        super().__init__(
            name="Extractor",
            description="论文结构提取专家，负责识别和提取论文的各个组成部分"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的学术论文阅读助手，擅长分析论文结构。

你的任务是仔细阅读论文图片，提取并整理论文的核心结构：

1. **引言 (Introduction)**
   - 研究背景
   - 研究动机
   - 主要贡献

2. **相关工作 (Related Work)**
   - 前人工作概述
   - 与本文的关系

3. **方法 (Methodology)**
   - 核心方法/模型
   - 关键技术点
   - 算法流程

4. **实验 (Experiments)**
   - 数据集
   - 评估指标
   - 主要结果

5. **结论 (Conclusion)**
   - 主要发现
   - 未来工作

请用简洁清晰的中文输出，使用Markdown格式组织内容。"""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行结构提取"""
        images = state.get("paper_images", [])
        metadata = state.get("paper_metadata", {})

        logger.info(f"[Extractor] 开始提取论文结构，共{len(images)}页")

        prompt = f"""请仔细阅读这篇论文的所有页面，提取论文的结构化内容。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 摘要：{metadata.get('abstract', '未知')}

请按照以下结构提取内容：
1. 引言部分：研究背景、动机、贡献
2. 相关工作：前人研究概述
3. 方法部分：核心技术和算法
4. 实验部分：数据集、指标、结果
5. 结论部分：主要发现

用Markdown格式输出。"""

        response = self._invoke_llm_with_images(
            self.get_system_prompt(),
            prompt,
            images
        )

        return {
            "structure": {
                "raw_content": response,
                "sections": self._parse_sections(response)
            },
            "execution_trace": [{
                "agent": self.name,
                "action": "结构提取",
                "summary": "完成论文结构分析",
                "output_preview": response[:200]
            }]
        }

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """解析各个章节"""
        sections = {
            "introduction": "",
            "related_work": "",
            "methodology": "",
            "experiments": "",
            "conclusion": ""
        }

        # 简单的章节分割逻辑
        current_section = None
        current_content = []

        for line in content.split('\n'):
            line_lower = line.lower()

            if '引言' in line or 'introduction' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "introduction"
                current_content = [line]
            elif '相关' in line or 'related' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "related_work"
                current_content = [line]
            elif '方法' in line or 'method' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "methodology"
                current_content = [line]
            elif '实验' in line or 'experiment' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "experiments"
                current_content = [line]
            elif '结论' in line or 'conclusion' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "conclusion"
                current_content = [line]
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def run_stream(self, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """流式执行结构提取（使用非流式API调用，分块返回模拟流式效果）"""
        images = state.get("paper_images", [])
        metadata = state.get("paper_metadata", {})

        yield {"type": "agent_thinking", "agent": self.name, "content": "正在分析论文结构..."}

        prompt = f"""请仔细阅读这篇论文的所有页面，提取论文的结构化内容。

论文信息：
- 标题：{metadata.get('title', '未知')}
- 摘要：{metadata.get('abstract', '未知')}

请按照以下结构提取并详细说明：

## 1. 引言 (Introduction)
- 研究背景是什么？
- 研究动机和要解决的问题？
- 本文的主要贡献？

## 2. 相关工作 (Related Work)
- 相关的前人工作有哪些？
- 现有方法的不足？

## 3. 方法 (Methodology)
- 核心方法/模型是什么？
- 关键技术点？
- 算法流程？

## 4. 实验 (Experiments)
- 使用的数据集？
- 评估指标？
- 主要实验结果？

## 5. 结论 (Conclusion)
- 主要发现？
- 局限性？
- 未来工作？"""

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

        structure = {
            "raw_content": full_response,
            "sections": self._parse_sections(full_response)
        }

        yield {
            "type": "agent_complete",
            "agent": self.name,
            "result": {"structure": structure}
        }

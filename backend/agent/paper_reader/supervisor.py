"""
Supervisor Agent - 动态路由决策者
"""

import logging
from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config import Config
from .state import PaperReaderState

logger = logging.getLogger(__name__)


# 可用的 Worker 类型
WorkerType = Literal["planner", "extractor", "analyzer", "critic", "summarizer", "FINISH"]


class RouteDecision(BaseModel):
    """Supervisor 的结构化决策输出"""

    next_workers: List[WorkerType] = Field(
        description="选择下一步执行的 Agent，支持多选并行，完成则选 FINISH"
    )
    reasoning: str = Field(
        description="决策理由（简短说明）"
    )


# Worker 信息
WORKER_INFO = {
    "planner": {
        "description": "提取论文元信息（标题、作者、摘要、关键词）",
        "required": True,
        "order": 1,
    },
    "extractor": {
        "description": "提取论文结构（引言、方法、实验、结论）",
        "required": True,
        "order": 2,
    },
    "analyzer": {
        "description": "深度分析方法论和技术细节",
        "required": True,
        "order": 3,
        "can_parallel_with": ["critic"],
    },
    "critic": {
        "description": "分析创新点、局限性、改进方向",
        "required": True,
        "order": 3,
        "can_parallel_with": ["analyzer"],
    },
    "summarizer": {
        "description": "生成综合精读总结",
        "required": True,
        "order": 4,
        "depends_on": ["extractor", "analyzer", "critic"],
    },
}


class SupervisorAgent:
    """
    Supervisor Agent

    职责：
    1. 分析当前状态
    2. 决定下一步执行哪些 Worker（支持并行）
    3. 决定何时结束
    """

    def __init__(self):
        llm_config = Config.get_llm_config()

        # 使用低温度保证决策稳定
        self.llm = ChatOpenAI(
            model=llm_config.get('model'),
            api_key=llm_config.get('api_key'),
            base_url=llm_config.get('api_url'),
            temperature=0.1,
            timeout=60,
            max_retries=2
        ).with_structured_output(RouteDecision)

        self._init_prompt()

    def _init_prompt(self):
        """初始化决策 Prompt"""
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是论文精读任务的 Supervisor，负责协调多个 Worker 完成论文分析。

## 可用的 Worker

{workers_description}

## 决策规则

1. **顺序约束**：
   - planner 必须首先执行
   - summarizer 必须最后执行（依赖其他分析结果）

2. **并行优化**：
   - analyzer 和 critic 可以并行执行

3. **完成条件**：
   - 所有必需 Worker 都已完成
   - 已生成 summary
   - 返回 ["FINISH"]

## 输出格式

返回 next_workers 列表：
- 单个执行：["extractor"]
- 并行执行：["analyzer", "critic"]
- 完成：["FINISH"]
"""),
            ("human", """## 当前状态

{state_summary}

请决定下一步执行哪些 Worker。""")
        ])

    def _build_workers_description(self) -> str:
        """构建 Worker 描述"""
        lines = []
        for name, info in WORKER_INFO.items():
            parallel = f"（可与 {info.get('can_parallel_with', [])} 并行）" if info.get('can_parallel_with') else ""
            lines.append(f"- {name}: {info['description']} {parallel}")
        return "\n".join(lines)

    def _build_state_summary(self, state: PaperReaderState) -> str:
        """构建状态摘要"""
        completed = state.get("completed_agents", [])

        lines = [
            f"论文: {state.get('paper_name', '未知')}",
            f"迭代: {state.get('iteration', 0)}",
            f"已完成: {', '.join(completed) if completed else '无'}",
            "",
            "各 Worker 状态:",
        ]

        # 检查各 Worker 状态
        if state.get("paper_metadata"):
            title = state["paper_metadata"].get("title", "未知")[:30]
            lines.append(f"  planner: ✅ ({title}...)")
        else:
            lines.append("  planner: ⏳")

        lines.append(f"  extractor: {'✅' if state.get('structure') else '⏳'}")
        lines.append(f"  analyzer: {'✅' if state.get('methodology') else '⏳'}")
        lines.append(f"  critic: {'✅' if state.get('critique') else '⏳'}")
        lines.append(f"  summarizer: {'✅' if state.get('summary') else '⏳'}")

        return "\n".join(lines)

    async def decide(self, state: PaperReaderState) -> RouteDecision:
        """
        根据当前状态做出路由决策

        Returns:
            RouteDecision: 包含 next_workers 和 reasoning
        """
        workers_desc = self._build_workers_description()
        state_summary = self._build_state_summary(state)

        chain = self.prompt | self.llm

        try:
            decision = await chain.ainvoke({
                "workers_description": workers_desc,
                "state_summary": state_summary
            })

            logger.info(f"[Supervisor] 决策: {decision.next_workers} | {decision.reasoning}")
            return decision

        except Exception as e:
            logger.error(f"[Supervisor] 决策失败: {e}, 结束！！！")
            return RouteDecision(next_workers=["FINISH"], reasoning="Fallback: 所有 Worker 已完成")


# Supervisor 单例
_supervisor_instance = None


def get_supervisor() -> SupervisorAgent:
    """获取 Supervisor 单例"""
    global _supervisor_instance
    if _supervisor_instance is None:
        _supervisor_instance = SupervisorAgent()
    return _supervisor_instance


async def supervisor_node(state: PaperReaderState) -> Dict[str, Any]:
    """
    Supervisor 节点

    分析状态，返回 next_steps 供路由器使用
    """
    supervisor = get_supervisor()
    decision = await supervisor.decide(state)

    return {
        "next_steps": decision.next_workers,
        "iteration": state.get("iteration", 0) + 1
    }

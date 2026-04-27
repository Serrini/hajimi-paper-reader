"""
论文精读Agent集合
"""
from .base import BasePaperAgent
from .planner import PlannerAgent
from .extractor import ExtractorAgent
from .analyzer import AnalyzerAgent
from .critic import CriticAgent
from .summarizer import SummarizerAgent

__all__ = [
    'BasePaperAgent',
    'PlannerAgent',
    'ExtractorAgent',
    'AnalyzerAgent',
    'CriticAgent',
    'SummarizerAgent'
]

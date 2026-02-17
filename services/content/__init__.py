"""
FactoryLM Content Services
==========================
Content evaluation, generation, and competitive positioning.

Components:
- IndustrialContentJudge: Evaluates content against top industrial channels
- create_competitive_analysis_prompt: Generates LLM prompts for content creation
"""

from .industrial_content_judge import (
    IndustrialContentJudge,
    create_competitive_analysis_prompt,
    TOP_CHANNELS,
    FACTORYLM_CAPABILITIES
)

__all__ = [
    "IndustrialContentJudge",
    "create_competitive_analysis_prompt",
    "TOP_CHANNELS",
    "FACTORYLM_CAPABILITIES"
]

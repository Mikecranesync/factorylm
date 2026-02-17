"""
FactoryLM Content Services
==========================
Content evaluation, generation, and competitive positioning.

Components:
- IndustrialContentJudge: Evaluates content against top industrial channels
  - evaluate_content(): Score scripts against competitors
  - evaluate_visuals(): Score images/presentation quality
  - evaluate_full_production(): Combined script + visual evaluation
- create_competitive_analysis_prompt: Generates LLM prompts for content creation

Usage:
    from services.content import IndustrialContentJudge

    judge = IndustrialContentJudge()

    # Evaluate script only
    script_result = judge.evaluate_content("Your script here...")

    # Evaluate images only
    visual_result = judge.evaluate_visuals(
        images=["plc_panel.jpg", "hmi_error.png"],
        script="Optional script for alignment check",
        audio_duration=45.0
    )

    # Evaluate full production
    full_result = judge.evaluate_full_production(
        script="Your script",
        images=["img1.jpg", "img2.jpg", "img3.jpg"],
        audio_duration=45.0,
        topic="Motor troubleshooting"
    )
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

"""
FactoryLM Video Generation Pipeline
====================================
AI-powered video generation using NVIDIA Cosmos-Predict2.

Pipeline:
    Content Judge (8/10+) -> Cosmos-Predict2 -> Quality Validator -> Post-Processor -> Distribution

Components:
- CosmosVideoGenerator: Generates video from Content Judge output using Cosmos-Predict2
- VideoQualityValidator: Validates generated video quality using Cosmos-Reason1
- VideoPostProcessor: Adds branding, audio mix, compression for final output
- DistributionManager: Multi-platform deployment (YouTube, GitHub, competition)

Usage:
    from services.video import CosmosVideoGenerator, VideoQualityValidator

    # Generate video from scored content
    generator = CosmosVideoGenerator(model_size="14B")
    result = await generator.generate_from_judge_output(judge_output)

    # Validate quality
    validator = VideoQualityValidator()
    validation = await validator.validate(result["video_path"], judge_output)

    if validation["passed"]:
        # Post-process and distribute
        processor = VideoPostProcessor()
        final = processor.process(result["video_path"], audio_path)

Competition:
    NVIDIA Cosmos Cookoff 2026 - Deadline Feb 26, 2026
"""

from .cosmos_generator import (
    CosmosVideoGenerator,
    VideoGenerationError,
    VideoSegment,
)
from .quality_validator import (
    VideoQualityValidator,
    QualityValidationError,
)
from .post_processor import (
    VideoPostProcessor,
    PostProcessingError,
)
from .distribution import (
    DistributionManager,
    DistributionError,
)

__all__ = [
    # Generator
    "CosmosVideoGenerator",
    "VideoGenerationError",
    "VideoSegment",
    # Validator
    "VideoQualityValidator",
    "QualityValidationError",
    # Post-processor
    "VideoPostProcessor",
    "PostProcessingError",
    # Distribution
    "DistributionManager",
    "DistributionError",
]

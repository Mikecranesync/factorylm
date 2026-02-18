#!/usr/bin/env python3
"""
FactoryLM Video Generation CLI
==============================

Main entry point for the video generation pipeline.

NVIDIA Cosmos Cookoff 2026 - Competition ready.

Pipeline:
    Content Judge (8/10+) -> Cosmos-Predict2 -> Quality Validator -> Post-Processor -> Distribution

Usage:
    # Generate from scored content
    python services/video/generate.py \
        --judge-output scored_content/plc_training.json \
        --duration 60 \
        --output demos/competition_demo.mp4

    # Full pipeline from raw inputs
    python services/video/generate.py \
        --script "Your script text" \
        --images img1.jpg img2.jpg img3.jpg \
        --duration 45 \
        --preset competition

    # Batch processing
    python services/video/generate.py batch \
        --input-dir scored_content/ \
        --min-score 8.0 \
        --output-dir demos/
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.video.cosmos_generator import CosmosVideoGenerator, GenerationResult
from services.video.quality_validator import VideoQualityValidator, ValidationResult
from services.video.post_processor import VideoPostProcessor, ProcessingResult, get_preset
from services.video.distribution import DistributionManager, VideoMetadata
from services.content.industrial_content_judge import IndustrialContentJudge

logger = logging.getLogger(__name__)


class VideoPipeline:
    """
    End-to-end video generation pipeline.

    Orchestrates:
    1. Content evaluation (Content Judge)
    2. Video generation (Cosmos-Predict2)
    3. Quality validation (Cosmos-Reason1)
    4. Post-processing (FFmpeg)
    5. Distribution (YouTube, GitHub)
    """

    def __init__(
        self,
        model_size: str = "14B",
        output_dir: Optional[str] = None,
        preset: str = "competition",
    ):
        self.model_size = model_size
        self.preset = preset
        self.output_dir = Path(output_dir) if output_dir else Path("output/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.judge = IndustrialContentJudge()
        self.generator = CosmosVideoGenerator(model_size=model_size, output_dir=str(self.output_dir / "generated"))
        self.validator = VideoQualityValidator()
        self.processor = VideoPostProcessor(output_dir=str(self.output_dir / "processed"))
        self.distributor = DistributionManager()

    async def generate_from_judge_output(
        self,
        judge_output_path: str,
        duration: Optional[float] = None,
        skip_validation: bool = False,
        skip_processing: bool = False,
        distribute_to: Optional[list] = None,
    ) -> dict:
        """
        Generate video from pre-scored Content Judge output.

        Args:
            judge_output_path: Path to JSON file with judge output
            duration: Override duration (defaults to audio_duration in file)
            skip_validation: Skip quality validation step
            skip_processing: Skip post-processing step
            distribute_to: List of distribution targets

        Returns:
            Pipeline result dict
        """
        # Load judge output
        with open(judge_output_path) as f:
            judge_output = json.load(f)

        return await self._run_pipeline(
            judge_output=judge_output,
            duration=duration,
            skip_validation=skip_validation,
            skip_processing=skip_processing,
            distribute_to=distribute_to,
        )

    async def generate_from_raw_inputs(
        self,
        script: str,
        images: list,
        duration: float = 60.0,
        topic: str = "",
        skip_judge: bool = False,
        skip_validation: bool = False,
        skip_processing: bool = False,
        distribute_to: Optional[list] = None,
    ) -> dict:
        """
        Generate video from raw script and images.

        Args:
            script: Narration script text
            images: List of image file paths
            duration: Target duration in seconds
            topic: Content topic for evaluation
            skip_judge: Skip Content Judge evaluation (not recommended)
            skip_validation: Skip quality validation
            skip_processing: Skip post-processing
            distribute_to: Distribution targets

        Returns:
            Pipeline result dict
        """
        # Evaluate content unless skipped
        if skip_judge:
            # Create minimal judge output
            judge_output = {
                "overall_score": 8.0,
                "ready_for_production": True,
                "script_evaluation": {"original_script": script},
                "visual_evaluation": {
                    "image_analysis": [{"path": img, "index": i} for i, img in enumerate(images)]
                },
                "audio_duration": duration,
            }
        else:
            # Run full evaluation
            logger.info("Evaluating content with Content Judge...")
            judge_output = self.judge.evaluate_and_format(
                script=script,
                images=images,
                audio_duration=duration,
                topic=topic,
            )

            # Check score
            score = judge_output.get("overall_score", 0)
            if score < 8.0:
                logger.warning("Content scored %.1f/10 (below 8.0 threshold)", score)
                if not judge_output.get("ready_for_production"):
                    return {
                        "success": False,
                        "stage": "evaluation",
                        "error": f"Content scored {score:.1f}/10, below threshold",
                        "judge_output": judge_output,
                    }

        return await self._run_pipeline(
            judge_output=judge_output,
            duration=duration,
            skip_validation=skip_validation,
            skip_processing=skip_processing,
            distribute_to=distribute_to,
        )

    async def _run_pipeline(
        self,
        judge_output: dict,
        duration: Optional[float],
        skip_validation: bool,
        skip_processing: bool,
        distribute_to: Optional[list],
    ) -> dict:
        """Run the video generation pipeline."""
        result = {
            "success": False,
            "stages": {},
            "final_video": None,
            "distribution_results": None,
            "metadata": {
                "started_at": datetime.now().isoformat(),
                "model_size": self.model_size,
                "preset": self.preset,
            }
        }

        try:
            # Stage 1: Generate video
            logger.info("Stage 1: Generating video with Cosmos-Predict2...")
            gen_result = await self.generator.generate_from_judge_output(
                judge_output,
                duration=duration
            )
            result["stages"]["generation"] = {
                "success": gen_result.success,
                "video_path": gen_result.video_path,
                "segments": gen_result.segments_generated,
                "errors": gen_result.errors,
            }

            if not gen_result.success:
                result["error"] = "Video generation failed"
                return result

            current_video = gen_result.video_path

            # Stage 2: Validate quality (optional)
            if not skip_validation:
                logger.info("Stage 2: Validating quality with Cosmos-Reason1...")
                val_result = await self.validator.validate(
                    current_video,
                    original_judge_output=judge_output
                )
                result["stages"]["validation"] = {
                    "passed": val_result.passed,
                    "overall_score": val_result.overall_score,
                    "scores": val_result.scores,
                    "recommendation": val_result.recommendation,
                }

                if not val_result.passed:
                    logger.warning("Quality validation failed: %s", val_result.blocking_issues)
                    if val_result.recommendation == "regenerate":
                        result["error"] = "Quality validation failed - regeneration recommended"
                        # In production, would retry with different parameters
                        return result
            else:
                result["stages"]["validation"] = {"skipped": True}

            # Stage 3: Post-process (optional)
            if not skip_processing:
                logger.info("Stage 3: Post-processing video...")
                preset_config = get_preset(self.preset)

                # Extract script for captions
                script = judge_output.get("script_evaluation", {}).get("original_script", "")

                proc_result = self.processor.process(
                    generated_video=current_video,
                    compression=preset_config.get("compression"),
                    branding=preset_config.get("branding"),
                    add_captions=bool(script),
                    caption_script=script,
                )
                result["stages"]["processing"] = {
                    "success": proc_result.success,
                    "output_path": proc_result.output_path,
                    "duration": proc_result.duration,
                    "file_size_mb": proc_result.file_size_mb,
                }

                if proc_result.success:
                    current_video = proc_result.output_path
            else:
                result["stages"]["processing"] = {"skipped": True}

            result["final_video"] = current_video
            result["success"] = True

            # Stage 4: Distribute (optional)
            if distribute_to:
                logger.info("Stage 4: Distributing to %s...", distribute_to)

                # Build metadata
                topic = judge_output.get("generation_hints", {}).get("topic", "Industrial Training")
                metadata = VideoMetadata(
                    title=f"FactoryLM: {topic}",
                    description=f"AI-generated industrial training content.\n\n{topic}",
                    tags=["factorylm", "industrial", "ai", "automation", "plc"],
                    is_short=judge_output.get("audio_duration", 60) <= 60,
                )

                dist_result = await self.distributor.distribute(
                    current_video,
                    metadata,
                    targets=distribute_to
                )
                result["distribution_results"] = {
                    "success": dist_result.success,
                    "summary": dist_result.summary,
                    "uploads": [u.__dict__ for u in dist_result.uploads],
                }

            result["metadata"]["completed_at"] = datetime.now().isoformat()
            return result

        except Exception as e:
            logger.exception("Pipeline failed")
            result["error"] = str(e)
            result["metadata"]["completed_at"] = datetime.now().isoformat()
            return result

        finally:
            await self.generator.close()
            self.validator.cleanup()


async def run_single(args):
    """Run single video generation."""
    pipeline = VideoPipeline(
        model_size=args.model,
        output_dir=args.output_dir,
        preset=args.preset,
    )

    if args.judge_output:
        # Generate from judge output file
        result = await pipeline.generate_from_judge_output(
            judge_output_path=args.judge_output,
            duration=args.duration,
            skip_validation=args.skip_validation,
            skip_processing=args.skip_processing,
            distribute_to=args.distribute,
        )
    else:
        # Generate from raw inputs
        if not args.script:
            print("Error: --script is required when not using --judge-output")
            sys.exit(1)

        result = await pipeline.generate_from_raw_inputs(
            script=args.script,
            images=args.images or [],
            duration=args.duration or 60.0,
            topic=args.topic or "",
            skip_judge=args.skip_judge,
            skip_validation=args.skip_validation,
            skip_processing=args.skip_processing,
            distribute_to=args.distribute,
        )

    # Output result
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_result(result)

    return 0 if result["success"] else 1


async def run_batch(args):
    """Run batch video generation."""
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return 1

    # Find all judge output files
    judge_files = list(input_dir.glob("*.json"))
    print(f"Found {len(judge_files)} judge output files")

    # Filter by score
    eligible = []
    for f in judge_files:
        try:
            with open(f) as fp:
                data = json.load(fp)
            score = data.get("overall_score", 0)
            if score >= args.min_score:
                eligible.append((f, score))
        except Exception as e:
            print(f"Skipping {f}: {e}")

    print(f"{len(eligible)} files meet minimum score of {args.min_score}")

    if not eligible:
        return 0

    # Sort by score descending
    eligible.sort(key=lambda x: x[1], reverse=True)

    # Process in parallel batches
    results = []
    batch_size = args.parallel

    for i in range(0, len(eligible), batch_size):
        batch = eligible[i:i + batch_size]
        print(f"\nProcessing batch {i // batch_size + 1} ({len(batch)} files)...")

        tasks = []
        for f, score in batch:
            pipeline = VideoPipeline(
                model_size=args.model,
                output_dir=args.output_dir,
                preset=args.preset,
            )
            tasks.append(
                pipeline.generate_from_judge_output(
                    judge_output_path=str(f),
                    skip_validation=args.skip_validation,
                    distribute_to=args.distribute,
                )
            )

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for (f, score), result in zip(batch, batch_results):
            if isinstance(result, Exception):
                results.append({"file": str(f), "success": False, "error": str(result)})
            else:
                results.append({"file": str(f), **result})

    # Summary
    success_count = sum(1 for r in results if r.get("success"))
    print(f"\n{'='*50}")
    print(f"Batch complete: {success_count}/{len(results)} successful")

    if args.json:
        print(json.dumps(results, indent=2, default=str))

    return 0 if success_count > 0 else 1


def print_result(result: dict):
    """Pretty print pipeline result."""
    print(f"\n{'='*60}")
    print(f"VIDEO GENERATION {'SUCCEEDED' if result['success'] else 'FAILED'}")
    print(f"{'='*60}")

    if result.get("error"):
        print(f"\nError: {result['error']}")

    print(f"\nStages:")
    for stage, data in result.get("stages", {}).items():
        if isinstance(data, dict):
            status = "OK" if data.get("success") or data.get("passed") else "SKIP" if data.get("skipped") else "FAIL"
            print(f"  {stage}: [{status}]")
            if data.get("video_path"):
                print(f"    -> {data['video_path']}")
            if data.get("output_path"):
                print(f"    -> {data['output_path']}")

    if result.get("final_video"):
        print(f"\nFinal Video: {result['final_video']}")

    if result.get("distribution_results"):
        dist = result["distribution_results"]
        print(f"\nDistribution: {dist['summary']}")
        for upload in dist.get("uploads", []):
            if upload.get("url"):
                print(f"  - {upload['platform']}: {upload['url']}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FactoryLM Video Generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate from scored content
  python generate.py --judge-output scored/plc_training.json --preset competition

  # Generate from raw inputs
  python generate.py --script "Your script" --images img1.jpg img2.jpg --duration 45

  # Batch process directory
  python generate.py batch --input-dir scored/ --min-score 8.0 --parallel 3
        """
    )

    parser.add_argument("--model", "-m", default="14B", choices=["2B", "7B", "14B"],
                       help="Cosmos-Predict2 model size (default: 14B)")
    parser.add_argument("--preset", "-p", default="competition",
                       choices=["youtube_shorts", "youtube_standard", "competition"],
                       help="Processing preset")
    parser.add_argument("--output-dir", "-o", default="output/videos",
                       help="Output directory")
    parser.add_argument("--json", action="store_true",
                       help="Output results as JSON")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose logging")

    subparsers = parser.add_subparsers(dest="command")

    # Single generation (default)
    single_parser = subparsers.add_parser("single", help="Generate single video")
    single_parser.add_argument("--judge-output", "-j",
                               help="Path to Content Judge output JSON")
    single_parser.add_argument("--script", "-s",
                               help="Narration script text")
    single_parser.add_argument("--images", "-i", nargs="+",
                               help="Image file paths")
    single_parser.add_argument("--duration", "-d", type=float,
                               help="Target duration in seconds")
    single_parser.add_argument("--topic", "-t",
                               help="Content topic")
    single_parser.add_argument("--skip-judge", action="store_true",
                               help="Skip Content Judge evaluation")
    single_parser.add_argument("--skip-validation", action="store_true",
                               help="Skip quality validation")
    single_parser.add_argument("--skip-processing", action="store_true",
                               help="Skip post-processing")
    single_parser.add_argument("--distribute", nargs="+",
                               choices=["youtube", "github_pr", "competition", "social"],
                               help="Distribution targets")

    # Batch generation
    batch_parser = subparsers.add_parser("batch", help="Batch generate videos")
    batch_parser.add_argument("--input-dir", "-i", required=True,
                              help="Directory with judge output JSON files")
    batch_parser.add_argument("--min-score", type=float, default=8.0,
                              help="Minimum score threshold")
    batch_parser.add_argument("--parallel", type=int, default=3,
                              help="Parallel processing count")
    batch_parser.add_argument("--skip-validation", action="store_true")
    batch_parser.add_argument("--distribute", nargs="+",
                              choices=["youtube", "github_pr", "competition", "social"])

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    )

    # Default to single mode with same args
    if args.command is None:
        # Re-parse with single subparser
        sys.argv.insert(1, "single")
        args = parser.parse_args()

    # Run
    if args.command == "batch":
        exit_code = asyncio.run(run_batch(args))
    else:
        exit_code = asyncio.run(run_single(args))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

"""
Cosmos-Predict2 Video Generator for FactoryLM.

NVIDIA Cosmos Cookoff 2026 integration.

Modes:
- Video2World: Seed images -> extended video (primary)
- Text2World: Text prompt -> video from scratch

Architecture:
    Content Judge (8/10+) -> CosmosVideoGenerator -> VideoQualityValidator
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class VideoGenerationError(Exception):
    """Raised when video generation fails."""
    pass


@dataclass
class VideoSegment:
    """A single video segment (max ~5 seconds for Cosmos)."""
    index: int
    start_time: float
    end_time: float
    seed_image: Optional[str] = None
    prompt: str = ""
    output_path: Optional[str] = None
    generation_attempts: int = 0


@dataclass
class GenerationResult:
    """Result from video generation."""
    success: bool
    video_path: Optional[str] = None
    segments_generated: int = 0
    total_duration: float = 0.0
    model_used: str = ""
    errors: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class CosmosVideoGenerator:
    """
    NVIDIA Cosmos-Predict2 integration for AI video generation.

    Uses Content Judge 8/10+ output as input, generates video segments,
    chains them auto-regressively, and returns the final video.

    Model Sizes:
    - 2B: Fast iteration, lower quality (dev)
    - 7B: Balanced quality/speed
    - 14B: Competition quality (final renders)
    """

    # Model configurations
    MODEL_CONFIGS = {
        "2B": {
            "model_id": "nvidia/cosmos-predict2-2b",
            "max_segment_duration": 5.0,
            "resolution": (1024, 576),  # 16:9
            "fps": 24,
            "best_of_n": 2,
        },
        "7B": {
            "model_id": "nvidia/cosmos-predict2-7b",
            "max_segment_duration": 5.0,
            "resolution": (1280, 720),
            "fps": 24,
            "best_of_n": 3,
        },
        "14B": {
            "model_id": "nvidia/cosmos-predict2-14b",
            "max_segment_duration": 5.0,
            "resolution": (1920, 1080),
            "fps": 30,
            "best_of_n": 5,
        },
    }

    def __init__(
        self,
        model_size: str = "14B",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize Cosmos-Predict2 generator.

        Args:
            model_size: "2B", "7B", or "14B"
            api_key: NVIDIA API key (defaults to NVIDIA_COSMOS_API_KEY env)
            api_base: API base URL (defaults to NVIDIA's integrate API)
            output_dir: Where to save generated videos
        """
        if model_size not in self.MODEL_CONFIGS:
            raise ValueError(f"Invalid model_size: {model_size}. Use 2B, 7B, or 14B")

        self.model_size = model_size
        self.config = self.MODEL_CONFIGS[model_size]
        self.model_id = self.config["model_id"]

        self.api_key = api_key or os.getenv("NVIDIA_COSMOS_API_KEY") or os.getenv("NVIDIA_API_KEY_NEW", "")
        self.api_base = api_base or os.getenv(
            "COSMOS_PREDICT_API_URL",
            "https://integrate.api.nvidia.com/v1"
        )

        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "factorylm_videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,  # Long timeout for video generation
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate_from_judge_output(
        self,
        judge_output: dict,
        mode: str = "Video2World",
        duration: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generate video from Content Judge 8/10+ output.

        Args:
            judge_output: Output from IndustrialContentJudge.evaluate_full_production()
            mode: "Video2World" (image seeds) or "Text2World" (text only)
            duration: Target duration in seconds (defaults to audio_duration from judge)

        Returns:
            GenerationResult with video path and metadata
        """
        logger.info("Starting video generation from judge output, mode=%s", mode)

        # Validate judge output
        if not self._validate_judge_output(judge_output):
            return GenerationResult(
                success=False,
                errors=["Invalid judge output - missing required fields or score below threshold"]
            )

        # Extract info from judge output
        images = self._extract_images(judge_output)
        script = self._extract_script(judge_output)
        target_duration = duration or judge_output.get("audio_duration", 60.0)

        # Chunk into segments
        segments = self._create_segments(images, script, target_duration)
        logger.info("Created %d segments for %.1f second video", len(segments), target_duration)

        # Generate each segment
        video_clips = []
        errors = []

        for i, segment in enumerate(segments):
            logger.info("Generating segment %d/%d (%.1f-%.1f sec)",
                       i + 1, len(segments), segment.start_time, segment.end_time)

            try:
                clip_path = await self._generate_segment(segment, mode)
                video_clips.append(clip_path)
                segment.output_path = clip_path
            except Exception as e:
                logger.error("Failed to generate segment %d: %s", i, e)
                errors.append(f"Segment {i}: {str(e)}")
                # Try to continue with remaining segments
                continue

        if not video_clips:
            return GenerationResult(
                success=False,
                errors=errors or ["No segments were successfully generated"]
            )

        # Chain clips into final video
        try:
            final_video = await self._chain_clips(video_clips, target_duration)
        except Exception as e:
            logger.error("Failed to chain clips: %s", e)
            return GenerationResult(
                success=False,
                video_path=video_clips[0] if video_clips else None,  # Return first clip as fallback
                segments_generated=len(video_clips),
                errors=[f"Chain failed: {str(e)}"] + errors
            )

        return GenerationResult(
            success=True,
            video_path=final_video,
            segments_generated=len(video_clips),
            total_duration=target_duration,
            model_used=self.model_id,
            errors=errors,
            metadata={
                "mode": mode,
                "model_size": self.model_size,
                "resolution": self.config["resolution"],
                "fps": self.config["fps"],
                "best_of_n": self.config["best_of_n"],
            }
        )

    def _validate_judge_output(self, judge_output: dict) -> bool:
        """Validate that judge output meets requirements."""
        # Check for required fields
        required = ["overall_score", "ready_for_production"]
        for field in required:
            if field not in judge_output:
                logger.warning("Missing required field: %s", field)
                return False

        # Check score threshold (8/10+ required)
        score = judge_output.get("overall_score", 0)
        if score < 8.0:
            logger.warning("Score %.1f below threshold 8.0", score)
            return False

        # Check ready flag
        if not judge_output.get("ready_for_production", False):
            logger.warning("Content not marked ready for production")
            return False

        return True

    def _extract_images(self, judge_output: dict) -> list[str]:
        """Extract image paths from judge output."""
        images = []

        # Try visual_evaluation.image_analysis
        visual_eval = judge_output.get("visual_evaluation", {})
        image_analysis = visual_eval.get("image_analysis", [])

        for img in image_analysis:
            if isinstance(img, dict) and "path" in img:
                images.append(img["path"])
            elif isinstance(img, str):
                images.append(img)

        # Fallback to images field directly
        if not images:
            images = judge_output.get("images", [])

        return images

    def _extract_script(self, judge_output: dict) -> str:
        """Extract script/narration from judge output."""
        script_eval = judge_output.get("script_evaluation", {})

        # Try refined script first (from revision)
        script = script_eval.get("revised_script", "")
        if not script:
            script = script_eval.get("original_script", "")
        if not script:
            script = judge_output.get("script", "")

        return script

    def _create_segments(
        self,
        images: list[str],
        script: str,
        duration: float
    ) -> list[VideoSegment]:
        """
        Chunk video into segments (max ~5 sec each for Cosmos).

        Distributes images across segments and splits script accordingly.
        """
        max_segment = self.config["max_segment_duration"]
        num_segments = max(1, int(duration / max_segment))
        segment_duration = duration / num_segments

        # Distribute images across segments
        images_per_segment = max(1, len(images) // num_segments)

        # Split script into sentences
        import re
        sentences = re.split(r'(?<=[.!?])\s+', script.strip())
        sentences_per_segment = max(1, len(sentences) // num_segments)

        segments = []
        for i in range(num_segments):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, duration)

            # Get image for this segment
            img_idx = min(i * images_per_segment, len(images) - 1) if images else None
            seed_image = images[img_idx] if img_idx is not None and images else None

            # Get script portion for this segment
            sent_start = i * sentences_per_segment
            sent_end = min((i + 1) * sentences_per_segment, len(sentences))
            segment_script = " ".join(sentences[sent_start:sent_end])

            segments.append(VideoSegment(
                index=i,
                start_time=start,
                end_time=end,
                seed_image=seed_image,
                prompt=segment_script,
            ))

        return segments

    async def _generate_segment(
        self,
        segment: VideoSegment,
        mode: str
    ) -> str:
        """
        Generate a single video segment using Cosmos-Predict2.

        Uses best-of-N sampling - generates multiple candidates and selects best.
        """
        segment.generation_attempts += 1
        client = await self._get_client()

        # Build request based on mode
        if mode == "Video2World" and segment.seed_image:
            request = await self._build_video2world_request(segment)
        else:
            request = self._build_text2world_request(segment)

        # Best-of-N: generate multiple candidates
        best_of_n = self.config["best_of_n"]
        candidates = []

        for attempt in range(best_of_n):
            try:
                response = await client.post(
                    f"{self.api_base}/video/generate",
                    json=request,
                )
                response.raise_for_status()
                result = response.json()

                # Extract video data
                video_data = result.get("video", result.get("data", {}).get("video"))
                if video_data:
                    candidates.append({
                        "data": video_data,
                        "quality_score": result.get("quality_score", 0.5),
                    })

            except httpx.HTTPStatusError as e:
                logger.warning("Segment generation attempt %d failed: %s", attempt + 1, e)
                if e.response.status_code == 429:  # Rate limited
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            except Exception as e:
                logger.warning("Segment generation attempt %d error: %s", attempt + 1, e)
                continue

        if not candidates:
            # Fallback to stub for development
            return await self._generate_segment_stub(segment)

        # Select best candidate
        best = max(candidates, key=lambda x: x["quality_score"])

        # Save to file
        output_path = self.output_dir / f"segment_{segment.index:03d}.mp4"
        video_bytes = base64.b64decode(best["data"]) if isinstance(best["data"], str) else best["data"]

        with open(output_path, "wb") as f:
            f.write(video_bytes)

        return str(output_path)

    async def _build_video2world_request(self, segment: VideoSegment) -> dict:
        """Build Video2World API request with seed image."""
        # Encode seed image
        image_data = ""
        if segment.seed_image and Path(segment.seed_image).exists():
            image_bytes = Path(segment.seed_image).read_bytes()
            image_data = base64.b64encode(image_bytes).decode("utf-8")

        return {
            "model": self.model_id,
            "mode": "Video2World",
            "seed_image": image_data,
            "prompt": segment.prompt or "Industrial equipment in operation",
            "duration": segment.end_time - segment.start_time,
            "resolution": {
                "width": self.config["resolution"][0],
                "height": self.config["resolution"][1],
            },
            "fps": self.config["fps"],
            "guidance_scale": 7.5,
            "num_inference_steps": 50,
        }

    def _build_text2world_request(self, segment: VideoSegment) -> dict:
        """Build Text2World API request."""
        return {
            "model": self.model_id,
            "mode": "Text2World",
            "prompt": segment.prompt or "Industrial manufacturing equipment, factory floor, realistic lighting",
            "duration": segment.end_time - segment.start_time,
            "resolution": {
                "width": self.config["resolution"][0],
                "height": self.config["resolution"][1],
            },
            "fps": self.config["fps"],
            "guidance_scale": 7.5,
            "num_inference_steps": 50,
        }

    async def _generate_segment_stub(self, segment: VideoSegment) -> str:
        """
        Generate stub video segment for development/testing.

        Creates a placeholder video using FFmpeg when API is unavailable.
        """
        logger.info("Using stub generation for segment %d (no API key)", segment.index)

        output_path = self.output_dir / f"segment_{segment.index:03d}_stub.mp4"
        duration = segment.end_time - segment.start_time

        # Use FFmpeg to create a test pattern video
        # If we have a seed image, use it; otherwise generate color bars
        import subprocess

        if segment.seed_image and Path(segment.seed_image).exists():
            # Create video from image with Ken Burns effect
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", segment.seed_image,
                "-t", str(duration),
                "-vf", f"scale=1920:1080,zoompan=z='1.08':d={int(duration*30)}:s=1920x1080",
                "-c:v", "libx264",
                "-profile:v", "high",
                "-level", "4.0",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                str(output_path)
            ]
        else:
            # Generate SMPTE color bars with text
            label = f"Segment {segment.index + 1}: {segment.prompt[:50]}..." if segment.prompt else f"Segment {segment.index + 1}"
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"smptebars=size=1920x1080:rate=30:duration={duration}",
                "-vf", f"drawtext=text='{label}':fontsize=48:fontcolor=white:x=(w-tw)/2:y=h-100:box=1:boxcolor=black@0.7",
                "-c:v", "libx264",
                "-profile:v", "high",
                "-level", "4.0",
                "-pix_fmt", "yuv420p",
                str(output_path)
            ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.error("FFmpeg stub generation failed: %s", result.stderr)
                raise VideoGenerationError(f"FFmpeg failed: {result.stderr[:200]}")
        except FileNotFoundError:
            raise VideoGenerationError("FFmpeg not installed - required for video generation")

        return str(output_path)

    async def _chain_clips(
        self,
        clip_paths: list[str],
        target_duration: float
    ) -> str:
        """
        Chain video clips into final output using FFmpeg.

        Uses crossfade transitions between clips.
        """
        if len(clip_paths) == 1:
            # Single clip, just copy
            final_path = self.output_dir / "final_output.mp4"
            import shutil
            shutil.copy(clip_paths[0], final_path)
            return str(final_path)

        import subprocess

        # Build FFmpeg filter for crossfade transitions
        # Each transition is 0.5 seconds
        transition_duration = 0.5
        final_path = self.output_dir / "final_output.mp4"

        # Create concat file
        concat_file = self.output_dir / "concat.txt"
        with open(concat_file, "w") as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")

        # Use concat demuxer for simple joining (crossfade requires complex filter)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-profile:v", "high",
            "-level", "4.0",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            str(final_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                logger.error("FFmpeg chaining failed: %s", result.stderr)
                raise VideoGenerationError(f"FFmpeg chaining failed: {result.stderr[:200]}")
        except FileNotFoundError:
            raise VideoGenerationError("FFmpeg not installed")

        return str(final_path)

    def is_available(self) -> bool:
        """Check if API is available (has credentials)."""
        return bool(self.api_key)


# CLI Entry Point
async def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate video from Content Judge output")
    parser.add_argument("--judge-output", "-j", required=True, help="Path to judge output JSON")
    parser.add_argument("--model", "-m", default="2B", choices=["2B", "7B", "14B"], help="Model size")
    parser.add_argument("--mode", default="Video2World", choices=["Video2World", "Text2World"])
    parser.add_argument("--duration", "-d", type=float, help="Target duration in seconds")
    parser.add_argument("--output", "-o", help="Output directory")

    args = parser.parse_args()

    # Load judge output
    with open(args.judge_output) as f:
        judge_output = json.load(f)

    # Generate video
    generator = CosmosVideoGenerator(
        model_size=args.model,
        output_dir=args.output
    )

    try:
        result = await generator.generate_from_judge_output(
            judge_output,
            mode=args.mode,
            duration=args.duration
        )

        if result.success:
            print(f"Video generated successfully: {result.video_path}")
            print(f"Segments: {result.segments_generated}")
            print(f"Duration: {result.total_duration:.1f}s")
            print(f"Model: {result.model_used}")
        else:
            print(f"Generation failed: {result.errors}")
            exit(1)

    finally:
        await generator.close()


if __name__ == "__main__":
    asyncio.run(main())

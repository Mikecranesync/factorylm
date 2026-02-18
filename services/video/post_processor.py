"""
Video Post-Processor for FactoryLM.

Final assembly for competition-ready output:
- Branding (intro/outro)
- Audio mixing (narration + background)
- Caption generation
- H.264 compression for YouTube
"""

import asyncio
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PostProcessingError(Exception):
    """Raised when post-processing fails."""
    pass


@dataclass
class BrandingConfig:
    """Branding configuration."""
    intro_video: Optional[str] = None
    outro_video: Optional[str] = None
    watermark_image: Optional[str] = None
    watermark_position: str = "bottom-right"  # top-left, top-right, bottom-left, bottom-right
    watermark_opacity: float = 0.3
    intro_duration: float = 3.0
    outro_duration: float = 2.0


@dataclass
class AudioConfig:
    """Audio mixing configuration."""
    narration_path: Optional[str] = None
    background_music_path: Optional[str] = None
    narration_volume: float = 1.0  # 0.0 to 1.0
    music_volume: float = 0.15  # Background music at -20dB
    sfx_paths: list = None  # Optional sound effects
    ducking: bool = True  # Lower music when narration plays


@dataclass
class CompressionConfig:
    """Video compression settings."""
    codec: str = "libx264"
    profile: str = "high"
    level: str = "4.0"
    crf: int = 23  # Quality (lower = better, 18-28 typical)
    preset: str = "fast"  # ultrafast, fast, medium, slow
    max_bitrate: str = "8M"  # For YouTube
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    pixel_format: str = "yuv420p"


@dataclass
class ProcessingResult:
    """Result from post-processing."""
    success: bool
    output_path: Optional[str] = None
    duration: float = 0.0
    file_size_mb: float = 0.0
    errors: list = None
    metadata: dict = None


class VideoPostProcessor:
    """
    Final assembly for competition-ready output.

    Pipeline:
    1. Inject intro/outro
    2. Add watermark
    3. Mix audio tracks
    4. Generate captions
    5. Compress for YouTube
    """

    DEFAULT_BRANDING = BrandingConfig()
    DEFAULT_AUDIO = AudioConfig()
    DEFAULT_COMPRESSION = CompressionConfig()

    def __init__(
        self,
        output_dir: Optional[str] = None,
        ffmpeg_path: str = "ffmpeg",
    ):
        """
        Initialize post-processor.

        Args:
            output_dir: Where to save processed videos
            ffmpeg_path: Path to FFmpeg binary
        """
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "factorylm_processed"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_path = ffmpeg_path
        self._temp_dir = Path(tempfile.gettempdir()) / "factorylm_processing"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        generated_video: str,
        audio_narration: Optional[str] = None,
        branding: Optional[BrandingConfig] = None,
        audio: Optional[AudioConfig] = None,
        compression: Optional[CompressionConfig] = None,
        output_name: Optional[str] = None,
        add_captions: bool = True,
        caption_script: Optional[str] = None,
    ) -> ProcessingResult:
        """
        Full post-processing pipeline.

        Args:
            generated_video: Path to input video
            audio_narration: Path to narration audio
            branding: Branding configuration
            audio: Audio mixing configuration
            compression: Compression settings
            output_name: Output filename (without extension)
            add_captions: Whether to burn in captions
            caption_script: Script text for caption generation

        Returns:
            ProcessingResult with output path and metadata
        """
        branding = branding or self.DEFAULT_BRANDING
        audio = audio or self.DEFAULT_AUDIO
        compression = compression or self.DEFAULT_COMPRESSION

        if audio_narration:
            audio.narration_path = audio_narration

        video_path = Path(generated_video)
        if not video_path.exists():
            return ProcessingResult(
                success=False,
                errors=[f"Input video not found: {generated_video}"]
            )

        output_name = output_name or video_path.stem + "_final"
        errors = []

        try:
            # Step 1: Add branding (intro/outro/watermark)
            branded_path = self._add_branding(str(video_path), branding)
            logger.info("Branding applied: %s", branded_path)

            # Step 2: Mix audio
            with_audio = self._mix_audio(branded_path, audio)
            logger.info("Audio mixed: %s", with_audio)

            # Step 3: Add captions (optional)
            if add_captions and caption_script:
                with_captions = self._add_captions(with_audio, caption_script)
                logger.info("Captions added: %s", with_captions)
            else:
                with_captions = with_audio

            # Step 4: Final compression
            final_path = self._compress(with_captions, compression, output_name)
            logger.info("Compressed: %s", final_path)

            # Get file info
            duration = self._get_duration(final_path)
            file_size = Path(final_path).stat().st_size / (1024 * 1024)

            return ProcessingResult(
                success=True,
                output_path=final_path,
                duration=duration,
                file_size_mb=file_size,
                errors=errors if errors else None,
                metadata={
                    "codec": compression.codec,
                    "crf": compression.crf,
                    "has_captions": add_captions and caption_script is not None,
                    "has_branding": branding.intro_video is not None or branding.outro_video is not None,
                }
            )

        except Exception as e:
            logger.exception("Post-processing failed")
            return ProcessingResult(
                success=False,
                errors=[str(e)] + errors
            )

    def _add_branding(self, video_path: str, config: BrandingConfig) -> str:
        """Add intro, outro, and watermark."""
        current = video_path

        # Add watermark if configured
        if config.watermark_image and Path(config.watermark_image).exists():
            watermarked = self._temp_dir / "watermarked.mp4"
            current = self._apply_watermark(
                current,
                config.watermark_image,
                str(watermarked),
                config.watermark_position,
                config.watermark_opacity
            )

        # Concatenate intro + video + outro
        parts = []
        if config.intro_video and Path(config.intro_video).exists():
            parts.append(config.intro_video)
        parts.append(current)
        if config.outro_video and Path(config.outro_video).exists():
            parts.append(config.outro_video)

        if len(parts) > 1:
            branded = self._temp_dir / "branded.mp4"
            current = self._concatenate_videos(parts, str(branded))

        return current

    def _apply_watermark(
        self,
        video_path: str,
        watermark_path: str,
        output_path: str,
        position: str,
        opacity: float
    ) -> str:
        """Apply watermark overlay."""
        # Position mapping
        positions = {
            "top-left": "10:10",
            "top-right": "main_w-overlay_w-10:10",
            "bottom-left": "10:main_h-overlay_h-10",
            "bottom-right": "main_w-overlay_w-10:main_h-overlay_h-10",
        }
        overlay_pos = positions.get(position, positions["bottom-right"])

        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-i", watermark_path,
            "-filter_complex",
            f"[1:v]format=rgba,colorchannelmixer=aa={opacity}[wm];[0:v][wm]overlay={overlay_pos}",
            "-c:v", "libx264",
            "-c:a", "copy",
            output_path
        ]

        self._run_ffmpeg(cmd)
        return output_path

    def _concatenate_videos(self, video_paths: list, output_path: str) -> str:
        """Concatenate multiple videos."""
        # Create concat file
        concat_file = self._temp_dir / "concat.txt"
        with open(concat_file, "w") as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]

        self._run_ffmpeg(cmd)
        return output_path

    def _mix_audio(self, video_path: str, config: AudioConfig) -> str:
        """Mix narration and background music."""
        if not config.narration_path and not config.background_music_path:
            return video_path

        output_path = str(self._temp_dir / "audio_mixed.mp4")

        inputs = ["-i", video_path]
        filter_parts = []
        audio_streams = []

        stream_idx = 1  # 0 is video

        # Add narration
        if config.narration_path and Path(config.narration_path).exists():
            inputs.extend(["-i", config.narration_path])
            filter_parts.append(f"[{stream_idx}:a]volume={config.narration_volume}[narr]")
            audio_streams.append("[narr]")
            stream_idx += 1

        # Add background music
        if config.background_music_path and Path(config.background_music_path).exists():
            inputs.extend(["-i", config.background_music_path])
            filter_parts.append(f"[{stream_idx}:a]volume={config.music_volume}[music]")
            audio_streams.append("[music]")

        if not audio_streams:
            return video_path

        # Mix streams
        if len(audio_streams) > 1:
            mix_filter = "".join(audio_streams) + f"amix=inputs={len(audio_streams)}:duration=longest[aout]"
            filter_parts.append(mix_filter)
            audio_output = "[aout]"
        else:
            audio_output = audio_streams[0]

        filter_complex = ";".join(filter_parts)

        cmd = [
            self.ffmpeg_path, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", audio_output,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]

        self._run_ffmpeg(cmd)
        return output_path

    def _add_captions(self, video_path: str, script: str) -> str:
        """
        Add burned-in captions using FFmpeg drawtext.

        For production, would use SRT/VTT with proper timing.
        This is a simplified version that shows text at the bottom.
        """
        output_path = str(self._temp_dir / "captioned.mp4")

        # Get video duration
        duration = self._get_duration(video_path)

        # Split script into caption chunks (roughly 3 seconds each)
        import re
        sentences = re.split(r'(?<=[.!?])\s+', script.strip())

        # Create SRT-style timing
        chunk_duration = duration / max(len(sentences), 1)

        # For simplicity, just show a scrolling caption
        # In production, would generate proper SRT file
        escaped_text = script.replace("'", "\\'").replace(":", "\\:")[:200]

        # Use drawtext filter with scrolling
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-vf", (
                f"drawtext=text='{escaped_text}':"
                f"fontsize=36:fontcolor=white:borderw=2:bordercolor=black:"
                f"x=(w-tw)/2:y=h-80:"
                f"box=1:boxcolor=black@0.5:boxborderw=5"
            ),
            "-c:v", "libx264",
            "-c:a", "copy",
            output_path
        ]

        try:
            self._run_ffmpeg(cmd)
            return output_path
        except Exception as e:
            logger.warning("Caption rendering failed: %s, returning without captions", e)
            return video_path

    def _compress(
        self,
        video_path: str,
        config: CompressionConfig,
        output_name: str
    ) -> str:
        """Final H.264 compression for YouTube."""
        output_path = str(self.output_dir / f"{output_name}.mp4")

        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-c:v", config.codec,
            "-profile:v", config.profile,
            "-level", config.level,
            "-preset", config.preset,
            "-crf", str(config.crf),
            "-maxrate", config.max_bitrate,
            "-bufsize", "16M",
            "-pix_fmt", config.pixel_format,
            "-c:a", config.audio_codec,
            "-b:a", config.audio_bitrate,
            "-movflags", "+faststart",  # Web optimization
            output_path
        ]

        self._run_ffmpeg(cmd)
        return output_path

    def _get_duration(self, video_path: str) -> float:
        """Get video duration in seconds."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _run_ffmpeg(self, cmd: list, timeout: int = 300):
        """Run FFmpeg command with error handling."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                logger.error("FFmpeg error: %s", result.stderr[:500])
                raise PostProcessingError(f"FFmpeg failed: {result.stderr[:200]}")
        except FileNotFoundError:
            raise PostProcessingError(f"FFmpeg not found at: {self.ffmpeg_path}")

    def cleanup(self):
        """Clean up temporary files."""
        for f in self._temp_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass


# Preset configurations
PRESETS = {
    "youtube_shorts": {
        "compression": CompressionConfig(
            crf=20,
            preset="medium",
            max_bitrate="12M",
        ),
        "branding": BrandingConfig(
            intro_duration=0,  # No intro for Shorts
            outro_duration=0,
        ),
    },
    "youtube_standard": {
        "compression": CompressionConfig(
            crf=18,
            preset="slow",
            max_bitrate="20M",
        ),
        "branding": BrandingConfig(
            intro_duration=3.0,
            outro_duration=2.0,
        ),
    },
    "competition": {
        "compression": CompressionConfig(
            crf=16,
            preset="slow",
            max_bitrate="25M",
        ),
        "branding": BrandingConfig(
            intro_duration=5.0,
            outro_duration=3.0,
        ),
    },
}


def get_preset(name: str) -> dict:
    """Get preset configuration by name."""
    return PRESETS.get(name, PRESETS["youtube_standard"])


# CLI Entry Point
def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Post-process generated video")
    parser.add_argument("video", help="Path to input video")
    parser.add_argument("--audio", "-a", help="Path to narration audio")
    parser.add_argument("--music", "-m", help="Path to background music")
    parser.add_argument("--watermark", "-w", help="Path to watermark image")
    parser.add_argument("--captions", "-c", help="Script text for captions")
    parser.add_argument("--preset", "-p", choices=list(PRESETS.keys()), default="youtube_standard")
    parser.add_argument("--output", "-o", help="Output filename")
    parser.add_argument("--output-dir", "-d", help="Output directory")

    args = parser.parse_args()

    # Get preset config
    preset = get_preset(args.preset)

    # Override with CLI args
    audio_config = AudioConfig(
        narration_path=args.audio,
        background_music_path=args.music,
    )
    branding_config = preset.get("branding", BrandingConfig())
    if args.watermark:
        branding_config.watermark_image = args.watermark

    # Process
    processor = VideoPostProcessor(output_dir=args.output_dir)

    result = processor.process(
        generated_video=args.video,
        branding=branding_config,
        audio=audio_config,
        compression=preset.get("compression", CompressionConfig()),
        output_name=args.output,
        add_captions=bool(args.captions),
        caption_script=args.captions,
    )

    if result.success:
        print(f"Processing complete: {result.output_path}")
        print(f"Duration: {result.duration:.1f}s")
        print(f"Size: {result.file_size_mb:.1f} MB")
    else:
        print(f"Processing failed: {result.errors}")
        exit(1)


if __name__ == "__main__":
    main()

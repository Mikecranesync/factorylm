"""
Distribution Manager for FactoryLM Videos.

Multi-platform deployment:
- YouTube (standard + Shorts)
- GitHub PR embedding
- Competition submission
- Social media cross-posting
"""

import asyncio
import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DistributionError(Exception):
    """Raised when distribution fails."""
    pass


@dataclass
class UploadResult:
    """Result from a single upload."""
    success: bool
    platform: str
    url: Optional[str] = None
    id: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DistributionResult:
    """Result from multi-platform distribution."""
    success: bool
    uploads: list  # List of UploadResult
    errors: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


@dataclass
class VideoMetadata:
    """Metadata for video upload."""
    title: str
    description: str
    tags: list = field(default_factory=list)
    category: str = "Education"  # YouTube category
    privacy: str = "public"  # public, unlisted, private
    is_short: bool = False
    thumbnail_path: Optional[str] = None
    scheduled_publish: Optional[datetime] = None
    playlist_id: Optional[str] = None


class BaseUploader(ABC):
    """Base class for platform uploaders."""

    @abstractmethod
    async def upload(
        self,
        video_path: str,
        metadata: VideoMetadata
    ) -> UploadResult:
        """Upload video to platform."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if credentials are configured."""
        pass


class YouTubeUploader(BaseUploader):
    """
    YouTube upload via google-api-python-client or yt-dlp.

    Requires OAuth2 credentials in YOUTUBE_OAUTH_PATH or
    uses browser-based auth flow.
    """

    # YouTube category IDs
    CATEGORIES = {
        "Education": "27",
        "Science & Technology": "28",
        "Howto & Style": "26",
    }

    def __init__(self):
        self.oauth_path = os.getenv("YOUTUBE_OAUTH_PATH", "config/youtube_oauth.json")
        self.client_secrets = os.getenv("YOUTUBE_CLIENT_SECRETS", "config/client_secrets.json")

    def is_configured(self) -> bool:
        """Check if YouTube credentials exist."""
        return Path(self.client_secrets).exists()

    async def upload(
        self,
        video_path: str,
        metadata: VideoMetadata
    ) -> UploadResult:
        """
        Upload video to YouTube.

        Uses google-api-python-client if available, falls back to yt-dlp.
        """
        try:
            # Try google-api-python-client first
            return await self._upload_via_api(video_path, metadata)
        except ImportError:
            logger.info("google-api-python-client not available, trying yt-dlp")
            return await self._upload_via_ytdlp(video_path, metadata)
        except Exception as e:
            logger.error("YouTube upload failed: %s", e)
            return UploadResult(
                success=False,
                platform="youtube",
                error=str(e)
            )

    async def _upload_via_api(
        self,
        video_path: str,
        metadata: VideoMetadata
    ) -> UploadResult:
        """Upload using Google API."""
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        # Get credentials
        creds = None
        if Path(self.oauth_path).exists():
            creds = Credentials.from_authorized_user_file(self.oauth_path)

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets,
                scopes=["https://www.googleapis.com/auth/youtube.upload"]
            )
            creds = flow.run_local_server(port=0)
            # Save for future use
            with open(self.oauth_path, "w") as f:
                f.write(creds.to_json())

        # Build YouTube service
        youtube = build("youtube", "v3", credentials=creds)

        # Prepare description
        description = metadata.description
        if metadata.is_short:
            description = "#Shorts\n\n" + description

        # Upload
        body = {
            "snippet": {
                "title": metadata.title[:100],  # YouTube limit
                "description": description,
                "tags": metadata.tags,
                "categoryId": self.CATEGORIES.get(metadata.category, "27"),
            },
            "status": {
                "privacyStatus": metadata.privacy,
                "selfDeclaredMadeForKids": False,
            }
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = request.execute()

        video_id = response["id"]
        url = f"https://youtube.com/watch?v={video_id}"
        if metadata.is_short:
            url = f"https://youtube.com/shorts/{video_id}"

        return UploadResult(
            success=True,
            platform="youtube",
            url=url,
            id=video_id,
            metadata={
                "title": metadata.title,
                "privacy": metadata.privacy,
                "is_short": metadata.is_short
            }
        )

    async def _upload_via_ytdlp(
        self,
        video_path: str,
        metadata: VideoMetadata
    ) -> UploadResult:
        """Upload using yt-dlp (requires browser cookies)."""
        # Note: yt-dlp upload requires additional setup
        # This is a placeholder for the command structure
        logger.warning("yt-dlp upload not fully implemented")
        return UploadResult(
            success=False,
            platform="youtube",
            error="yt-dlp upload requires manual browser auth"
        )


class GitHubPRUpdater(BaseUploader):
    """
    Update GitHub PR with video embed.

    Uploads video to GitHub releases or links to YouTube.
    """

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        self.repo = os.getenv("GITHUB_REPO", "Mikecranesync/factorylm")

    def is_configured(self) -> bool:
        return bool(self.token)

    async def upload(
        self,
        video_path: str,
        metadata: VideoMetadata
    ) -> UploadResult:
        """
        Upload/link video to GitHub PR.

        Large videos are linked from YouTube; small ones uploaded to releases.
        """
        try:
            file_size_mb = Path(video_path).stat().st_size / (1024 * 1024)

            if file_size_mb > 100:
                # Too large for GitHub - return info for manual linking
                return UploadResult(
                    success=True,
                    platform="github_pr",
                    metadata={
                        "action": "link_required",
                        "reason": f"Video too large ({file_size_mb:.1f}MB) - upload to YouTube first",
                        "video_path": video_path
                    }
                )

            # Upload to releases using gh CLI
            result = subprocess.run(
                [
                    "gh", "release", "upload",
                    "latest",  # or specific tag
                    video_path,
                    "--clobber",
                    "-R", self.repo
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                video_name = Path(video_path).name
                url = f"https://github.com/{self.repo}/releases/latest/download/{video_name}"
                return UploadResult(
                    success=True,
                    platform="github_pr",
                    url=url,
                    metadata={"file": video_name}
                )
            else:
                return UploadResult(
                    success=False,
                    platform="github_pr",
                    error=result.stderr[:200]
                )

        except Exception as e:
            return UploadResult(
                success=False,
                platform="github_pr",
                error=str(e)
            )


class CompetitionSubmitter(BaseUploader):
    """
    Submit to NVIDIA Cosmos Cookoff competition.

    Handles competition-specific requirements.
    """

    COMPETITION_URL = "https://developer.nvidia.com/cosmos-cookoff"

    def __init__(self):
        self.submission_dir = Path("competition/submissions")
        self.submission_dir.mkdir(parents=True, exist_ok=True)

    def is_configured(self) -> bool:
        """Competition submission is always available (creates package)."""
        return True

    async def upload(
        self,
        video_path: str,
        metadata: VideoMetadata
    ) -> UploadResult:
        """
        Prepare competition submission package.

        Creates a submission folder with:
        - Video file
        - metadata.json
        - README.md
        - Source code snapshot
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            submission_name = f"cosmos_cookoff_{timestamp}"
            submission_path = self.submission_dir / submission_name
            submission_path.mkdir(parents=True, exist_ok=True)

            # Copy video
            import shutil
            video_dest = submission_path / "demo_video.mp4"
            shutil.copy(video_path, video_dest)

            # Create metadata file
            meta_file = submission_path / "metadata.json"
            submission_meta = {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "created_at": timestamp,
                "video_file": "demo_video.mp4",
                "project": "FactoryLM",
                "team": "Industrial Skills Hub",
                "cosmos_models_used": [
                    "cosmos-predict2-14b",
                    "cosmos-reason2-8b"
                ],
                "features": [
                    "Real-time industrial diagnosis",
                    "AI video generation from maintenance data",
                    "Natural language factory interface"
                ]
            }
            with open(meta_file, "w") as f:
                json.dump(submission_meta, f, indent=2)

            # Create README
            readme_file = submission_path / "README.md"
            readme_content = f"""# FactoryLM - Cosmos Cookoff 2026 Submission

## {metadata.title}

{metadata.description}

### Project Overview

FactoryLM uses NVIDIA Cosmos models to revolutionize industrial maintenance:

1. **Cosmos-Reason2**: Analyzes equipment faults from photos and sensor data
2. **Cosmos-Predict2**: Generates training videos from maintenance sessions

### Demo Video

See `demo_video.mp4` for a demonstration of our AI-generated training content.

### Key Features

- Real-time AI diagnosis via Telegram
- Photo-based troubleshooting
- Auto-generated training content
- Edge deployment capable (air-gapped)

### Repository

https://github.com/Mikecranesync/factorylm

### Team

Industrial Skills Hub - Building the future of industrial training.
"""
            with open(readme_file, "w") as f:
                f.write(readme_content)

            return UploadResult(
                success=True,
                platform="competition",
                url=str(submission_path),
                metadata={
                    "submission_name": submission_name,
                    "contents": ["demo_video.mp4", "metadata.json", "README.md"],
                    "next_steps": f"Upload {submission_path} to {self.COMPETITION_URL}"
                }
            )

        except Exception as e:
            return UploadResult(
                success=False,
                platform="competition",
                error=str(e)
            )


class SocialMediaCrossPost(BaseUploader):
    """
    Cross-post to social media platforms.

    Supports Twitter/X, LinkedIn, and Instagram (via API or manual).
    """

    def __init__(self):
        self.twitter_api_key = os.getenv("TWITTER_API_KEY")
        self.linkedin_token = os.getenv("LINKEDIN_TOKEN")

    def is_configured(self) -> bool:
        return bool(self.twitter_api_key or self.linkedin_token)

    async def upload(
        self,
        video_path: str,
        metadata: VideoMetadata
    ) -> UploadResult:
        """
        Create social media post package.

        For most platforms, prepares content for manual posting.
        """
        # Create shareable snippet
        title = metadata.title[:50]
        tags = " ".join(f"#{tag}" for tag in metadata.tags[:5])

        tweet_text = f"{title}\n\n{tags}\n\nWatch the full video!"

        linkedin_text = f"""🏭 {metadata.title}

{metadata.description[:200]}...

{tags}

#IndustrialAutomation #AI #Manufacturing
"""

        return UploadResult(
            success=True,
            platform="social",
            metadata={
                "twitter_text": tweet_text[:280],
                "linkedin_text": linkedin_text,
                "video_path": video_path,
                "note": "Manual posting recommended for best engagement"
            }
        )


class DistributionManager:
    """
    Multi-platform video distribution.

    Orchestrates uploads across configured platforms.
    """

    # Available uploaders
    UPLOADERS = {
        "youtube": YouTubeUploader,
        "github_pr": GitHubPRUpdater,
        "competition": CompetitionSubmitter,
        "social": SocialMediaCrossPost,
    }

    def __init__(self):
        self._uploaders = {}

    def _get_uploader(self, platform: str) -> BaseUploader:
        """Get or create uploader for platform."""
        if platform not in self._uploaders:
            if platform not in self.UPLOADERS:
                raise DistributionError(f"Unknown platform: {platform}")
            self._uploaders[platform] = self.UPLOADERS[platform]()
        return self._uploaders[platform]

    async def distribute(
        self,
        video_path: str,
        metadata: VideoMetadata,
        targets: list = None,
    ) -> DistributionResult:
        """
        Distribute video to multiple platforms.

        Args:
            video_path: Path to video file
            metadata: Video metadata
            targets: List of platforms (default: ["youtube", "github_pr"])

        Returns:
            DistributionResult with per-platform results
        """
        if targets is None:
            targets = ["youtube", "github_pr"]

        if not Path(video_path).exists():
            return DistributionResult(
                success=False,
                uploads=[],
                errors=[f"Video not found: {video_path}"]
            )

        uploads = []
        errors = []

        for platform in targets:
            try:
                uploader = self._get_uploader(platform)

                if not uploader.is_configured():
                    logger.warning("Platform %s not configured, skipping", platform)
                    uploads.append(UploadResult(
                        success=False,
                        platform=platform,
                        error="Not configured"
                    ))
                    continue

                logger.info("Uploading to %s...", platform)
                result = await uploader.upload(video_path, metadata)
                uploads.append(result)

                if not result.success:
                    errors.append(f"{platform}: {result.error}")

            except Exception as e:
                logger.error("Error uploading to %s: %s", platform, e)
                uploads.append(UploadResult(
                    success=False,
                    platform=platform,
                    error=str(e)
                ))
                errors.append(f"{platform}: {str(e)}")

        # Compile summary
        success_count = sum(1 for u in uploads if u.success)
        summary = {
            "total": len(targets),
            "successful": success_count,
            "failed": len(targets) - success_count,
            "urls": [u.url for u in uploads if u.url],
        }

        return DistributionResult(
            success=success_count > 0,
            uploads=uploads,
            errors=errors,
            summary=summary
        )

    def available_platforms(self) -> list[str]:
        """List platforms with valid configuration."""
        available = []
        for name, cls in self.UPLOADERS.items():
            uploader = cls()
            if uploader.is_configured():
                available.append(name)
        return available


# CLI Entry Point
async def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Distribute video to platforms")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--title", "-t", required=True, help="Video title")
    parser.add_argument("--description", "-d", default="", help="Video description")
    parser.add_argument("--tags", nargs="+", default=["factorylm", "industrial", "ai"])
    parser.add_argument("--platforms", "-p", nargs="+",
                       choices=list(DistributionManager.UPLOADERS.keys()),
                       default=["competition"])
    parser.add_argument("--shorts", action="store_true", help="Mark as YouTube Short")
    parser.add_argument("--list", action="store_true", help="List available platforms")

    args = parser.parse_args()

    manager = DistributionManager()

    if args.list:
        print("Available platforms:")
        for p in manager.available_platforms():
            print(f"  - {p}")
        return

    metadata = VideoMetadata(
        title=args.title,
        description=args.description,
        tags=args.tags,
        is_short=args.shorts,
    )

    result = await manager.distribute(
        args.video,
        metadata,
        targets=args.platforms
    )

    print(f"\nDistribution {'succeeded' if result.success else 'failed'}")
    print(f"Summary: {result.summary}")

    for upload in result.uploads:
        status = "OK" if upload.success else "FAILED"
        print(f"  {upload.platform}: [{status}]", end="")
        if upload.url:
            print(f" -> {upload.url}")
        elif upload.error:
            print(f" - {upload.error}")
        else:
            print()

    if result.errors:
        print(f"\nErrors: {result.errors}")


if __name__ == "__main__":
    asyncio.run(main())

"""
Travel Laptop Digital Twin

Represents the development/travel laptop with Claude Code, Git, and development tools.
Provides development, testing, and deployment capabilities.
"""

from typing import Dict, Any, List, Optional
import logging

from .twin import DigitalTwin, TwinStatus

logger = logging.getLogger(__name__)


class TravelTwin(DigitalTwin):
    """
    Digital twin for the Travel laptop (Miguelomaniac).

    Capabilities:
    - Git operations (status, commit, push, pull)
    - Test execution (pytest, unit tests, integration tests)
    - Deployment operations
    - Claude Code session management
    - Development environment management
    """

    def __init__(self, id: str = "travel", name: str = "Travel Laptop", url: str = "http://100.83.251.23:8765"):
        """Initialize Travel twin with development capabilities"""
        super().__init__(
            id=id,
            name=name,
            url=url,
            capabilities=[
                "git_status",
                "git_commit",
                "git_push",
                "git_pull",
                "run_tests",
                "deploy",
                "build_project",
                "lint_code",
                "format_code",
                "install_dependencies",
                "claude_code_status",
                "create_branch",
                "merge_branch"
            ],
            metadata={
                "device_type": "development_laptop",
                "hostname": "Miguelomaniac",
                "ip_address": "100.83.251.23",
                "role": "development",
                "tools": ["git", "python", "node", "docker", "claude_code"]
            }
        )

    async def git_status(self, repo_path: str = None) -> Dict[str, Any]:
        """
        Get Git repository status.

        Args:
            repo_path: Path to repository (defaults to FactoryLM)

        Returns:
            dict: Git status including branch, staged files, unstaged files
        """
        params = {}
        if repo_path:
            params["repo_path"] = repo_path

        result = await self.execute("git_status", params)

        if result.get("success"):
            logger.info(f"📋 Git status: {result.get('branch', 'unknown')}")
        else:
            logger.error(f"❌ Git status failed: {result.get('error')}")

        return result

    async def git_commit(self, message: str, files: Optional[List[str]] = None) -> bool:
        """
        Create a Git commit.

        Args:
            message: Commit message
            files: Files to stage (None for all changes)

        Returns:
            bool: True if commit succeeded
        """
        params = {"message": message}
        if files:
            params["files"] = files

        result = await self.execute("git_commit", params)

        if result.get("success"):
            logger.info(f"✅ Committed: {message[:50]}...")
            return True
        else:
            logger.error(f"❌ Commit failed: {result.get('error')}")
            return False

    async def git_push(self, branch: Optional[str] = None, remote: str = "origin") -> bool:
        """
        Push commits to remote repository.

        Args:
            branch: Branch to push (None for current branch)
            remote: Remote name (default: origin)

        Returns:
            bool: True if push succeeded
        """
        params = {"remote": remote}
        if branch:
            params["branch"] = branch

        result = await self.execute("git_push", params)

        if result.get("success"):
            logger.info(f"📤 Pushed to {remote}/{branch or 'current branch'}")
            return True
        else:
            logger.error(f"❌ Push failed: {result.get('error')}")
            return False

    async def git_pull(self, branch: Optional[str] = None, remote: str = "origin") -> bool:
        """
        Pull changes from remote repository.

        Args:
            branch: Branch to pull (None for current branch)
            remote: Remote name (default: origin)

        Returns:
            bool: True if pull succeeded
        """
        params = {"remote": remote}
        if branch:
            params["branch"] = branch

        result = await self.execute("git_pull", params)

        if result.get("success"):
            logger.info(f"📥 Pulled from {remote}/{branch or 'current branch'}")
            return True
        else:
            logger.error(f"❌ Pull failed: {result.get('error')}")
            return False

    async def run_tests(self, test_path: Optional[str] = None, test_type: str = "all") -> Dict[str, Any]:
        """
        Run test suite.

        Args:
            test_path: Specific test file or directory
            test_type: Type of tests ("unit", "integration", "e2e", "all")

        Returns:
            dict: Test results with pass/fail counts
        """
        params = {"test_type": test_type}
        if test_path:
            params["test_path"] = test_path

        result = await self.execute("run_tests", params)

        if result.get("success"):
            passed = result.get("passed", 0)
            failed = result.get("failed", 0)
            logger.info(f"🧪 Tests: {passed} passed, {failed} failed")
        else:
            logger.error(f"❌ Test execution failed: {result.get('error')}")

        return result

    async def deploy(self, environment: str = "staging", service: Optional[str] = None) -> Dict[str, Any]:
        """
        Deploy application to specified environment.

        Args:
            environment: Target environment ("dev", "staging", "production")
            service: Specific service to deploy (None for all)

        Returns:
            dict: Deployment result
        """
        params = {"environment": environment}
        if service:
            params["service"] = service

        result = await self.execute("deploy", params)

        if result.get("success"):
            logger.info(f"🚀 Deployed to {environment}")
        else:
            logger.error(f"❌ Deployment failed: {result.get('error')}")

        return result

    async def build_project(self, clean: bool = False) -> bool:
        """
        Build the project.

        Args:
            clean: Whether to clean before building

        Returns:
            bool: True if build succeeded
        """
        result = await self.execute("build_project", {"clean": clean})

        if result.get("success"):
            logger.info("🔨 Build completed successfully")
            return True
        else:
            logger.error(f"❌ Build failed: {result.get('error')}")
            return False

    async def lint_code(self, fix: bool = False) -> Dict[str, Any]:
        """
        Lint codebase.

        Args:
            fix: Whether to auto-fix linting issues

        Returns:
            dict: Linting results
        """
        result = await self.execute("lint_code", {"fix": fix})

        if result.get("success"):
            issues = result.get("issues", 0)
            logger.info(f"🔍 Linting: {issues} issues found")
        else:
            logger.error(f"❌ Linting failed: {result.get('error')}")

        return result

    async def format_code(self, check_only: bool = False) -> bool:
        """
        Format codebase.

        Args:
            check_only: Only check formatting without making changes

        Returns:
            bool: True if formatting succeeded (or is correct for check_only)
        """
        result = await self.execute("format_code", {"check_only": check_only})

        if result.get("success"):
            logger.info("✨ Code formatted successfully")
            return True
        else:
            logger.error(f"❌ Formatting failed: {result.get('error')}")
            return False

    async def install_dependencies(self, package_manager: str = "auto") -> bool:
        """
        Install project dependencies.

        Args:
            package_manager: Package manager to use ("npm", "pip", "auto")

        Returns:
            bool: True if installation succeeded
        """
        result = await self.execute("install_dependencies", {"package_manager": package_manager})

        if result.get("success"):
            logger.info("📦 Dependencies installed successfully")
            return True
        else:
            logger.error(f"❌ Dependency installation failed: {result.get('error')}")
            return False

    async def claude_code_status(self) -> Dict[str, Any]:
        """
        Get Claude Code session status.

        Returns:
            dict: Claude Code status and active sessions
        """
        result = await self.execute("claude_code_status")

        if result.get("success"):
            logger.info("🤖 Retrieved Claude Code status")
        else:
            logger.error(f"❌ Claude Code status check failed: {result.get('error')}")

        return result

    async def create_branch(self, branch_name: str, from_branch: Optional[str] = None) -> bool:
        """
        Create a new Git branch.

        Args:
            branch_name: Name of the new branch
            from_branch: Branch to create from (None for current)

        Returns:
            bool: True if branch created successfully
        """
        params = {"branch_name": branch_name}
        if from_branch:
            params["from_branch"] = from_branch

        result = await self.execute("create_branch", params)

        if result.get("success"):
            logger.info(f"🌿 Created branch: {branch_name}")
            return True
        else:
            logger.error(f"❌ Branch creation failed: {result.get('error')}")
            return False

    async def merge_branch(self, branch_name: str, into_branch: Optional[str] = None) -> bool:
        """
        Merge a Git branch.

        Args:
            branch_name: Branch to merge
            into_branch: Branch to merge into (None for current)

        Returns:
            bool: True if merge succeeded
        """
        params = {"branch_name": branch_name}
        if into_branch:
            params["into_branch"] = into_branch

        result = await self.execute("merge_branch", params)

        if result.get("success"):
            logger.info(f"🔀 Merged branch: {branch_name}")
            return True
        else:
            logger.error(f"❌ Merge failed: {result.get('error')}")
            return False

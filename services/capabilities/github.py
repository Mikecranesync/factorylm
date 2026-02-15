"""
GitHub Capability - gh CLI wrapper
==================================
Create gists, issues, PRs, manage repos via gh CLI.
"""

import os
import json
import subprocess
import logging
import tempfile
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_ORG = os.getenv("GITHUB_ORG", "Mikecranesync")


class GitHubCapability:
    """GitHub operations via gh CLI."""

    def __init__(self, org: str = DEFAULT_ORG):
        self.org = org

    def _gh(self, *args: str, input_text: str = None) -> tuple[int, str, str]:
        """Run gh command and return (returncode, stdout, stderr)."""
        cmd = ["gh"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                input=input_text,
                timeout=60,
                errors="replace"
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 1, "", "gh CLI not installed"
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)

    def _gh_json(self, *args: str) -> Any:
        """Run gh command expecting JSON output."""
        code, stdout, stderr = self._gh(*args)
        if code != 0:
            raise RuntimeError(f"gh error: {stderr}")
        return json.loads(stdout) if stdout.strip() else None

    async def health(self) -> dict:
        """Check GitHub CLI health."""
        code, stdout, stderr = self._gh("auth", "status")
        if code == 0:
            return {"status": "ok", "authenticated": True}
        return {"status": "unavailable", "reason": stderr}

    async def create_gist(
        self,
        files: Dict[str, str],
        description: str = "",
        public: bool = False
    ) -> str:
        """
        Create a GitHub Gist.

        Args:
            files: Dict of {filename: content}
            description: Gist description
            public: Whether gist is public

        Returns:
            Gist URL
        """
        # Write files to temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            file_paths = []
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                file_paths.append(filepath)

            # Build command
            args = ["gist", "create"]
            if description:
                args.extend(["-d", description])
            if public:
                args.append("--public")
            args.extend(file_paths)

            code, stdout, stderr = self._gh(*args)
            if code != 0:
                raise RuntimeError(f"Failed to create gist: {stderr}")

            # gh gist create returns the URL
            return stdout.strip()

    async def update_gist(
        self,
        gist_id: str,
        files: Dict[str, str]
    ) -> str:
        """Update an existing gist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_paths = []
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                file_paths.append(filepath)

            args = ["gist", "edit", gist_id] + file_paths
            code, stdout, stderr = self._gh(*args)
            if code != 0:
                raise RuntimeError(f"Failed to update gist: {stderr}")

            return f"https://gist.github.com/{gist_id}"

    async def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        labels: List[str] = None
    ) -> str:
        """
        Create a GitHub issue.

        Args:
            repo: Repository name (will use self.org as owner)
            title: Issue title
            body: Issue body/description
            labels: List of labels to apply

        Returns:
            Issue URL
        """
        args = ["issue", "create", "-R", f"{self.org}/{repo}", "-t", title]

        if body:
            args.extend(["-b", body])
        if labels:
            args.extend(["-l", ",".join(labels)])

        code, stdout, stderr = self._gh(*args)
        if code != 0:
            raise RuntimeError(f"Failed to create issue: {stderr}")

        return stdout.strip()

    async def create_pr(
        self,
        repo: str,
        title: str,
        body: str = "",
        base: str = "main",
        head: str = None,
        draft: bool = False
    ) -> str:
        """
        Create a pull request.

        Args:
            repo: Repository name
            title: PR title
            body: PR body
            base: Base branch (default: main)
            head: Head branch (default: current branch)
            draft: Create as draft PR

        Returns:
            PR URL
        """
        args = ["pr", "create", "-R", f"{self.org}/{repo}", "-t", title, "-B", base]

        if body:
            args.extend(["-b", body])
        if head:
            args.extend(["-H", head])
        if draft:
            args.append("--draft")

        code, stdout, stderr = self._gh(*args)
        if code != 0:
            raise RuntimeError(f"Failed to create PR: {stderr}")

        return stdout.strip()

    async def list_repos(self, limit: int = 50) -> List[Dict]:
        """List repositories for the org."""
        try:
            return self._gh_json(
                "repo", "list", self.org,
                "--limit", str(limit),
                "--json", "name,description,pushedAt,isArchived,stargazerCount"
            )
        except Exception as e:
            logger.error(f"Failed to list repos: {e}")
            return []

    async def search_code(
        self,
        query: str,
        repo: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search code across repos.

        Args:
            query: Search query
            repo: Optional specific repo to search
            limit: Max results

        Returns:
            List of {path, repository} matches
        """
        args = ["search", "code", query, "--limit", str(limit)]

        if repo:
            args.extend(["--repo", f"{self.org}/{repo}"])
        else:
            args.extend(["--owner", self.org])

        args.extend(["--json", "path,repository"])

        try:
            results = self._gh_json(*args)
            return results or []
        except Exception as e:
            logger.error(f"Code search failed: {e}")
            return []

    async def get_repo(self, repo: str) -> Dict:
        """Get repository info."""
        try:
            return self._gh_json(
                "repo", "view", f"{self.org}/{repo}",
                "--json", "name,description,url,defaultBranchRef,stargazerCount,forkCount,issues,pullRequests"
            )
        except Exception as e:
            logger.error(f"Failed to get repo: {e}")
            return {}

    async def list_issues(
        self,
        repo: str,
        state: str = "open",
        limit: int = 20
    ) -> List[Dict]:
        """List issues in a repo."""
        try:
            return self._gh_json(
                "issue", "list", "-R", f"{self.org}/{repo}",
                "--state", state,
                "--limit", str(limit),
                "--json", "number,title,state,author,createdAt"
            )
        except Exception as e:
            logger.error(f"Failed to list issues: {e}")
            return []

    async def list_prs(
        self,
        repo: str,
        state: str = "open",
        limit: int = 20
    ) -> List[Dict]:
        """List pull requests in a repo."""
        try:
            return self._gh_json(
                "pr", "list", "-R", f"{self.org}/{repo}",
                "--state", state,
                "--limit", str(limit),
                "--json", "number,title,state,author,createdAt,headRefName"
            )
        except Exception as e:
            logger.error(f"Failed to list PRs: {e}")
            return []

    async def clone_repo(self, repo: str, dest: str) -> bool:
        """Clone a repository."""
        code, stdout, stderr = self._gh(
            "repo", "clone", f"{self.org}/{repo}", dest
        )
        return code == 0

#!/usr/bin/env python3
"""
Jesus H Christ — Agentic Repo Resurrector
==========================================
"I am the resurrection and the code."

Scans GitHub repos, clones candidates, runs deep forensics,
and finds buried treasure: abandoned features, dead code,
valuable patterns, and commercial opportunities.

Requires: git, gh (GitHub CLI) — both free. No pip installs.

Usage:
    python resurrector.py scan                          # Scan all repos, rank by resurrection score
    python resurrector.py dig <repo>                    # Deep forensics on a single repo
    python resurrector.py hunt "search terms"           # Search code across all repos
    python resurrector.py autopsy <repo>                # Full autopsy: clone → forensics → report
    python resurrector.py mass-grave                    # Find all archived/abandoned repos
    python resurrector.py resurrect <repo>              # Clone + analyze + generate resurrection plan
    python resurrector.py report                        # Full HTML report of all findings

Options:
    --org <org>          GitHub org/user (default: mikecranesync)
    --top <n>            Max results (default: 20)
    --workspace <path>   Where to clone repos (default: ~/resurrection-yard)
    --no-color           Disable colors
"""

from __future__ import annotations

import argparse
import collections
import datetime
import html as html_mod
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ============================================================================
# Branding
# ============================================================================

VERSION = "2.0.0"
ANSI = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "green": "\033[38;2;0;255;136m", "nvidia": "\033[38;2;118;185;0m",
    "red": "\033[38;2;255;68;68m", "yellow": "\033[38;2;255;170;0m",
    "cyan": "\033[38;2;0;200;255m", "gray": "\033[38;2;120;120;120m",
    "white": "\033[97m", "gold": "\033[38;2;255;215;0m",
    "purple": "\033[38;2;180;100;255m",
}

BANNER = r"""
       ✝  JESUS H CHRIST  ✝
      ═══════════════════════
       The Repo Resurrector
    "Bringing dead code back to life"
"""


def c(text: str, color: str, use: bool = True) -> str:
    if not use:
        return str(text)
    return f"{ANSI.get(color, '')}{text}{ANSI['reset']}"


def _fix_encoding() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ============================================================================
# Data
# ============================================================================

@dataclass
class RepoInfo:
    name: str
    full_name: str
    description: str = ""
    archived: bool = False
    pushed_at: str = ""
    languages: list[str] = field(default_factory=list)
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    open_prs: int = 0
    has_readme: bool = False
    has_tests: bool = False
    has_ci: bool = False
    default_branch: str = "main"
    topics: list[str] = field(default_factory=list)
    size_kb: int = 0
    # Computed
    resurrection_score: int = 0
    dormant_days: int = 0
    verdict: str = ""
    flags: list[str] = field(default_factory=list)


@dataclass
class ForensicsResult:
    repo: str
    total_commits: int = 0
    authors: list[str] = field(default_factory=list)
    span_days: int = 0
    top_churn: list[dict] = field(default_factory=list)
    hotspots: list[dict] = field(default_factory=list)
    suspects: list[dict] = field(default_factory=list)
    ghosts: list[dict] = field(default_factory=list)
    ownership: dict[str, dict[str, int]] = field(default_factory=dict)
    buried_treasure: list[dict] = field(default_factory=list)
    dead_branches: list[dict] = field(default_factory=list)
    lost_features: list[dict] = field(default_factory=list)


# ============================================================================
# GitHub CLI wrapper
# ============================================================================

class GitHubScanner:
    """Scans GitHub via `gh` CLI."""

    def __init__(self, org: str = "mikecranesync", use_color: bool = True) -> None:
        self.org = org
        self.color = use_color

    def _gh(self, *args: str) -> str:
        cmd = ["gh"] + list(args)
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            raise RuntimeError(f"gh error: {r.stderr.strip()}")
        return r.stdout

    def _gh_json(self, *args: str) -> Any:
        return json.loads(self._gh(*args))

    def list_repos(self) -> list[RepoInfo]:
        """List all repos for the org/user."""
        raw = self._gh_json(
            "repo", "list", self.org,
            "--limit", "200",
            "--json", "name,description,pushedAt,isArchived,languages,stargazerCount,"
                      "forkCount,issues,pullRequests,defaultBranchRef,repositoryTopics,diskUsage",
        )
        repos: list[RepoInfo] = []
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        for r in raw:
            pushed = r.get("pushedAt", "")
            dormant = 0
            if pushed:
                try:
                    pushed_dt = datetime.datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                    dormant = (now - pushed_dt).days
                except ValueError:
                    pass

            langs = [l.get("node", {}).get("name", "") for l in r.get("languages", [])] if isinstance(r.get("languages"), list) else []
            topics = [t.get("name", "") for t in r.get("repositoryTopics", [])] if isinstance(r.get("repositoryTopics"), list) else []
            branch_ref = r.get("defaultBranchRef") or {}

            info = RepoInfo(
                name=r["name"],
                full_name=f"{self.org}/{r['name']}",
                description=r.get("description", "") or "",
                archived=r.get("isArchived", False),
                pushed_at=pushed,
                languages=langs,
                stars=r.get("stargazerCount", 0),
                forks=r.get("forkCount", 0),
                open_issues=r.get("issues", {}).get("totalCount", 0) if isinstance(r.get("issues"), dict) else 0,
                open_prs=r.get("pullRequests", {}).get("totalCount", 0) if isinstance(r.get("pullRequests"), dict) else 0,
                default_branch=branch_ref.get("name", "main"),
                topics=topics,
                size_kb=r.get("diskUsage", 0),
                dormant_days=dormant,
            )
            self._score(info)
            repos.append(info)

        repos.sort(key=lambda x: x.resurrection_score, reverse=True)
        return repos

    def _score(self, r: RepoInfo) -> None:
        """Calculate resurrection score and verdict."""
        score = 40
        flags: list[str] = []

        # Language bonus
        hot_langs = {"Python", "TypeScript", "JavaScript", "Go", "Rust"}
        if set(r.languages) & hot_langs:
            score += 10
            flags.append("🔥hot-lang")

        # Activity signals
        if r.open_issues > 0:
            score += 5
            flags.append(f"📋{r.open_issues}-issues")
        if r.open_prs > 0:
            score += 10
            flags.append(f"🔀{r.open_prs}-PRs")
        if r.stars > 0:
            score += min(r.stars * 2, 15)
            flags.append(f"⭐{r.stars}")
        if r.forks > 0:
            score += min(r.forks * 3, 10)
            flags.append(f"🍴{r.forks}")

        # Description = someone cared
        if r.description and len(r.description) > 20:
            score += 5

        # Size = substance
        if r.size_kb > 500:
            score += 5
            flags.append("📦substantial")
        elif r.size_kb < 10:
            score -= 10
            flags.append("🪶tiny")

        # Dormancy penalty
        if r.dormant_days > 365:
            score -= 15
            flags.append(f"💀{r.dormant_days}d-dormant")
        elif r.dormant_days > 180:
            score -= 5
            flags.append(f"😴{r.dormant_days}d-dormant")
        elif r.dormant_days < 30:
            score += 10
            flags.append("✨recent")

        # Archived = explicitly abandoned
        if r.archived:
            score -= 10
            flags.append("🗄️archived")

        score = max(0, min(100, score))
        r.resurrection_score = score
        r.flags = flags

        if score >= 70:
            r.verdict = "🟢 RESURRECT"
        elif score >= 50:
            r.verdict = "🟡 INVESTIGATE"
        elif score >= 30:
            r.verdict = "🟠 SALVAGE PARTS"
        else:
            r.verdict = "⚫ REST IN PEACE"

    def search_code(self, query: str, limit: int = 20) -> list[dict]:
        """Search code across all repos in the org."""
        raw = self._gh(
            "search", "code", query,
            "--owner", self.org,
            "--limit", str(limit),
            "--json", "path,repository",
        )
        results = json.loads(raw) if raw.strip() else []
        # Normalize: repository may be nested dict with fullName/name
        for r in results:
            repo = r.get("repository", {})
            if isinstance(repo, dict):
                r["_repo_name"] = repo.get("fullName", "") or repo.get("name", "") or repo.get("nameWithOwner", "?")
            else:
                r["_repo_name"] = str(repo)
        return results

    def get_branches(self, repo: str) -> list[dict]:
        """Get all branches for a repo."""
        raw = self._gh(
            "api", f"repos/{self.org}/{repo}/branches",
            "--paginate", "--jq", ".[].name",
        )
        return [{"name": b.strip()} for b in raw.strip().splitlines() if b.strip()]

    def get_recent_commits(self, repo: str, limit: int = 20) -> list[dict]:
        """Get recent commits via API."""
        try:
            raw = self._gh(
                "api", f"repos/{self.org}/{repo}/commits",
                "-f", f"per_page={limit}",
                "--jq", '.[].{sha: .sha, author: .commit.author.name, date: .commit.author.date, message: .commit.message}',
            )
            # Parse JSONL
            results = []
            for line in raw.strip().splitlines():
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return results
        except RuntimeError:
            return []


# ============================================================================
# Local Git Forensics (embedded from tools/git_forensics.py)
# ============================================================================

class RepoForensics:
    """Deep forensics on a locally cloned repo."""

    def __init__(self, repo_path: str) -> None:
        self.repo = repo_path

    def _git(self, *args: str) -> str:
        cmd = ["git", "-C", self.repo] + list(args)
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        return r.stdout

    def commit_count(self) -> int:
        return int(self._git("rev-list", "--count", "HEAD").strip() or "0")

    def authors(self) -> list[str]:
        raw = self._git("shortlog", "-sn", "--all", "--no-merges")
        return [line.strip().split("\t", 1)[-1] for line in raw.splitlines() if line.strip()]

    def all_branches(self) -> list[dict]:
        raw = self._git("branch", "-a", "--format=%(refname:short) %(committerdate:iso)")
        branches = []
        for line in raw.splitlines():
            parts = line.strip().split(" ", 1)
            if parts:
                name = parts[0]
                date = parts[1].strip() if len(parts) > 1 else ""
                branches.append({"name": name, "date": date})
        return branches

    def dead_branches(self) -> list[dict]:
        """Branches not merged into default branch."""
        raw = self._git("branch", "-a", "--no-merged", "HEAD",
                         "--format=%(refname:short) %(committerdate:iso) %(subject)")
        dead = []
        for line in raw.splitlines():
            parts = line.strip().split(" ", 2)
            if parts and not parts[0].startswith("origin/HEAD"):
                dead.append({
                    "name": parts[0],
                    "date": parts[1] if len(parts) > 1 else "",
                    "subject": parts[2] if len(parts) > 2 else "",
                })
        return dead

    def churn_files(self, top: int = 20) -> list[dict]:
        """Most changed files."""
        raw = self._git("log", "--all", "--numstat", "--format=")
        counts: dict[str, dict] = {}
        for line in raw.splitlines():
            cols = line.split("\t")
            if len(cols) == 3:
                try:
                    added, deleted, path = int(cols[0]), int(cols[1]), cols[2]
                except ValueError:
                    continue
                if path not in counts:
                    counts[path] = {"path": path, "churn": 0, "commits": 0}
                counts[path]["churn"] += added + deleted
                counts[path]["commits"] += 1
        ranked = sorted(counts.values(), key=lambda x: x["churn"], reverse=True)
        return ranked[:top]

    def ghost_files(self) -> list[dict]:
        """Files in HEAD that were added once and never modified."""
        raw = self._git("log", "--all", "--diff-filter=A", "--name-only", "--format=")
        added_files = set(line.strip() for line in raw.splitlines() if line.strip())
        raw2 = self._git("log", "--all", "--diff-filter=M", "--name-only", "--format=")
        modified_files = set(line.strip() for line in raw2.splitlines() if line.strip())
        # Files that exist in HEAD
        tracked = set(self._git("ls-files").splitlines())
        ghosts = (added_files - modified_files) & tracked
        return [{"path": p} for p in sorted(ghosts)]

    def find_buried_treasure(self) -> list[dict]:
        """Search for valuable patterns in the codebase."""
        treasures: list[dict] = []
        patterns = [
            ("API endpoints", r"@app\.(get|post|put|delete|patch)\("),
            ("API endpoints", r"app\.route\("),
            ("Database models", r"class \w+\(.*Model\)"),
            ("Database models", r"CREATE TABLE"),
            ("Test files", r"def test_|class Test"),
            ("CI/CD config", r"\.github/workflows|\.gitlab-ci|Jenkinsfile"),
            ("Docker", r"FROM |docker-compose"),
            ("Auth/Security", r"jwt|oauth|token|auth|password"),
            ("ML/AI", r"import (torch|tensorflow|sklearn|transformers|openai)"),
            ("CLI tools", r"argparse|click\.command|typer\."),
            ("Web UI", r"<html|ReactDOM|createApp|Flask\("),
            ("Config/Secrets", r"\.env|config\.yaml|settings\.py"),
        ]

        for label, pattern in patterns:
            try:
                result = self._git("grep", "-rlE", pattern, "--", ".")
                files = [f.strip() for f in result.splitlines() if f.strip()]
                if files:
                    treasures.append({
                        "type": label,
                        "pattern": pattern,
                        "files": files[:10],
                        "count": len(files),
                    })
            except Exception:
                pass

        return treasures

    def find_lost_features(self) -> list[dict]:
        """Find features in non-default branches that never merged."""
        dead = self.dead_branches()
        features: list[dict] = []
        for branch in dead[:20]:
            name = branch["name"]
            # Get unique files in this branch
            try:
                raw = self._git("diff", "--name-only", f"HEAD...{name}")
                files = [f.strip() for f in raw.splitlines() if f.strip()]
                if files:
                    # Get commit count unique to this branch
                    count_raw = self._git("rev-list", "--count", f"HEAD..{name}")
                    count = int(count_raw.strip()) if count_raw.strip() else 0
                    if count > 0:
                        features.append({
                            "branch": name,
                            "unique_commits": count,
                            "unique_files": files[:15],
                            "file_count": len(files),
                            "date": branch.get("date", ""),
                        })
            except Exception:
                pass

        features.sort(key=lambda x: x["unique_commits"], reverse=True)
        return features

    def run_full_forensics(self) -> ForensicsResult:
        """Run complete forensic analysis."""
        result = ForensicsResult(repo=self.repo)
        result.total_commits = self.commit_count()
        result.authors = self.authors()
        result.top_churn = self.churn_files(15)
        result.ghosts = self.ghost_files()[:20]
        result.buried_treasure = self.find_buried_treasure()
        result.dead_branches = self.dead_branches()[:20]
        result.lost_features = self.find_lost_features()
        return result


# ============================================================================
# Agentic Orchestrator
# ============================================================================

class Resurrector:
    """The agentic layer — orchestrates scan → clone → forensics → report."""

    def __init__(
        self, org: str = "mikecranesync",
        workspace: str = "",
        top: int = 20,
        use_color: bool = True,
    ) -> None:
        self.org = org
        self.top = top
        self.color = use_color
        self.workspace = Path(workspace or os.path.expanduser("~/resurrection-yard"))
        self.scanner = GitHubScanner(org, use_color)
        self._repos_cache: list[RepoInfo] | None = None

    # -- helpers ---

    def _p(self, text: str, color: str = "white") -> None:
        print(c(text, color, self.color))

    def _header(self, text: str) -> None:
        self._p(f"\n  {'═' * 60}", "gold")
        self._p(f"  ✝  {text}", "gold")
        self._p(f"  {'═' * 60}", "gold")

    def _ensure_workspace(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _clone_repo(self, repo_name: str) -> Path:
        """Shallow clone a repo into the workspace."""
        self._ensure_workspace()
        dest = self.workspace / repo_name
        if dest.exists():
            self._p(f"    Already cloned: {dest}", "gray")
            # Fetch all branches
            subprocess.run(
                ["git", "-C", str(dest), "fetch", "--all"],
                capture_output=True, text=True,
            )
            return dest
        self._p(f"    Cloning {self.org}/{repo_name}...", "cyan")
        subprocess.run(
            ["gh", "repo", "clone", f"{self.org}/{repo_name}", str(dest), "--", "--bare"],
            capture_output=True, text=True,
        )
        return dest

    # ======================================================================
    # Commands
    # ======================================================================

    def cmd_scan(self) -> list[RepoInfo]:
        """Scan all repos and print ranked results."""
        self._header("SCANNING ALL REPOS")
        self._p(f"  Organization: {self.org}\n", "gray")

        repos = self.scanner.list_repos()
        self._repos_cache = repos

        # Summary
        total = len(repos)
        resurrect = sum(1 for r in repos if r.resurrection_score >= 70)
        investigate = sum(1 for r in repos if 50 <= r.resurrection_score < 70)
        salvage = sum(1 for r in repos if 30 <= r.resurrection_score < 50)
        rip = sum(1 for r in repos if r.resurrection_score < 30)
        archived = sum(1 for r in repos if r.archived)

        self._p(f"  Found {total} repos  |  🗄️ {archived} archived", "white")
        self._p(f"  🟢 {resurrect} resurrect  🟡 {investigate} investigate  🟠 {salvage} salvage  ⚫ {rip} RIP\n", "white")

        # Table
        self._p(f"  {'Repo':<35} {'Score':>5}  {'Verdict':<20} {'Lang':<15} Flags", "gray")
        self._p(f"  {'─' * 100}", "gray")

        for r in repos[:self.top]:
            langs = ", ".join(r.languages[:3]) if r.languages else "—"
            flags = " ".join(r.flags[:4])
            score_color = "green" if r.resurrection_score >= 70 else "yellow" if r.resurrection_score >= 50 else "red"
            self._p(
                f"  {r.name:<35} "
                f"{c(str(r.resurrection_score), score_color, self.color):>16}  "
                f"{r.verdict:<20} "
                f"{langs:<15} "
                f"{flags}"
            )

        return repos

    def cmd_dig(self, repo_name: str) -> ForensicsResult:
        """Deep forensics on a single repo (clones it first)."""
        self._header(f"DIGGING INTO {repo_name}")

        clone_path = self._clone_repo(repo_name)
        forensics = RepoForensics(str(clone_path))
        result = forensics.run_full_forensics()

        # Print findings
        self._p(f"\n  📊 {result.total_commits} commits by {len(result.authors)} authors", "white")

        if result.authors:
            self._p(f"\n  👥 Authors: {', '.join(result.authors[:5])}", "gray")

        if result.top_churn:
            self._p(f"\n  🔥 Top Churn Files:", "yellow")
            for f in result.top_churn[:10]:
                self._p(f"     {f['path']:<50} {f['churn']:>6} churn  ({f['commits']} commits)", "white")

        if result.buried_treasure:
            self._p(f"\n  💎 Buried Treasure:", "gold")
            for t in result.buried_treasure:
                self._p(f"     {t['type']:<20} {t['count']} files: {', '.join(t['files'][:3])}", "green")

        if result.dead_branches:
            self._p(f"\n  💀 Dead Branches ({len(result.dead_branches)} unmerged):", "red")
            for b in result.dead_branches[:8]:
                self._p(f"     {b['name']:<40} {b.get('date', '')[:10]}", "gray")

        if result.lost_features:
            self._p(f"\n  🗝️ Lost Features (in dead branches):", "purple")
            for f in result.lost_features[:8]:
                self._p(
                    f"     {f['branch']:<35} {f['unique_commits']:>3} commits, "
                    f"{f['file_count']} files", "cyan"
                )

        if result.ghosts:
            self._p(f"\n  👻 Ghost Files ({len(result.ghosts)} — added once, never touched):", "gray")
            for g in result.ghosts[:8]:
                self._p(f"     {g['path']}", "gray")

        return result

    def cmd_hunt(self, query: str) -> list[dict]:
        """Search code across all repos."""
        self._header(f"HUNTING FOR: {query}")

        results = self.scanner.search_code(query, limit=self.top)

        if not results:
            self._p("  No results found.", "gray")
            return []

        self._p(f"\n  Found {len(results)} matches:\n", "green")
        self._p(f"  {'Repo':<30} {'File':<50}", "gray")
        self._p(f"  {'─' * 80}", "gray")

        for r in results:
            repo = r.get("_repo_name", "?")
            path = r.get("path", "?")
            self._p(f"  {repo:<30} {path:<50}", "white")

        return results

    def cmd_mass_grave(self) -> list[RepoInfo]:
        """Find all archived and deeply dormant repos."""
        self._header("MASS GRAVE — archived & abandoned repos")

        repos = self._repos_cache or self.scanner.list_repos()
        dead = [r for r in repos if r.archived or r.dormant_days > 365]
        dead.sort(key=lambda x: x.dormant_days, reverse=True)

        self._p(f"\n  Found {len(dead)} dead/dormant repos:\n", "red")
        self._p(f"  {'Repo':<35} {'Dormant':>8}  {'Archived':>9}  {'Lang':<15} Description", "gray")
        self._p(f"  {'─' * 100}", "gray")

        for r in dead[:self.top]:
            arch = "🗄️ yes" if r.archived else "   no"
            langs = ", ".join(r.languages[:2]) if r.languages else "—"
            desc = (r.description[:35] + "…") if len(r.description) > 35 else r.description
            dormant_color = "red" if r.dormant_days > 365 else "yellow"
            self._p(
                f"  {r.name:<35} "
                f"{c(f'{r.dormant_days}d', dormant_color, self.color):>19}  "
                f"{arch:>9}  "
                f"{langs:<15} "
                f"{desc}"
            )

        return dead

    def cmd_autopsy(self, repo_name: str) -> None:
        """Full autopsy: clone → forensics → HTML report."""
        self._header(f"FULL AUTOPSY: {repo_name}")

        result = self.cmd_dig(repo_name)

        # Generate HTML report
        html = self._generate_repo_html(repo_name, result)
        report_dir = self.workspace / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"autopsy-{repo_name}.html"
        report_path.write_text(html, encoding="utf-8")

        self._p(f"\n  ✅ Autopsy report: {report_path}", "green")

    def cmd_resurrect(self, repo_name: str) -> None:
        """Clone + analyze + generate resurrection plan."""
        self._header(f"RESURRECTING: {repo_name}")

        result = self.cmd_dig(repo_name)

        # Generate resurrection plan
        self._p(f"\n  {'═' * 50}", "gold")
        self._p(f"  ✝  RESURRECTION PLAN: {repo_name}", "gold")
        self._p(f"  {'═' * 50}\n", "gold")

        plan_items: list[str] = []

        if result.buried_treasure:
            self._p("  Phase 1: EXTRACT valuable patterns", "green")
            for t in result.buried_treasure[:5]:
                item = f"    → Extract {t['type']} from {', '.join(t['files'][:2])}"
                self._p(item, "white")
                plan_items.append(item)

        if result.lost_features:
            self._p("\n  Phase 2: RECOVER lost features from dead branches", "cyan")
            for f in result.lost_features[:5]:
                item = f"    → Cherry-pick {f['unique_commits']} commits from {f['branch']}"
                self._p(item, "white")
                plan_items.append(item)

        if result.top_churn:
            self._p("\n  Phase 3: STABILIZE high-churn files", "yellow")
            for ch in result.top_churn[:3]:
                item = f"    → Review {ch['path']} ({ch['churn']} churn)"
                self._p(item, "white")
                plan_items.append(item)

        self._p("\n  Phase 4: SHIP", "gold")
        self._p("    → Create new repo or merge into monorepo", "white")
        self._p("    → Add tests for extracted code", "white")
        self._p("    → Deploy and verify", "white")

        # Save plan
        plan_path = self.workspace / "reports" / f"plan-{repo_name}.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_md = f"# Resurrection Plan: {repo_name}\n\n"
        plan_md += f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        plan_md += f"## Summary\n- {result.total_commits} commits, {len(result.authors)} authors\n"
        plan_md += f"- {len(result.buried_treasure)} treasure types found\n"
        plan_md += f"- {len(result.lost_features)} lost features in dead branches\n"
        plan_md += f"- {len(result.ghosts)} ghost files\n\n"
        for item in plan_items:
            plan_md += f"{item}\n"
        plan_path.write_text(plan_md, encoding="utf-8")

        self._p(f"\n  ✅ Plan saved: {plan_path}", "green")

    def cmd_report(self) -> None:
        """Full HTML report of all findings."""
        self._header("GENERATING FULL REPORT")

        repos = self._repos_cache or self.scanner.list_repos()
        self._repos_cache = repos

        html = self._generate_full_html(repos)
        report_dir = self.workspace / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"resurrection-report-{datetime.datetime.now().strftime('%Y%m%d')}.html"
        report_path.write_text(html, encoding="utf-8")

        self._p(f"\n  ✅ Full report: {report_path}", "green")
        self._p(f"  Open in browser for interactive dashboard\n", "gray")

    # ======================================================================
    # HTML generation
    # ======================================================================

    def _generate_repo_html(self, repo_name: str, result: ForensicsResult) -> str:
        esc = html_mod.escape

        treasure_html = ""
        for t in result.buried_treasure:
            files = ", ".join(f"<code>{esc(f)}</code>" for f in t["files"][:5])
            treasure_html += f'<div class="treasure-item"><span class="treasure-type">{esc(t["type"])}</span> <span class="treasure-count">{t["count"]} files</span><br>{files}</div>\n'

        branches_html = ""
        for b in result.dead_branches[:15]:
            branches_html += f'<tr><td class="file">{esc(b["name"])}</td><td>{esc(b.get("date", "")[:10])}</td></tr>\n'

        features_html = ""
        for f in result.lost_features[:10]:
            files = ", ".join(f"<code>{esc(p)}</code>" for p in f["unique_files"][:5])
            features_html += f'<div class="feature-item"><strong>{esc(f["branch"])}</strong> — {f["unique_commits"]} commits, {f["file_count"]} files<br><span class="files">{files}</span></div>\n'

        churn_html = ""
        max_churn = result.top_churn[0]["churn"] if result.top_churn else 1
        for ch in result.top_churn[:15]:
            pct = ch["churn"] / max_churn * 100
            churn_html += f'<tr><td class="file">{esc(ch["path"])}</td><td class="num">{ch["churn"]}</td><td class="num">{ch["commits"]}</td><td><div class="bar" style="width:{pct:.0f}%"></div></td></tr>\n'

        return self._html_shell(
            f"Autopsy: {repo_name}",
            f"""
            <div class="stats">
                <div class="stat"><div class="val">{result.total_commits}</div><div class="lbl">Commits</div></div>
                <div class="stat"><div class="val">{len(result.authors)}</div><div class="lbl">Authors</div></div>
                <div class="stat"><div class="val">{len(result.dead_branches)}</div><div class="lbl">Dead Branches</div></div>
                <div class="stat"><div class="val">{len(result.lost_features)}</div><div class="lbl">Lost Features</div></div>
                <div class="stat"><div class="val">{len(result.buried_treasure)}</div><div class="lbl">Treasure Types</div></div>
            </div>

            <div class="section open"><div class="section-head" onclick="this.parentElement.classList.toggle('open')"><h2>💎 Buried Treasure</h2><span class="toggle">▸</span></div>
            <div class="section-body">{treasure_html or '<p class="muted">No treasure found</p>'}</div></div>

            <div class="section open"><div class="section-head" onclick="this.parentElement.classList.toggle('open')"><h2>🗝️ Lost Features</h2><span class="toggle">▸</span></div>
            <div class="section-body">{features_html or '<p class="muted">No lost features</p>'}</div></div>

            <div class="section"><div class="section-head" onclick="this.parentElement.classList.toggle('open')"><h2>🔥 File Churn</h2><span class="toggle">▸</span></div>
            <div class="section-body"><table><thead><tr><th>File</th><th>Churn</th><th>Commits</th><th>Bar</th></tr></thead><tbody>{churn_html}</tbody></table></div></div>

            <div class="section"><div class="section-head" onclick="this.parentElement.classList.toggle('open')"><h2>💀 Dead Branches</h2><span class="toggle">▸</span></div>
            <div class="section-body"><table><thead><tr><th>Branch</th><th>Last Commit</th></tr></thead><tbody>{branches_html}</tbody></table></div></div>
            """,
        )

    def _generate_full_html(self, repos: list[RepoInfo]) -> str:
        esc = html_mod.escape
        total = len(repos)
        resurrect = sum(1 for r in repos if r.resurrection_score >= 70)
        investigate = sum(1 for r in repos if 50 <= r.resurrection_score < 70)
        archived = sum(1 for r in repos if r.archived)

        rows = ""
        for r in repos:
            score_cls = "score-high" if r.resurrection_score >= 70 else "score-med" if r.resurrection_score >= 50 else "score-low"
            langs = ", ".join(r.languages[:3]) if r.languages else "—"
            flags = " ".join(r.flags[:3])
            desc = esc((r.description[:40] + "…") if len(r.description) > 40 else r.description)
            rows += f"""<tr>
                <td class="file"><a href="https://github.com/{esc(r.full_name)}" target="_blank">{esc(r.name)}</a></td>
                <td class="num {score_cls}">{r.resurrection_score}</td>
                <td>{r.verdict}</td>
                <td>{langs}</td>
                <td class="num">{r.dormant_days}d</td>
                <td class="flags">{flags}</td>
                <td class="desc">{desc}</td>
            </tr>\n"""

        return self._html_shell(
            f"Resurrection Report — {self.org}",
            f"""
            <div class="stats">
                <div class="stat"><div class="val">{total}</div><div class="lbl">Repos</div></div>
                <div class="stat"><div class="val">{resurrect}</div><div class="lbl">🟢 Resurrect</div></div>
                <div class="stat"><div class="val">{investigate}</div><div class="lbl">🟡 Investigate</div></div>
                <div class="stat"><div class="val">{archived}</div><div class="lbl">🗄️ Archived</div></div>
            </div>

            <div class="section open"><div class="section-head" onclick="this.parentElement.classList.toggle('open')"><h2>✝ All Repos — Ranked by Resurrection Score</h2><span class="toggle">▸</span></div>
            <div class="section-body">
            <table><thead><tr><th>Repo</th><th>Score</th><th>Verdict</th><th>Languages</th><th>Dormant</th><th>Flags</th><th>Description</th></tr></thead>
            <tbody>{rows}</tbody></table>
            </div></div>
            """,
        )

    def _html_shell(self, title: str, body: str) -> str:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_mod.escape(title)}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e0e0e0;line-height:1.5}}
a{{color:#00ff88;text-decoration:none}} a:hover{{text-decoration:underline}}
.header{{background:linear-gradient(135deg,#1a1a2e 0%,#2a1a2e 50%,#1a2e1a 100%);padding:24px 32px;border-bottom:2px solid #4a2a0a;text-align:center}}
.header h1{{color:#ffd700;font-size:1.6rem;letter-spacing:3px}}
.header .cross{{font-size:2rem;margin-bottom:8px;display:block}}
.header p{{color:#888;font-size:0.85rem;margin-top:4px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;margin:20px 24px}}
.stat{{background:#12121a;border:1px solid #2a2a3a;border-radius:8px;padding:12px 20px;min-width:100px;text-align:center}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#ffd700}}
.stat .lbl{{font-size:0.7rem;color:#888;text-transform:uppercase;letter-spacing:1px}}
.section{{margin:16px 24px;background:#12121a;border:1px solid #2a2a3a;border-radius:12px;overflow:hidden}}
.section-head{{background:#1a1a2e;padding:14px 20px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none}}
.section-head:hover{{background:#1e1e35}}
.section-head .toggle{{color:#666;font-size:1.2rem;transition:transform .2s}}
.section-body{{padding:20px;display:none}}
.section.open .section-body{{display:block}}
.section.open .toggle{{transform:rotate(90deg)}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{text-align:left;color:#888;padding:6px 10px;border-bottom:1px solid #333;font-weight:600;white-space:nowrap}}
td{{padding:6px 10px;border-bottom:1px solid #1a1a2a}}
tr:hover{{background:#1a1a2a}}
.file{{font-family:'SF Mono',Monaco,monospace;font-size:0.78rem;color:#ccc}} .file a{{color:#00ff88}}
.num{{text-align:right;font-family:'SF Mono',Monaco,monospace}}
.flags{{font-size:0.78rem}} .desc{{color:#888;font-size:0.78rem;max-width:250px}}
.score-high{{color:#00ff88;font-weight:700}} .score-med{{color:#ffaa00}} .score-low{{color:#ff4444}}
.bar{{height:14px;background:linear-gradient(90deg,#ffd700,#ff8800);border-radius:3px;min-width:2px}}
.muted{{color:#666;font-style:italic}}
.treasure-item{{background:#1a1a2a;padding:10px 14px;border-radius:8px;margin-bottom:8px;border-left:3px solid #ffd700}}
.treasure-type{{color:#ffd700;font-weight:600}} .treasure-count{{color:#888;font-size:0.8rem}}
.treasure-item code{{color:#00ff88;font-size:0.78rem}}
.feature-item{{background:#1a1a2a;padding:10px 14px;border-radius:8px;margin-bottom:8px;border-left:3px solid #0af}}
.feature-item .files{{color:#888;font-size:0.78rem}} .feature-item code{{color:#76b900;font-size:0.78rem}}
.footer{{text-align:center;padding:20px;color:#444;font-size:0.75rem;border-top:1px solid #1a1a2a;margin-top:24px}}
.footer span{{color:#ffd700}}
</style></head><body>
<div class="header"><span class="cross">✝</span><h1>JESUS H CHRIST</h1><p>Repo Resurrector — {html_mod.escape(now)}</p></div>
{body}
<div class="footer">Generated by <span>Jesus H Christ — Repo Resurrector</span> v{VERSION}</div>
</body></html>"""


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    _fix_encoding()

    parser = argparse.ArgumentParser(
        prog="resurrector",
        description="Jesus H Christ — Agentic Repo Resurrector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              resurrector.py scan                    Scan all repos
              resurrector.py dig remoteme            Deep forensics on a repo
              resurrector.py hunt "FastAPI"           Search code across repos
              resurrector.py autopsy remoteme         Full autopsy with HTML report
              resurrector.py mass-grave               Find all dead repos
              resurrector.py resurrect remoteme       Analyze + generate resurrection plan
              resurrector.py report                   Full HTML dashboard of all repos
        """),
    )
    parser.add_argument("command",
                        choices=["scan", "dig", "hunt", "autopsy", "mass-grave",
                                 "resurrect", "report"],
                        help="What to do")
    parser.add_argument("target", nargs="?", default="",
                        help="Repo name or search query")
    parser.add_argument("--org", default="mikecranesync", help="GitHub org/user")
    parser.add_argument("--top", type=int, default=20, help="Max results")
    parser.add_argument("--workspace", default="", help="Where to clone repos")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    parser.add_argument("--version", action="version", version=f"resurrector {VERSION}")

    args = parser.parse_args()

    print(c(BANNER, "gold", not args.no_color))

    agent = Resurrector(
        org=args.org,
        workspace=args.workspace,
        top=args.top,
        use_color=not args.no_color,
    )

    cmd = args.command
    if cmd == "scan":
        agent.cmd_scan()
    elif cmd == "dig":
        if not args.target:
            parser.error("dig requires a repo name")
        agent.cmd_dig(args.target)
    elif cmd == "hunt":
        if not args.target:
            parser.error("hunt requires a search query")
        agent.cmd_hunt(args.target)
    elif cmd == "autopsy":
        if not args.target:
            parser.error("autopsy requires a repo name")
        agent.cmd_autopsy(args.target)
    elif cmd == "mass-grave":
        agent.cmd_scan()
        agent.cmd_mass_grave()
    elif cmd == "resurrect":
        if not args.target:
            parser.error("resurrect requires a repo name")
        agent.cmd_resurrect(args.target)
    elif cmd == "report":
        agent.cmd_scan()
        agent.cmd_report()


if __name__ == "__main__":
    main()

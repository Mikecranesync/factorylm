#!/usr/bin/env python3
"""
FactoryLM Git Forensics — zero-dependency retroactive git analysis.

Single-file, stdlib-only (Python 3.9+). Calls git CLI via subprocess.

Usage:
    python tools/git_forensics.py report
    python tools/git_forensics.py churn --since "30 days ago" --top 10
    python tools/git_forensics.py hotspots --path services/
    python tools/git_forensics.py suspects --since "2 weeks ago"
    python tools/git_forensics.py blame-age services/telegram/factorylm_bot.py
    python tools/git_forensics.py ownership --path cosmos/
    python tools/git_forensics.py ghosts
    python tools/git_forensics.py diff-impact --top 20
    python tools/git_forensics.py timeline --since "90 days ago"
    python tools/git_forensics.py bisect-prep --test "pytest tests/" --good abc123
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
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ============================================================================
# Constants
# ============================================================================

VERSION = "1.0.0"
RECORD_SEP = "<<<GF>>>"
FIELD_SEP = "<<<F>>>"
ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[38;2;0;255;136m",
    "nvidia": "\033[38;2;118;185;0m",
    "red": "\033[38;2;255;68;68m",
    "yellow": "\033[38;2;255;170;0m",
    "cyan": "\033[38;2;0;200;255m",
    "gray": "\033[38;2;120;120;120m",
    "white": "\033[97m",
}

# ============================================================================
# Data classes
# ============================================================================


@dataclass
class Commit:
    sha: str
    author: str
    email: str
    date: datetime.datetime
    subject: str
    files: list[FileChange] = field(default_factory=list)


@dataclass
class FileChange:
    added: int
    deleted: int
    path: str

    @property
    def churn(self) -> int:
        return self.added + self.deleted


@dataclass
class FileStats:
    path: str
    total_churn: int = 0
    commit_count: int = 0
    authors: set[str] = field(default_factory=set)
    last_touched: datetime.datetime | None = None
    first_touched: datetime.datetime | None = None

    @property
    def hotspot_score(self) -> float:
        return self.total_churn * len(self.authors) * math.log1p(self.commit_count)


# ============================================================================
# Color helpers
# ============================================================================


def c(text: str, color: str, use_color: bool = True) -> str:
    if not use_color:
        return str(text)
    return f"{ANSI.get(color, '')}{text}{ANSI['reset']}"


def progress(current: int, total: int, label: str = "", width: int = 30) -> None:
    pct = current / max(total, 1)
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    sys.stderr.write(f"\r  {bar} {pct:.0%} {label}")
    if current >= total:
        sys.stderr.write("\n")
    sys.stderr.flush()


# ============================================================================
# Git wrapper
# ============================================================================


class GitForensics:
    """Core git analysis engine — all git interaction goes through here."""

    def __init__(
        self,
        repo_path: str = ".",
        since: str = "",
        until: str = "",
        path_filter: str = "",
        branch: str = "",
        top: int = 20,
        use_color: bool = True,
    ) -> None:
        self.repo = repo_path
        self.since = since
        self.until = until
        self.path_filter = path_filter
        self.branch = branch
        self.top = top
        self.color = use_color
        self._commits_cache: list[Commit] | None = None

    # -- low level ----------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> str:
        cmd = ["git", "-C", self.repo] + list(args)
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if check and r.returncode != 0:
            raise RuntimeError(f"git error: {' '.join(cmd)}\n{r.stderr.strip()}")
        return r.stdout

    def _log_args(self, extra: list[str] | None = None) -> list[str]:
        args: list[str] = []
        if self.branch:
            args.append(self.branch)
        if self.since:
            args += ["--since", self.since]
        if self.until:
            args += ["--until", self.until]
        if extra:
            args += extra
        if self.path_filter:
            args += ["--", self.path_filter]
        return args

    # -- parsed commits -----------------------------------------------------

    def commits(self, force: bool = False) -> list[Commit]:
        if self._commits_cache is not None and not force:
            return self._commits_cache

        fmt = FIELD_SEP.join(["%H", "%an", "%ae", "%aI", "%s"])
        raw = self._git(
            "log",
            "--first-parent",
            f"--format={RECORD_SEP}{fmt}",
            "--numstat",
            *self._log_args(),
        )

        commits: list[Commit] = []
        for block in raw.split(RECORD_SEP):
            block = block.strip()
            if not block:
                continue
            header, *rest = block.split("\n", 1)
            parts = header.split(FIELD_SEP)
            if len(parts) < 5:
                continue
            sha, author, email, date_str, subject = parts[0], parts[1], parts[2], parts[3], parts[4]
            try:
                dt = datetime.datetime.fromisoformat(date_str)
            except ValueError:
                continue

            files: list[FileChange] = []
            if rest:
                for line in rest[0].strip().splitlines():
                    cols = line.split("\t")
                    if len(cols) == 3:
                        a, d, p = cols
                        try:
                            files.append(FileChange(int(a), int(d), p))
                        except ValueError:
                            # binary file shows "-"
                            files.append(FileChange(0, 0, p))

            commits.append(Commit(sha, author, email, dt, subject, files))

        self._commits_cache = commits
        return commits

    def file_stats(self) -> dict[str, FileStats]:
        stats: dict[str, FileStats] = {}
        for cm in self.commits():
            for fc in cm.files:
                s = stats.setdefault(fc.path, FileStats(path=fc.path))
                s.total_churn += fc.churn
                s.commit_count += 1
                s.authors.add(cm.author)
                if s.last_touched is None or cm.date > s.last_touched:
                    s.last_touched = cm.date
                if s.first_touched is None or cm.date < s.first_touched:
                    s.first_touched = cm.date
        return stats

    def summary_stats(self) -> dict[str, Any]:
        commits = self.commits()
        if not commits:
            return {"total_commits": 0}
        authors = {cm.author for cm in commits}
        files = {fc.path for cm in commits for fc in cm.files}
        first = min(cm.date for cm in commits)
        last = max(cm.date for cm in commits)
        span = (last - first).days or 1
        return {
            "total_commits": len(commits),
            "authors": len(authors),
            "files_touched": len(files),
            "first_commit": first.strftime("%Y-%m-%d"),
            "last_commit": last.strftime("%Y-%m-%d"),
            "span_days": span,
            "commits_per_day": round(len(commits) / span, 1),
        }

    # ======================================================================
    # Subcommands
    # ======================================================================

    # -- churn --------------------------------------------------------------

    def churn(self) -> list[FileStats]:
        stats = self.file_stats()
        ranked = sorted(stats.values(), key=lambda s: s.total_churn, reverse=True)
        return ranked[: self.top]

    def print_churn(self) -> None:
        ranked = self.churn()
        if not ranked:
            print("No commits found.")
            return
        max_churn = ranked[0].total_churn
        print(c("\n  FILE CHURN — most changed files\n", "bold", self.color))
        print(c(f"  {'File':<55} {'Churn':>7} {'Commits':>8} {'Authors':>8}  Bar", "gray", self.color))
        print(c("  " + "─" * 95, "gray", self.color))
        for s in ranked:
            bar_w = int(30 * s.total_churn / max(max_churn, 1))
            bar = "█" * bar_w
            print(
                f"  {s.path:<55} "
                f"{c(str(s.total_churn), 'green', self.color):>18} "
                f"{s.commit_count:>8} "
                f"{len(s.authors):>8}  "
                f"{c(bar, 'nvidia', self.color)}"
            )

    # -- hotspots -----------------------------------------------------------

    def hotspots(self) -> list[FileStats]:
        stats = self.file_stats()
        ranked = sorted(stats.values(), key=lambda s: s.hotspot_score, reverse=True)
        return ranked[: self.top]

    def print_hotspots(self) -> None:
        ranked = self.hotspots()
        if not ranked:
            print("No commits found.")
            return
        max_score = ranked[0].hotspot_score
        print(c("\n  HOTSPOTS — churn × authors × log(commits)\n", "bold", self.color))
        print(c(f"  {'File':<50} {'Score':>8} {'Churn':>7} {'Auth':>5} {'Cm':>4}  Risk", "gray", self.color))
        print(c("  " + "─" * 90, "gray", self.color))
        for s in ranked:
            bar_w = int(25 * s.hotspot_score / max(max_score, 1))
            risk = "🔴" if bar_w > 18 else "🟡" if bar_w > 10 else "🟢"
            bar = "█" * bar_w
            print(
                f"  {s.path:<50} "
                f"{s.hotspot_score:>8.0f} "
                f"{s.total_churn:>7} "
                f"{len(s.authors):>5} "
                f"{s.commit_count:>4}  "
                f"{risk} {c(bar, 'red' if bar_w > 18 else 'yellow' if bar_w > 10 else 'green', self.color)}"
            )

    # -- suspects -----------------------------------------------------------

    def suspects(self) -> list[dict]:
        commits = self.commits()
        scored: list[dict] = []
        for i, cm in enumerate(commits):
            if not cm.files:
                continue
            total_churn = sum(fc.churn for fc in cm.files)
            n_files = len(cm.files)
            hour = cm.date.hour
            late_night = 1.5 if (hour >= 23 or hour < 5) else 1.0
            # Check if next commit (older) was a "fix" for this
            has_followup_fix = False
            if i > 0:
                prev = commits[i - 1]
                if re.search(r"\bfix\b", prev.subject, re.I) and (cm.date - prev.date).total_seconds() < 86400:
                    has_followup_fix = True
            fix_mult = 1.8 if has_followup_fix else 1.0
            is_fix = 1.3 if re.search(r"\bfix\b", cm.subject, re.I) else 1.0

            score = total_churn * math.log1p(n_files) * late_night * fix_mult * is_fix
            flags: list[str] = []
            if late_night > 1:
                flags.append("🌙late")
            if has_followup_fix:
                flags.append("🔧fix-after")
            if is_fix > 1:
                flags.append("🩹is-fix")
            if n_files > 10:
                flags.append("💣wide")
            if total_churn > 500:
                flags.append("📦huge")

            scored.append({
                "sha": cm.sha[:8],
                "author": cm.author,
                "date": cm.date.strftime("%Y-%m-%d %H:%M"),
                "subject": cm.subject[:50],
                "score": score,
                "churn": total_churn,
                "files": n_files,
                "flags": flags,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: self.top]

    def print_suspects(self) -> None:
        ranked = self.suspects()
        if not ranked:
            print("No commits found.")
            return
        print(c("\n  SUSPECTS — commits most likely to introduce bugs\n", "bold", self.color))
        print(c(f"  {'SHA':<10} {'Date':<18} {'Score':>7} {'Churn':>6} {'Files':>5}  {'Subject':<40} Flags", "gray", self.color))
        print(c("  " + "─" * 110, "gray", self.color))
        for s in ranked:
            flags = " ".join(s["flags"])
            color = "red" if s["score"] > 1000 else "yellow" if s["score"] > 200 else "white"
            print(
                f"  {c(s['sha'], 'cyan', self.color):<21} "
                f"{s['date']:<18} "
                f"{c(f'{s[\"score\"]:.0f}', color, self.color):>18} "
                f"{s['churn']:>6} "
                f"{s['files']:>5}  "
                f"{s['subject']:<40} "
                f"{flags}"
            )

    # -- ghosts -------------------------------------------------------------

    def ghosts(self) -> list[dict]:
        stats = self.file_stats()
        # Files touched only once (added, never modified)
        ghosts = []
        for s in stats.values():
            if s.commit_count == 1:
                # Verify it still exists
                check = self._git("ls-files", s.path, check=False).strip()
                if check:
                    age_days = (datetime.datetime.now(tz=s.first_touched.tzinfo) - s.first_touched).days if s.first_touched else 0
                    ghosts.append({
                        "path": s.path,
                        "author": list(s.authors)[0] if s.authors else "?",
                        "date": s.first_touched.strftime("%Y-%m-%d") if s.first_touched else "?",
                        "age_days": age_days,
                    })
        ghosts.sort(key=lambda x: x["age_days"], reverse=True)
        return ghosts[: self.top]

    def print_ghosts(self) -> None:
        ranked = self.ghosts()
        if not ranked:
            print("No ghost files found.")
            return
        print(c("\n  GHOSTS — files added once, never touched again\n", "bold", self.color))
        print(c(f"  {'File':<55} {'Author':<20} {'Added':<12} {'Age':>6}", "gray", self.color))
        print(c("  " + "─" * 95, "gray", self.color))
        for g in ranked:
            age_str = f"{g['age_days']}d"
            color = "red" if g["age_days"] > 180 else "yellow" if g["age_days"] > 60 else "white"
            print(
                f"  {g['path']:<55} "
                f"{g['author']:<20} "
                f"{g['date']:<12} "
                f"{c(age_str, color, self.color):>17}"
            )

    # -- ownership ----------------------------------------------------------

    def ownership(self) -> dict[str, dict[str, int]]:
        """Returns {directory: {author: lines_changed}}."""
        result: dict[str, dict[str, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
        for cm in self.commits():
            for fc in cm.files:
                dir_name = str(Path(fc.path).parent)
                if dir_name == ".":
                    dir_name = "(root)"
                result[dir_name][cm.author] += fc.churn
        return dict(result)

    def print_ownership(self) -> None:
        ownership = self.ownership()
        if not ownership:
            print("No commits found.")
            return
        # Sort directories by total churn
        dirs_sorted = sorted(ownership.items(), key=lambda x: sum(x[1].values()), reverse=True)
        print(c("\n  CODE OWNERSHIP — who owns what (by lines changed)\n", "bold", self.color))
        for dir_name, authors in dirs_sorted[: self.top]:
            total = sum(authors.values())
            sorted_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)
            print(c(f"\n  📁 {dir_name}  ", "bold", self.color) + c(f"({total} lines changed)", "gray", self.color))
            for author, lines in sorted_authors[:5]:
                pct = lines / max(total, 1) * 100
                bar_w = int(25 * pct / 100)
                bar = "█" * bar_w + "░" * (25 - bar_w)
                print(f"     {author:<25} {c(bar, 'green', self.color)} {pct:>5.1f}% ({lines})")

    # -- blame-age ----------------------------------------------------------

    def blame_age(self, filepath: str) -> list[dict]:
        """Get blame info for a file — returns list of {line, author, date, age_days, content}."""
        raw = self._git("blame", "--line-porcelain", filepath, check=False)
        if not raw.strip():
            return []

        results: list[dict] = []
        current: dict[str, Any] = {}
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        for line in raw.splitlines():
            if line.startswith("author "):
                current["author"] = line[7:]
            elif line.startswith("author-time "):
                ts = int(line[12:])
                dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
                current["date"] = dt
                current["age_days"] = (now - dt).days
            elif line.startswith("\t"):
                current["content"] = line[1:]
                results.append(current)
                current = {}

        return results

    def print_blame_age(self, filepath: str) -> None:
        blame = self.blame_age(filepath)
        if not blame:
            print(f"No blame data for {filepath}")
            return
        # Aggregate by age buckets
        buckets = {"< 7 days": 0, "7-30 days": 0, "30-90 days": 0, "90-180 days": 0, "180+ days": 0}
        for b in blame:
            age = b.get("age_days", 0)
            if age < 7:
                buckets["< 7 days"] += 1
            elif age < 30:
                buckets["7-30 days"] += 1
            elif age < 90:
                buckets["30-90 days"] += 1
            elif age < 180:
                buckets["90-180 days"] += 1
            else:
                buckets["180+ days"] += 1

        total = len(blame)
        authors = collections.Counter(b.get("author", "?") for b in blame)
        newest = min((b.get("age_days", 999) for b in blame), default=0)
        oldest = max((b.get("age_days", 0) for b in blame), default=0)

        print(c(f"\n  BLAME AGE — {filepath}\n", "bold", self.color))
        print(f"  Total lines: {total}  |  Newest: {newest}d ago  |  Oldest: {oldest}d ago\n")

        colors = ["green", "nvidia", "yellow", "yellow", "red"]
        for (label, count), clr in zip(buckets.items(), colors):
            pct = count / max(total, 1) * 100
            bar_w = int(30 * pct / 100)
            bar = "█" * bar_w
            print(f"  {label:<14} {c(bar, clr, self.color):<42} {count:>5} lines ({pct:.1f}%)")

        print(c(f"\n  Top authors:", "gray", self.color))
        for author, count in authors.most_common(5):
            print(f"    {author:<30} {count} lines ({count/max(total,1)*100:.1f}%)")

    # -- diff-impact --------------------------------------------------------

    def diff_impact(self) -> list[dict]:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        scored: list[dict] = []
        for cm in self.commits():
            if not cm.files:
                continue
            total_churn = sum(fc.churn for fc in cm.files)
            n_files = len(cm.files)
            age_days = max((now - cm.date.replace(tzinfo=datetime.timezone.utc)).days, 1) if cm.date.tzinfo is None else max((now - cm.date).days, 1)
            recency = 1.0 / math.log1p(age_days)
            score = total_churn * n_files * recency
            scored.append({
                "sha": cm.sha[:8],
                "author": cm.author,
                "date": cm.date.strftime("%Y-%m-%d"),
                "subject": cm.subject[:45],
                "score": score,
                "churn": total_churn,
                "files": n_files,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: self.top]

    def print_diff_impact(self) -> None:
        ranked = self.diff_impact()
        if not ranked:
            print("No commits found.")
            return
        print(c("\n  DIFF IMPACT — files × churn × recency\n", "bold", self.color))
        print(c(f"  {'SHA':<10} {'Date':<12} {'Impact':>8} {'Churn':>7} {'Files':>6}  Subject", "gray", self.color))
        print(c("  " + "─" * 95, "gray", self.color))
        for s in ranked:
            color = "red" if s["score"] > 500 else "yellow" if s["score"] > 100 else "white"
            print(
                f"  {c(s['sha'], 'cyan', self.color):<21} "
                f"{s['date']:<12} "
                f"{c(f'{s[\"score\"]:.0f}', color, self.color):>19} "
                f"{s['churn']:>7} "
                f"{s['files']:>6}  "
                f"{s['subject']}"
            )

    # -- timeline -----------------------------------------------------------

    def timeline(self) -> list[dict]:
        commits = self.commits()
        by_day: dict[str, dict] = collections.OrderedDict()
        for cm in reversed(commits):
            day = cm.date.strftime("%Y-%m-%d")
            if day not in by_day:
                by_day[day] = {"date": day, "count": 0, "authors": set(), "churn": 0, "subjects": []}
            by_day[day]["count"] += 1
            by_day[day]["authors"].add(cm.author)
            by_day[day]["churn"] += sum(fc.churn for fc in cm.files)
            if len(by_day[day]["subjects"]) < 3:
                by_day[day]["subjects"].append(cm.subject[:60])
        # Convert sets for display
        result = []
        for d in by_day.values():
            d["authors"] = list(d["authors"])
            result.append(d)
        return result

    def print_timeline(self) -> None:
        days = self.timeline()
        if not days:
            print("No commits found.")
            return
        max_count = max(d["count"] for d in days)
        print(c("\n  COMMIT TIMELINE\n", "bold", self.color))
        for d in days:
            bar_w = int(40 * d["count"] / max(max_count, 1))
            bar = "█" * bar_w
            authors_str = ", ".join(d["authors"][:2])
            subj = d["subjects"][0] if d["subjects"] else ""
            print(
                f"  {d['date']}  "
                f"{c(bar, 'green', self.color):<52} "
                f"{d['count']:>3} commits  "
                f"{c(authors_str, 'gray', self.color)}"
            )

    # -- bisect-prep --------------------------------------------------------

    def bisect_prep(self, test_cmd: str, good_sha: str = "") -> str:
        commits = self.commits()
        if not commits:
            return "No commits to bisect."
        bad_sha = commits[0].sha[:10]
        if not good_sha:
            good_sha = commits[-1].sha[:10] if len(commits) > 1 else "HEAD~20"

        script = textwrap.dedent(f"""\
            #!/bin/bash
            # FactoryLM Git Forensics — auto-bisect script
            # Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
            #
            # This script finds the exact commit that broke your test.
            # Review and edit before running.

            set -e

            echo "=== Starting git bisect ==="
            echo "Bad:  {bad_sha} (latest)"
            echo "Good: {good_sha}"
            echo "Test: {test_cmd}"
            echo ""

            git bisect start {bad_sha} {good_sha}
            git bisect run {test_cmd}

            echo ""
            echo "=== Bisect complete ==="
            echo "First bad commit:"
            git bisect visualize --oneline | head -1
            git bisect reset
        """)
        return script

    def print_bisect_prep(self, test_cmd: str, good_sha: str = "") -> None:
        script = self.bisect_prep(test_cmd, good_sha)
        print(c("\n  BISECT SCRIPT\n", "bold", self.color))
        print(script)
        # Also write to file
        out_path = Path(self.repo) / "bisect-run.sh"
        out_path.write_text(script, encoding="utf-8")
        print(c(f"\n  Written to: {out_path}", "green", self.color))
        print(c("  Run with: bash bisect-run.sh", "gray", self.color))

    # ======================================================================
    # HTML Report
    # ======================================================================

    def generate_html(self, output: str = "git-forensics-report.html") -> str:
        summary = self.summary_stats()
        churn = self.churn()
        hotspots_list = self.hotspots()
        suspects_list = self.suspects()
        ghosts_list = self.ghosts()
        timeline_data = self.timeline()
        ownership_data = self.ownership()
        impact_list = self.diff_impact()

        def esc(s: str) -> str:
            return html_mod.escape(str(s))

        # Build churn table rows
        churn_rows = ""
        max_churn = churn[0].total_churn if churn else 1
        for s in churn:
            pct = s.total_churn / max_churn * 100
            churn_rows += f"""<tr>
                <td class="file">{esc(s.path)}</td>
                <td class="num">{s.total_churn}</td>
                <td class="num">{s.commit_count}</td>
                <td class="num">{len(s.authors)}</td>
                <td><div class="bar" style="width:{pct:.0f}%"></div></td>
            </tr>\n"""

        # Build hotspot rows
        hotspot_rows = ""
        max_hs = hotspots_list[0].hotspot_score if hotspots_list else 1
        for s in hotspots_list:
            pct = s.hotspot_score / max_hs * 100
            risk_cls = "risk-high" if pct > 70 else "risk-med" if pct > 40 else "risk-low"
            hotspot_rows += f"""<tr>
                <td class="file">{esc(s.path)}</td>
                <td class="num">{s.hotspot_score:.0f}</td>
                <td class="num">{s.total_churn}</td>
                <td class="num">{len(s.authors)}</td>
                <td><div class="bar {risk_cls}" style="width:{pct:.0f}%"></div></td>
            </tr>\n"""

        # Build suspect rows
        suspect_rows = ""
        for s in suspects_list:
            flags = " ".join(s["flags"])
            suspect_rows += f"""<tr>
                <td class="sha">{esc(s['sha'])}</td>
                <td>{esc(s['date'])}</td>
                <td class="num">{s['score']:.0f}</td>
                <td class="num">{s['churn']}</td>
                <td class="num">{s['files']}</td>
                <td>{esc(s['subject'])}</td>
                <td class="flags">{esc(flags)}</td>
            </tr>\n"""

        # Build ghost rows
        ghost_rows = ""
        for g in ghosts_list:
            age_cls = "risk-high" if g["age_days"] > 180 else "risk-med" if g["age_days"] > 60 else ""
            ghost_rows += f"""<tr>
                <td class="file">{esc(g['path'])}</td>
                <td>{esc(g['author'])}</td>
                <td>{esc(g['date'])}</td>
                <td class="num {age_cls}">{g['age_days']}d</td>
            </tr>\n"""

        # Build timeline
        timeline_html = ""
        max_tc = max((d["count"] for d in timeline_data), default=1)
        for d in timeline_data:
            pct = d["count"] / max_tc * 100
            churn_opacity = min(d["churn"] / 2000, 1.0)
            subj = esc(d["subjects"][0]) if d["subjects"] else ""
            timeline_html += f"""<div class="tl-row">
                <span class="tl-date">{d['date']}</span>
                <div class="tl-bar-wrap"><div class="tl-bar" style="width:{pct:.0f}%;opacity:{0.4+churn_opacity*0.6:.2f}"></div></div>
                <span class="tl-count">{d['count']}</span>
                <span class="tl-subj">{subj}</span>
            </div>\n"""

        # Build ownership
        ownership_html = ""
        dirs_sorted = sorted(ownership_data.items(), key=lambda x: sum(x[1].values()), reverse=True)
        for dir_name, authors in dirs_sorted[:15]:
            total = sum(authors.values())
            sorted_a = sorted(authors.items(), key=lambda x: x[1], reverse=True)
            bars = ""
            for author, lines in sorted_a[:5]:
                pct = lines / max(total, 1) * 100
                bars += f'<div class="own-row"><span class="own-name">{esc(author)}</span><div class="own-bar-wrap"><div class="own-bar" style="width:{pct:.0f}%"></div></div><span class="own-pct">{pct:.0f}%</span></div>\n'
            ownership_html += f'<div class="own-dir"><div class="own-dir-name">📁 {esc(dir_name)} <span class="own-total">({total} lines)</span></div>{bars}</div>\n'

        # Impact rows
        impact_rows = ""
        for s in impact_list:
            impact_rows += f"""<tr>
                <td class="sha">{esc(s['sha'])}</td>
                <td>{esc(s['date'])}</td>
                <td class="num">{s['score']:.0f}</td>
                <td class="num">{s['churn']}</td>
                <td class="num">{s['files']}</td>
                <td>{esc(s['subject'])}</td>
            </tr>\n"""

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FactoryLM Git Forensics Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e0e0e0;line-height:1.5}}
h1{{color:#00ff88;font-size:1.8rem;letter-spacing:2px}}
h1 span{{color:#76b900;font-weight:300;font-style:italic}}
h2{{color:#00ff88;font-size:1.1rem;margin:0}}
h3{{color:#aaa;font-size:0.9rem;margin:16px 0 8px}}
.header{{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#1a2e1a 100%);padding:24px 32px;border-bottom:2px solid #0f3460}}
.header p{{color:#888;font-size:0.85rem;margin-top:4px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px}}
.stat{{background:#12121a;border:1px solid #2a2a3a;border-radius:8px;padding:12px 20px;min-width:120px}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#00ff88}}
.stat .lbl{{font-size:0.75rem;color:#888;text-transform:uppercase;letter-spacing:1px}}
.section{{margin:24px;background:#12121a;border:1px solid #2a2a3a;border-radius:12px;overflow:hidden}}
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
.file{{font-family:'SF Mono',Monaco,monospace;font-size:0.78rem;color:#ccc;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.sha{{font-family:'SF Mono',Monaco,monospace;color:#0af}}
.num{{text-align:right;font-family:'SF Mono',Monaco,monospace}}
.flags{{font-size:0.8rem}}
.bar{{height:14px;background:linear-gradient(90deg,#00ff88,#76b900);border-radius:3px;min-width:2px}}
.bar.risk-high{{background:linear-gradient(90deg,#ff4444,#ff8800)}}
.bar.risk-med{{background:linear-gradient(90deg,#ffaa00,#ffcc00)}}
.bar.risk-low{{background:linear-gradient(90deg,#00ff88,#76b900)}}
.risk-high{{color:#ff4444}}
.risk-med{{color:#ffaa00}}
.tl-row{{display:flex;align-items:center;gap:8px;padding:2px 0;font-size:0.8rem}}
.tl-date{{min-width:80px;color:#888;font-family:monospace}}
.tl-bar-wrap{{flex:1;height:16px;background:#1a1a2a;border-radius:3px;overflow:hidden}}
.tl-bar{{height:100%;background:#00ff88;border-radius:3px}}
.tl-count{{min-width:30px;text-align:right;color:#76b900;font-weight:600;font-family:monospace}}
.tl-subj{{color:#666;font-size:0.75rem;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.own-dir{{margin-bottom:16px}}
.own-dir-name{{font-weight:600;margin-bottom:6px;font-size:0.85rem}}
.own-total{{color:#888;font-weight:400;font-size:0.75rem}}
.own-row{{display:flex;align-items:center;gap:8px;padding:2px 0;font-size:0.8rem}}
.own-name{{min-width:180px;color:#ccc}}
.own-bar-wrap{{flex:1;max-width:200px;height:12px;background:#1a1a2a;border-radius:3px;overflow:hidden}}
.own-bar{{height:100%;background:#76b900;border-radius:3px}}
.own-pct{{min-width:40px;text-align:right;color:#888;font-family:monospace;font-size:0.75rem}}
.footer{{text-align:center;padding:24px;color:#444;font-size:0.75rem;border-top:1px solid #1a1a2a;margin-top:32px}}
.footer span{{color:#76b900}}
</style>
</head>
<body>
<div class="header">
<h1>Factory·<span>LM</span> Git Forensics</h1>
<p>Generated {now} | {esc(self.repo)}</p>
<div class="stats">
<div class="stat"><div class="val">{summary.get('total_commits',0)}</div><div class="lbl">Commits</div></div>
<div class="stat"><div class="val">{summary.get('authors',0)}</div><div class="lbl">Authors</div></div>
<div class="stat"><div class="val">{summary.get('files_touched',0)}</div><div class="lbl">Files</div></div>
<div class="stat"><div class="val">{summary.get('span_days',0)}d</div><div class="lbl">Span</div></div>
<div class="stat"><div class="val">{summary.get('commits_per_day',0)}</div><div class="lbl">Per Day</div></div>
</div>
</div>

<div class="section open">
<div class="section-head" onclick="this.parentElement.classList.toggle('open')">
<h2>📊 File Churn</h2><span class="toggle">▸</span>
</div>
<div class="section-body">
<table><thead><tr><th>File</th><th>Churn</th><th>Commits</th><th>Authors</th><th>Bar</th></tr></thead>
<tbody>{churn_rows}</tbody></table>
</div></div>

<div class="section open">
<div class="section-head" onclick="this.parentElement.classList.toggle('open')">
<h2>🔥 Hotspots</h2><span class="toggle">▸</span>
</div>
<div class="section-body">
<table><thead><tr><th>File</th><th>Score</th><th>Churn</th><th>Authors</th><th>Risk</th></tr></thead>
<tbody>{hotspot_rows}</tbody></table>
</div></div>

<div class="section">
<div class="section-head" onclick="this.parentElement.classList.toggle('open')">
<h2>🕵️ Suspects</h2><span class="toggle">▸</span>
</div>
<div class="section-body">
<table><thead><tr><th>SHA</th><th>Date</th><th>Score</th><th>Churn</th><th>Files</th><th>Subject</th><th>Flags</th></tr></thead>
<tbody>{suspect_rows}</tbody></table>
</div></div>

<div class="section">
<div class="section-head" onclick="this.parentElement.classList.toggle('open')">
<h2>📈 Commit Timeline</h2><span class="toggle">▸</span>
</div>
<div class="section-body">{timeline_html}</div></div>

<div class="section">
<div class="section-head" onclick="this.parentElement.classList.toggle('open')">
<h2>👻 Ghost Files</h2><span class="toggle">▸</span>
</div>
<div class="section-body">
<table><thead><tr><th>File</th><th>Author</th><th>Added</th><th>Age</th></tr></thead>
<tbody>{ghost_rows}</tbody></table>
</div></div>

<div class="section">
<div class="section-head" onclick="this.parentElement.classList.toggle('open')">
<h2>👥 Code Ownership</h2><span class="toggle">▸</span>
</div>
<div class="section-body">{ownership_html}</div></div>

<div class="section">
<div class="section-head" onclick="this.parentElement.classList.toggle('open')">
<h2>💥 Diff Impact</h2><span class="toggle">▸</span>
</div>
<div class="section-body">
<table><thead><tr><th>SHA</th><th>Date</th><th>Impact</th><th>Churn</th><th>Files</th><th>Subject</th></tr></thead>
<tbody>{impact_rows}</tbody></table>
</div></div>

<div class="footer">Generated by <span>FactoryLM Git Forensics</span> v{VERSION}</div>
</body></html>"""

        out_path = Path(output)
        out_path.write_text(page, encoding="utf-8")
        return str(out_path.resolve())

    # -- full report --------------------------------------------------------

    def print_report(self, output: str = "git-forensics-report.html") -> None:
        summary = self.summary_stats()
        if not summary.get("total_commits"):
            print("No commits found.")
            return

        print(c("\n  ╔══════════════════════════════════════════════════╗", "green", self.color))
        print(c("  ║       Factory·LM  Git Forensics Report          ║", "green", self.color))
        print(c("  ╚══════════════════════════════════════════════════╝\n", "green", self.color))

        print(c("  Summary", "bold", self.color))
        print(f"    Commits:     {c(str(summary['total_commits']), 'green', self.color)}")
        print(f"    Authors:     {summary['authors']}")
        print(f"    Files:       {summary['files_touched']}")
        print(f"    Span:        {summary['first_commit']} → {summary['last_commit']} ({summary['span_days']}d)")
        print(f"    Rate:        {summary['commits_per_day']} commits/day")

        self.print_churn()
        self.print_hotspots()
        self.print_suspects()
        self.print_timeline()

        html_path = self.generate_html(output)
        print(c(f"\n  ✅ Full HTML report: {html_path}", "green", self.color))
        print(c("  Open in browser for interactive sections\n", "gray", self.color))


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="git-forensics",
        description="FactoryLM Git Forensics — zero-dependency retroactive git analysis",
    )
    parser.add_argument("command", nargs="?", default="report",
                        choices=["report", "churn", "hotspots", "suspects", "ghosts",
                                 "ownership", "blame-age", "diff-impact", "timeline",
                                 "bisect-prep"],
                        help="Analysis to run (default: report)")
    parser.add_argument("file", nargs="?", help="File path for blame-age")
    parser.add_argument("--since", default="", help="Only commits after this date")
    parser.add_argument("--until", default="", help="Only commits before this date")
    parser.add_argument("--path", default="", help="Scope to a subdirectory")
    parser.add_argument("--branch", default="", help="Analyze a specific branch")
    parser.add_argument("--top", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--output", default="git-forensics-report.html", help="HTML output path")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--repo", default=".", help="Path to git repo")
    parser.add_argument("--test", default="", help="Test command for bisect-prep")
    parser.add_argument("--good", default="", help="Known-good SHA for bisect-prep")
    parser.add_argument("--version", action="version", version=f"git-forensics {VERSION}")

    args = parser.parse_args()

    gf = GitForensics(
        repo_path=args.repo,
        since=args.since,
        until=args.until,
        path_filter=args.path,
        branch=args.branch,
        top=args.top,
        use_color=not args.no_color,
    )

    cmd = args.command
    if cmd == "report":
        gf.print_report(args.output)
    elif cmd == "churn":
        gf.print_churn()
    elif cmd == "hotspots":
        gf.print_hotspots()
    elif cmd == "suspects":
        gf.print_suspects()
    elif cmd == "ghosts":
        gf.print_ghosts()
    elif cmd == "ownership":
        gf.print_ownership()
    elif cmd == "blame-age":
        filepath = args.file or args.path
        if not filepath:
            parser.error("blame-age requires a file path: git-forensics blame-age <file>")
        gf.print_blame_age(filepath)
    elif cmd == "diff-impact":
        gf.print_diff_impact()
    elif cmd == "timeline":
        gf.print_timeline()
    elif cmd == "bisect-prep":
        if not args.test:
            parser.error("bisect-prep requires --test <command>")
        gf.print_bisect_prep(args.test, args.good)


if __name__ == "__main__":
    main()

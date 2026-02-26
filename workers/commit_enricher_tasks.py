"""
📝 COMMIT ENRICHER WORKER
=========================
Indexes ALL commits across every Mikecranesync repo back to inception,
creates Obsidian commit note files for each day, and enriches every
commit with an AI-generated summary via Groq LLM (Kimi K2).

Operates in reverse chronological order — newest day first.

Data flow:
  gh repo list → discover repos (skip forks)
  gh api repos/{owner}/{repo}/commits --paginate → all commit metadata
  group by date → create/update 10_Commit_Notes/YYYY-MM-DD.md
  gh api repos/{owner}/{repo}/commits/{sha} → get diff per commit
  Groq LLM → generate 2-3 sentence summary
  insert > **What changed:** blockquote into markdown
"""

import os
import sys
import json
import re
import subprocess
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent

logger = logging.getLogger(__name__)

# === Configuration ===
COMMIT_NOTES_DIR = Path(os.getenv(
    'COMMIT_NOTES_DIR',
    '/Users/factorylm/FactoryLM_OS/10_Commit_Notes'
))
STATE_FILE = Path('/opt/master_of_puppets/state/commit_enricher_state.json')
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

GITHUB_OWNER = os.getenv('GITHUB_OWNER', 'Mikecranesync')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'moonshotai/kimi-k2-instruct')
GROQ_RPM_DELAY = 2.5  # seconds between LLM calls (stay under 30 RPM free tier)
MAX_PATCH_CHARS = 4000  # truncate patch for LLM context

# Repos to skip entirely (high-noise automated repos)
SKIP_REPOS = set(os.getenv('ENRICHER_SKIP_REPOS', 'clawdbot').split(','))

# Patterns for trivial commits — get lightweight file-only summary, no LLM
TRIVIAL_PREFIXES = (
    'Merge pull request', 'Merge branch', 'Merge remote',
    'auto:', 'sync:', 'chore: sync', 'chore(deps)',
    'Initial commit',
)
TRIVIAL_AUTHORS = {
    'factorylm-bot', 'github-actions[bot]', 'dependabot[bot]',
    'GitHub', 'hharp',
}

LLM_SYSTEM_PROMPT = (
    "You are a commit summarizer. Given a commit message, files changed, "
    "and patch preview, write a 2-3 sentence summary of what changed and why. "
    "Focus on the functional impact. List the key files modified. "
    "Be concise — this goes into an Obsidian daily note."
)

# Section header: "## RepoName — Push at HH:MM UTC" or "## Push at HH:MM UTC"
SECTION_RE = re.compile(r'^## (?:(.+?) — )?Push at \d{2}:\d{2} UTC')
# Commit hash in table row: | `abc1234` |
HASH_RE = re.compile(r'^\| `([a-f0-9]{7,40})` \|')
ENRICHED_MARKER = '> **What changed:**'


class CommitEnricher(BaseAgent):
    """Indexes all Mikecranesync repos and enriches commit notes."""

    def __init__(self):
        super().__init__("CommitEnricher")
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load state: {e}")
        return {
            "enriched_commits": [],
            "indexed_repos": [],
            "last_run": None,
            "stats": {"total_enriched": 0, "total_skipped": 0, "total_errors": 0},
        }

    def _save_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")

    # ------------------------------------------------------------------
    # Repo Discovery
    # ------------------------------------------------------------------

    def discover_repos(self) -> List[str]:
        """List all non-fork repos under GITHUB_OWNER, minus SKIP_REPOS."""
        try:
            result = subprocess.run(
                ['gh', 'repo', 'list', GITHUB_OWNER, '--limit', '200',
                 '--no-archived', '--json', 'name,isFork',
                 '--jq', '[.[] | select(.isFork == false) | .name] | sort[]'],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                self.logger.error(f"Failed to list repos: {result.stderr}")
                return []
            repos = [
                l.strip() for l in result.stdout.strip().split('\n')
                if l.strip() and l.strip() not in SKIP_REPOS
            ]
            self.logger.info(
                f"Discovered {len(repos)} repos (skipping {SKIP_REPOS})"
            )
            return repos
        except Exception as e:
            self.logger.error(f"Repo discovery failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Trivial Commit Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_trivial(message: str, author: str) -> bool:
        """Check if a commit is trivial (merge, sync, bot) — skip LLM."""
        if author in TRIVIAL_AUTHORS:
            return True
        for prefix in TRIVIAL_PREFIXES:
            if message.startswith(prefix):
                return True
        return False

    def _lightweight_summary(self, owner: str, repo: str,
                             sha: str, message: str) -> Optional[str]:
        """Generate a file-list summary without LLM for trivial commits."""
        try:
            result = subprocess.run(
                ['gh', 'api', f'repos/{owner}/{repo}/commits/{sha}',
                 '--jq', '[.files[].filename] | join(", ")'],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return f"{message}."
            files = result.stdout.strip()
            if not files:
                return f"{message}."
            file_list = files.split(', ')
            if len(file_list) > 5:
                shown = ', '.join(f'`{f}`' for f in file_list[:5])
                return f"{message}. Files: {shown} (+{len(file_list)-5} more)."
            shown = ', '.join(f'`{f}`' for f in file_list)
            return f"{message}. Files: {shown}."
        except Exception:
            return f"{message}."

    # ------------------------------------------------------------------
    # Commit Fetching (full history)
    # ------------------------------------------------------------------

    def fetch_all_repo_commits(self, repo: str) -> List[Dict]:
        """Fetch ALL commits for a repo via gh api --paginate.

        Returns list of dicts:
            {sha, short_sha, message, full_message, author, date_str, time_str, repo}
        Ordered newest-first (GitHub default).
        """
        try:
            result = subprocess.run(
                ['gh', 'api', '--paginate',
                 f'repos/{GITHUB_OWNER}/{repo}/commits?per_page=100'],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                self.logger.error(
                    f"Failed to fetch commits for {repo}: {result.stderr[:200]}"
                )
                return []

            raw = json.loads(result.stdout)
            commits = []
            for c in raw:
                try:
                    date_raw = c['commit']['committer']['date']
                    dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                    first_line = c['commit']['message'].split('\n')[0]
                    commits.append({
                        'sha': c['sha'],
                        'short_sha': c['sha'][:7],
                        'message': first_line,
                        'full_message': c['commit']['message'],
                        'author': c['commit']['author']['name'],
                        'date_str': dt.strftime('%Y-%m-%d'),
                        'time_str': dt.strftime('%H:%M'),
                        'repo': repo,
                    })
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Bad commit in {repo}: {e}")
            self.logger.info(f"  {repo}: {len(commits)} commits")
            return commits
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error for {repo}: {e}")
            return []
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout fetching commits for {repo}")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching commits for {repo}: {e}")
            return []

    # ------------------------------------------------------------------
    # Note File Creation
    # ------------------------------------------------------------------

    def create_note_file(self, date_str: str,
                         commits_by_repo: Dict[str, List[Dict]]) -> Path:
        """Create a new commit note markdown file from API-discovered commits.

        commits_by_repo: {repo_name: [commit_dicts]}  (newest-first per repo)
        """
        filepath = COMMIT_NOTES_DIR / f"{date_str}.md"
        COMMIT_NOTES_DIR.mkdir(parents=True, exist_ok=True)

        # Build tags
        project_tags = [f"project/{r}" for r in sorted(commits_by_repo.keys())]
        tags_str = ', '.join(project_tags + ['type/commit-note'])

        lines = [
            '---',
            f'title: "Commit Notes - {date_str}"',
            f'date: {date_str}',
            f'tags: [{tags_str}]',
            'status: active',
            '---',
            '',
            f'# Commit Notes - {date_str}',
        ]

        for repo in sorted(commits_by_repo.keys()):
            commits = commits_by_repo[repo]
            latest_time = commits[0]['time_str']

            lines.append('')
            lines.append(f'## {repo} — Push at {latest_time} UTC')
            lines.append('')
            lines.append(f'**Commits:** {len(commits)}')
            lines.append(f'**Trigger:** `{commits[0]["short_sha"]}` on `main`')
            lines.append('')
            lines.append('| Hash | Message | Author |')
            lines.append('|------|---------|--------|')

            for c in commits:
                msg = c['message'].replace('|', '\\|')
                lines.append(f'| `{c["short_sha"]}` | {msg} | {c["author"]} |')

        lines.append('')
        filepath.write_text('\n'.join(lines))
        self.logger.info(f"Created {filepath.name} ({sum(len(v) for v in commits_by_repo.values())} commits)")
        return filepath

    # ------------------------------------------------------------------
    # Markdown Parsing (for existing files)
    # ------------------------------------------------------------------

    def parse_note_file(self, filepath: Path) -> List[Dict]:
        """Parse a commit note markdown file into sections with commit data.

        Returns list of dicts with keys:
            header, repo, hashes, start_line, table_end_line, already_enriched
        """
        text = filepath.read_text()
        lines = text.split('\n')
        fallback_repos = self._extract_project_tags(lines)

        sections = []
        i = 0
        while i < len(lines):
            header_match = SECTION_RE.match(lines[i])
            if not header_match:
                i += 1
                continue

            repo = header_match.group(1)
            header = lines[i]
            start_line = i

            hashes = []
            commit_meta = {}  # {short_sha: {message, author}}
            table_end_line = i + 1
            j = i + 1
            while j < len(lines):
                if lines[j].startswith('## '):
                    break
                hash_match = HASH_RE.match(lines[j])
                if hash_match:
                    sha = hash_match.group(1)
                    hashes.append(sha)
                    table_end_line = j + 1
                    # Extract message and author from table row
                    cols = lines[j].split(' | ')
                    if len(cols) >= 3:
                        commit_meta[sha] = {
                            'message': cols[1].strip(),
                            'author': cols[2].strip().rstrip(' |'),
                        }
                j += 1

            if not hashes:
                i = j
                continue

            already_enriched = False
            for k in range(table_end_line, min(table_end_line + 5, j)):
                if ENRICHED_MARKER in lines[k]:
                    already_enriched = True
                    break

            if not repo and fallback_repos:
                non_vault = [r for r in fallback_repos if r != 'FactoryLM_OS']
                repo = non_vault[0] if non_vault else fallback_repos[0]

            sections.append({
                'header': header,
                'repo': repo,
                'hashes': hashes,
                'commit_meta': commit_meta,
                'start_line': start_line,
                'table_end_line': table_end_line,
                'already_enriched': already_enriched,
            })
            i = j

        return sections

    @staticmethod
    def _extract_project_tags(lines: List[str]) -> List[str]:
        in_frontmatter = False
        for line in lines:
            if line.strip() == '---':
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue
            if in_frontmatter and 'tags:' in line:
                return re.findall(r'project/([^\s,\]]+)', line)
        return []

    # ------------------------------------------------------------------
    # GitHub API (individual commit diff)
    # ------------------------------------------------------------------

    def fetch_commit_diff(self, owner: str, repo: str, sha: str) -> Optional[Dict]:
        """Fetch commit details and diff via gh api.

        Returns dict with: message, files_list, patch_preview
        """
        try:
            result = subprocess.run(
                ['gh', 'api', f'repos/{owner}/{repo}/commits/{sha}'],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                self.logger.warning(
                    f"gh api failed for {owner}/{repo}/{sha}: "
                    f"{result.stderr[:200]}"
                )
                return None

            data = json.loads(result.stdout)
            message = data.get('commit', {}).get('message', '')
            files = data.get('files', [])
            files_list = [f.get('filename', '') for f in files]

            patches = []
            total_chars = 0
            for f in files:
                patch = f.get('patch', '')
                if not patch:
                    continue
                entry = f"--- {f['filename']} ---\n{patch}"
                if total_chars + len(entry) > MAX_PATCH_CHARS:
                    remaining = MAX_PATCH_CHARS - total_chars
                    if remaining > 100:
                        patches.append(entry[:remaining] + '\n... (truncated)')
                    break
                patches.append(entry)
                total_chars += len(entry)

            return {
                'message': message,
                'files_list': files_list,
                'patch_preview': '\n'.join(patches) if patches else '(no patch available)',
            }
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout fetching {owner}/{repo}/{sha}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {owner}/{repo}/{sha}: {e}")
            return None

    # ------------------------------------------------------------------
    # LLM Summarization
    # ------------------------------------------------------------------

    def summarize_diff(self, commit_msg: str, files_changed: List[str],
                       patch_preview: str) -> Optional[str]:
        """Call Groq API to generate a 2-3 sentence summary."""
        import requests

        if not GROQ_API_KEY:
            self.logger.error("GROQ_API_KEY not set")
            return None

        user_prompt = (
            f"Commit: {commit_msg}\n"
            f"Files changed: {', '.join(files_changed)}\n"
            f"Patch (truncated):\n{patch_preview}"
        )

        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": LLM_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()

            self.logger.error(
                f"Groq API error {response.status_code}: {response.text[:300]}"
            )
            return None
        except Exception as e:
            self.logger.error(f"Groq API call failed: {e}")
            return None

    # ------------------------------------------------------------------
    # File Enrichment
    # ------------------------------------------------------------------

    @staticmethod
    def _build_blockquote(summaries: Dict[str, str]) -> str:
        if len(summaries) == 1:
            summary = next(iter(summaries.values()))
            return f"\n> **What changed:** {summary}"
        bq_lines = ["\n> **What changed:**"]
        for sha, summary in summaries.items():
            bq_lines.append(f"> - `{sha}`: {summary}")
        return '\n'.join(bq_lines)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def enrich_day(self, date_str: str) -> Dict:
        """Parse one day's note file and enrich unenriched sections."""
        self.log_start('enrich_day', date=date_str)

        filepath = COMMIT_NOTES_DIR / f"{date_str}.md"
        if not filepath.exists():
            self.logger.info(f"No commit note for {date_str}")
            return {"date": date_str, "status": "no_file"}

        sections = self.parse_note_file(filepath)
        enriched = 0
        skipped = 0
        errors = 0

        # Phase 1: collect summaries (LLM calls)
        section_summaries = {}

        for idx, section in enumerate(sections):
            if section['already_enriched']:
                skipped += len(section['hashes'])
                continue

            if not section['repo']:
                self.logger.warning(
                    f"Cannot determine repo for: {section['header']}"
                )
                errors += len(section['hashes'])
                continue

            summaries = {}
            for sha in section['hashes']:
                if sha in self.state['enriched_commits']:
                    skipped += 1
                    continue

                # Check if trivial (merge, bot, sync) — skip LLM
                meta = section.get('commit_meta', {}).get(sha, {})
                msg = meta.get('message', '')
                author = meta.get('author', '')

                if self._is_trivial(msg, author):
                    summary = self._lightweight_summary(
                        GITHUB_OWNER, section['repo'], sha, msg,
                    )
                else:
                    diff_data = self.fetch_commit_diff(
                        GITHUB_OWNER, section['repo'], sha,
                    )
                    if not diff_data:
                        errors += 1
                        continue
                    summary = self.summarize_diff(
                        diff_data['message'],
                        diff_data['files_list'],
                        diff_data['patch_preview'],
                    )
                    if summary:
                        time.sleep(GROQ_RPM_DELAY)

                if not summary:
                    errors += 1
                    continue

                summaries[sha] = summary
                self.state['enriched_commits'].append(sha)
                enriched += 1

            if summaries:
                section_summaries[idx] = summaries

        # Phase 2: insert blockquotes bottom-up
        if section_summaries:
            text = filepath.read_text()
            lines = text.split('\n')
            for idx in sorted(section_summaries.keys(), reverse=True):
                blockquote = self._build_blockquote(section_summaries[idx])
                lines.insert(sections[idx]['table_end_line'], blockquote)
            filepath.write_text('\n'.join(lines))

        self.state['last_run'] = datetime.utcnow().isoformat()
        self.state['stats']['total_enriched'] += enriched
        self.state['stats']['total_skipped'] += skipped
        self.state['stats']['total_errors'] += errors
        self._save_state()

        result = {
            "date": date_str, "enriched": enriched,
            "skipped": skipped, "errors": errors,
        }
        self.log_complete('enrich_day', result)
        return result

    def backfill_from_inception(self) -> Dict:
        """Full historical backfill: discover all repos, create missing
        note files, enrich every commit — reverse chronological order.
        """
        self.log_start('backfill_from_inception')

        # 1. Discover all non-fork repos
        repos = self.discover_repos()
        self.logger.info(f"Scanning {len(repos)} repos under {GITHUB_OWNER}")

        # 2. Fetch all commits across every repo, group by date
        commits_by_date: Dict[str, Dict[str, List[Dict]]] = {}
        # structure: {date_str: {repo_name: [commit, ...]}}

        for repo in repos:
            commits = self.fetch_all_repo_commits(repo)
            for c in commits:
                d = c['date_str']
                commits_by_date.setdefault(d, {})
                commits_by_date[d].setdefault(c['repo'], []).append(c)

        total_commits = sum(
            len(c) for by_repo in commits_by_date.values()
            for c in by_repo.values()
        )
        self.logger.info(
            f"Indexed {total_commits} commits across {len(commits_by_date)} days"
        )
        self.state['indexed_repos'] = repos
        self._save_state()

        # 3. Process dates in reverse chronological order
        dates = sorted(commits_by_date.keys(), reverse=True)
        if dates:
            self.logger.info(f"Date range: {dates[-1]} → {dates[0]} (newest first)")

        results = []
        for date_str in dates:
            filepath = COMMIT_NOTES_DIR / f"{date_str}.md"

            # Create note file if it doesn't exist
            if not filepath.exists():
                self.create_note_file(date_str, commits_by_date[date_str])

            # Enrich all unenriched sections
            try:
                result = self.enrich_day(date_str)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed {date_str}: {e}")
                results.append({"date": date_str, "error": str(e)})

        total = {
            "repos_scanned": len(repos),
            "dates_processed": len(dates),
            "date_range": f"{dates[-1]} → {dates[0]}" if dates else "none",
            "total_commits_indexed": total_commits,
            "total_enriched": sum(r.get('enriched', 0) for r in results),
            "total_skipped": sum(r.get('skipped', 0) for r in results),
            "total_errors": sum(r.get('errors', 0) for r in results),
        }
        self.log_complete('backfill_from_inception', total)
        return total

    def backfill_existing(self) -> Dict:
        """Enrich only existing note files (no repo discovery)."""
        self.log_start('backfill_existing')
        note_files = sorted(COMMIT_NOTES_DIR.glob('*.md'), reverse=True)
        results = []
        for filepath in note_files:
            try:
                result = self.enrich_day(filepath.stem)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed {filepath.stem}: {e}")
                results.append({"date": filepath.stem, "error": str(e)})

        total = {
            "files_processed": len(results),
            "total_enriched": sum(r.get('enriched', 0) for r in results),
            "total_skipped": sum(r.get('skipped', 0) for r in results),
            "total_errors": sum(r.get('errors', 0) for r in results),
        }
        self.log_complete('backfill_existing', total)
        return total

    def enrich_latest(self) -> Dict:
        """Enrich the most recent commit note (today or latest file)."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        today_file = COMMIT_NOTES_DIR / f"{today}.md"
        if today_file.exists():
            return self.enrich_day(today)
        note_files = sorted(COMMIT_NOTES_DIR.glob('*.md'))
        if note_files:
            return self.enrich_day(note_files[-1].stem)
        return {"status": "no_files"}


# === Global Instance ===
enricher = CommitEnricher()


# === Celery Tasks ===

@app.task(name='commit_enricher.enrich_day')
def enrich_day(date_str: str) -> Dict:
    """Enrich a single day's commit notes."""
    logger.info(f"Enriching commit notes for {date_str}")
    return enricher.enrich_day(date_str)


@app.task(name='commit_enricher.backfill')
def backfill() -> Dict:
    """Backfill existing commit notes only."""
    logger.info("Starting backfill of existing commit notes")
    return enricher.backfill_existing()


@app.task(name='commit_enricher.backfill_inception')
def backfill_inception() -> Dict:
    """Full historical backfill from repo inception to present.
    Discovers all repos, creates missing note files, enriches everything.
    """
    logger.info("Starting full historical backfill from inception")
    return enricher.backfill_from_inception()


@app.task(name='commit_enricher.enrich_latest')
def enrich_latest() -> Dict:
    """Enrich the latest commit notes (hook for post-sync)."""
    logger.info("Enriching latest commit notes")
    return enricher.enrich_latest()

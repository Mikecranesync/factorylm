#!/usr/bin/env python3
"""
Standalone enrichment runner — no Celery, no BaseAgent dependency.
Runs the commit enricher directly against local Obsidian vault files.

Usage:
    GROQ_API_KEY=gsk_... python run_enrichment.py [--day 2026-02-25] [--all]
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('enricher')

# === Configuration ===
COMMIT_NOTES_DIR = Path(os.getenv(
    'COMMIT_NOTES_DIR',
    '/Users/factorylm/FactoryLM_OS/10_Commit_Notes'
))
STATE_FILE = Path(os.getenv(
    'ENRICHER_STATE_FILE',
    '/Users/factorylm/factorylm/workers/.enricher_state.json'
))

GITHUB_OWNER = os.getenv('GITHUB_OWNER', 'Mikecranesync')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'moonshotai/kimi-k2-instruct')
GROQ_RPM_DELAY = float(os.getenv('GROQ_RPM_DELAY', '2.5'))
MAX_PATCH_CHARS = 4000

SKIP_REPOS = set(os.getenv('ENRICHER_SKIP_REPOS', 'clawdbot').split(','))

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

# Wikilink mapping: keyword patterns → vault links
# Used to add cross-references in enriched summaries
WIKILINK_MAP = {
    r'\bTony\b|\btony[_-]macaroni\b': '[[04_Agents/Tony_Macaroni/Tony_Macaroni|Tony]]',
    r'\bUltron\b': '[[04_Agents/Ultron/Ultron|Ultron]]',
    r'\bJarvis\b': '[[04_Agents/Jarvis_Local/Jarvis_Local|Jarvis]]',
    r'\bHetzner\b': '[[04_Agents/Hetzner/Hetzner|Hetzner]]',
    r'\bOpenClaw\b|openclaw': '[[03_Projects/OpenClaw/OpenClaw|OpenClaw]]',
    r'\bAntfarm\b|antfarm': '[[03_Projects/Antfarm/Antfarm|Antfarm]]',
    r'\bCMMS\b|cmms|Atlas': '[[03_Projects/Atlas_CMMS/Atlas_CMMS|Atlas CMMS]]',
    r'\bCosmos\b|cosmos': '[[03_Projects/Cosmos/Cosmos|Cosmos]]',
    r'\bdiscord[_-]layer\b|discord.layer': '[[03_Projects/Discord_Adapter/Discord_Adapter|Discord Layer]]',
    r'\bgist[_-]watch\b|gist.poller': '[[03_Projects/Gist_Watch/Gist_Watch|Gist Watch]]',
    r'\bMicro820\b|PLC|Modbus': '[[05_Infrastructure/PLCs/Micro820|Micro820 PLC]]',
}

SECTION_RE = re.compile(r'^## (?:(.+?) — )?Push at \d{2}:\d{2} UTC')
HASH_RE = re.compile(r'^\| `([a-f0-9]{7,40})` \|')
ENRICHED_MARKER = '> **What changed:**'


class LocalEnricher:
    """Standalone enricher — no BaseAgent, no Celery."""

    def __init__(self):
        self.state = self._load_state()
        self.llm_calls = 0
        self.gh_calls = 0

    def _load_state(self) -> Dict:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return {
            "enriched_commits": [],
            "last_run": None,
            "stats": {"total_enriched": 0, "total_skipped": 0, "total_errors": 0},
        }

    def _save_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    @staticmethod
    def _is_trivial(message: str, author: str) -> bool:
        if author in TRIVIAL_AUTHORS:
            return True
        for prefix in TRIVIAL_PREFIXES:
            if message.startswith(prefix):
                return True
        return False

    def _lightweight_summary(self, owner: str, repo: str,
                             sha: str, message: str) -> Optional[str]:
        try:
            self.gh_calls += 1
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

    def fetch_commit_diff(self, owner: str, repo: str, sha: str) -> Optional[Dict]:
        try:
            self.gh_calls += 1
            result = subprocess.run(
                ['gh', 'api', f'repos/{owner}/{repo}/commits/{sha}'],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                logger.warning(f"gh api failed for {owner}/{repo}/{sha}: {result.stderr[:200]}")
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
            logger.error(f"Timeout fetching {owner}/{repo}/{sha}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {owner}/{repo}/{sha}: {e}")
            return None

    def summarize_diff(self, commit_msg: str, files_changed: List[str],
                       patch_preview: str) -> Optional[str]:
        if not GROQ_API_KEY:
            logger.error("GROQ_API_KEY not set")
            return None

        user_prompt = (
            f"Commit: {commit_msg}\n"
            f"Files changed: {', '.join(files_changed)}\n"
            f"Patch (truncated):\n{patch_preview}"
        )

        payload = json.dumps({
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 300,
            "temperature": 0.3,
        })

        try:
            self.llm_calls += 1
            result = subprocess.run(
                ['curl', '-s', '-X', 'POST',
                 'https://api.groq.com/openai/v1/chat/completions',
                 '-H', f'Authorization: Bearer {GROQ_API_KEY}',
                 '-H', 'Content-Type: application/json',
                 '-d', payload],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                logger.error(f"curl failed: {result.stderr[:200]}")
                return None

            data = json.loads(result.stdout)
            if 'error' in data:
                logger.error(f"Groq API error: {data['error']}")
                if 'rate_limit' in str(data['error']).lower():
                    logger.info("Rate limited — waiting 10s...")
                    time.sleep(10)
                return None
            return data['choices'][0]['message']['content'].strip()
        except subprocess.TimeoutExpired:
            logger.error("Groq API call timed out")
            return None
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return None

    def parse_note_file(self, filepath: Path) -> List[Dict]:
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
            commit_meta = {}
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
                if k < len(lines) and ENRICHED_MARKER in lines[k]:
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

    @staticmethod
    def _add_wikilinks(text: str) -> str:
        """Add Obsidian wikilinks to enriched text based on keyword matching."""
        for pattern, link in WIKILINK_MAP.items():
            # Only add wikilink on the first match, avoid double-linking
            if link in text:
                continue
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Replace the first occurrence with the wikilink
                text = text[:match.start()] + link + text[match.end():]
        return text

    @staticmethod
    def _build_blockquote(summaries: Dict[str, str]) -> str:
        if len(summaries) == 1:
            summary = next(iter(summaries.values()))
            summary = LocalEnricher._add_wikilinks(summary)
            return f"\n> **What changed:** {summary}"
        bq_lines = ["\n> **What changed:**"]
        for sha, summary in summaries.items():
            summary = LocalEnricher._add_wikilinks(summary)
            bq_lines.append(f"> - `{sha}`: {summary}")
        return '\n'.join(bq_lines)

    def enrich_day(self, date_str: str) -> Dict:
        filepath = COMMIT_NOTES_DIR / f"{date_str}.md"
        if not filepath.exists():
            logger.info(f"No commit note for {date_str}")
            return {"date": date_str, "status": "no_file"}

        sections = self.parse_note_file(filepath)
        enriched = 0
        skipped = 0
        errors = 0

        section_summaries = {}

        for idx, section in enumerate(sections):
            if section['already_enriched']:
                skipped += len(section['hashes'])
                continue

            if not section['repo']:
                logger.warning(f"Cannot determine repo for: {section['header']}")
                errors += len(section['hashes'])
                continue

            summaries = {}
            for sha in section['hashes']:
                if sha in self.state['enriched_commits']:
                    skipped += 1
                    continue

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

        # Insert blockquotes bottom-up
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

        return {
            "date": date_str, "enriched": enriched,
            "skipped": skipped, "errors": errors,
        }

    def backfill_all(self) -> Dict:
        """Process all note files, newest first."""
        note_files = sorted(COMMIT_NOTES_DIR.glob('*.md'), reverse=True)
        logger.info(f"Found {len(note_files)} note files to process")

        results = []
        for i, filepath in enumerate(note_files):
            date_str = filepath.stem
            logger.info(f"[{i+1}/{len(note_files)}] Processing {date_str}...")
            try:
                result = self.enrich_day(date_str)
                results.append(result)
                if result.get('enriched', 0) > 0:
                    logger.info(
                        f"  → enriched={result['enriched']}, "
                        f"skipped={result['skipped']}, errors={result['errors']}"
                    )
            except Exception as e:
                logger.error(f"Failed {date_str}: {e}")
                results.append({"date": date_str, "error": str(e)})

        total = {
            "files_processed": len(results),
            "total_enriched": sum(r.get('enriched', 0) for r in results),
            "total_skipped": sum(r.get('skipped', 0) for r in results),
            "total_errors": sum(r.get('errors', 0) for r in results),
            "llm_calls": self.llm_calls,
            "gh_api_calls": self.gh_calls,
        }
        logger.info(f"DONE: {json.dumps(total, indent=2)}")
        return total


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Enrich commit notes with AI summaries')
    parser.add_argument('--day', help='Process a single day (YYYY-MM-DD)')
    parser.add_argument('--all', action='store_true', help='Process all note files')
    parser.add_argument('--dry-run', action='store_true', help='Parse only, no LLM calls')
    args = parser.parse_args()

    if not GROQ_API_KEY:
        logger.error("Set GROQ_API_KEY environment variable")
        sys.exit(1)

    enricher = LocalEnricher()

    if args.dry_run:
        note_files = sorted(COMMIT_NOTES_DIR.glob('*.md'), reverse=True)
        total_sections = 0
        total_hashes = 0
        total_already = 0
        total_in_state = 0
        for f in note_files:
            sections = enricher.parse_note_file(f)
            for s in sections:
                total_sections += 1
                for h in s['hashes']:
                    total_hashes += 1
                    if s['already_enriched']:
                        total_already += 1
                    elif h in enricher.state['enriched_commits']:
                        total_in_state += 1
        need = total_hashes - total_already - total_in_state
        logger.info(f"Files: {len(note_files)}")
        logger.info(f"Sections: {total_sections}")
        logger.info(f"Commits: {total_hashes}")
        logger.info(f"Already enriched (in file): {total_already}")
        logger.info(f"Already in state: {total_in_state}")
        logger.info(f"Need enrichment: {need}")
    elif args.day:
        result = enricher.enrich_day(args.day)
        logger.info(f"Result: {json.dumps(result, indent=2)}")
    elif args.all:
        enricher.backfill_all()
    else:
        parser.print_help()

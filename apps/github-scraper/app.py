#!/usr/bin/env python3
"""FactoryLM GitHub Scraper — NiceGUI web app.

Scrapes Mikecranesync GitHub repos for technical documentation (READMEs,
architecture docs, PRDs, whitepapers, CLAUDE.md files).  Ships as a
standalone PyInstaller exe alongside PLC Reader.

DEMO_MODE works fully offline with synthetic data for Cosmos judges.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import sys
import threading
import time
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from nicegui import app, run, ui

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
logger = logging.getLogger("github-scraper")
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── Resolve paths for both dev and frozen (PyInstaller) modes ────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # Frozen exe: _HERE is inside _MEIPASS temp dir
    _EXE_DIR = os.path.dirname(sys.executable)
    _MONOREPO = _EXE_DIR  # not meaningful when frozen
else:
    _EXE_DIR = _HERE
    _MONOREPO = os.path.abspath(os.path.join(_HERE, "..", ".."))

# ── .env (next to exe, next to app.py, next to launcher in _BUILDS, or CWD)
for _env_candidate in [
    os.path.join(_EXE_DIR, ".env"),                           # next to exe (frozen)
    os.path.join(_HERE, ".env"),                              # next to app.py (dev)
    os.path.join(_MONOREPO, "_BUILDS", "github-scraper", ".env"),  # next to launcher (dev)
    ".env",                                                   # CWD
]:
    if os.path.isfile(_env_candidate):
        load_dotenv(_env_candidate, override=False)
        logger.info("Loaded .env from %s", _env_candidate)
        break

# ── Token fallback: gh CLI / keyring (additive — does NOT replace .env) ──
if not os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GITHUB_TOKEN") == "your_token_here":
    # In frozen mode, token_loader is bundled; in dev, it's in _BUILDS/shared
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, os.path.join(_MONOREPO, "_BUILDS", "shared"))
    try:
        from token_loader import load_github_token as _load_token
        _resolved = _load_token()
        if _resolved:
            os.environ["GITHUB_TOKEN"] = _resolved
    except ImportError:
        logger.debug("token_loader not available, skipping gh/keyring fallback")

# ── Content patterns (from workers/github_scrubber_tasks.py) ────────────
CONTENT_PATTERNS: dict[str, list[str]] = {
    "readme": ["README.md", "*/README.md"],
    "claude_instructions": ["CLAUDE.md", ".claude/*.md", ".claude/**/*.md"],
    "architecture": [
        "ARCHITECTURE*.md",
        "architecture*.md",
        "docs/ARCHITECTURE*.md",
        "docs/architecture*.md",
    ],
    "prd": ["PRD*.md", "prd*.md", "docs/PRD*.md", "docs/prd*.md"],
    "whitepaper": [
        "WHITEPAPER*.md",
        "whitepaper*.md",
        "docs/*whitepaper*.md",
        "docs/WHITEPAPER*.md",
    ],
    "technical_docs": ["docs/*.md", "documentation/*.md"],
}

# Flat list for fast matching
_ALL_PATTERNS: list[str] = []
for _pats in CONTENT_PATTERNS.values():
    _ALL_PATTERNS.extend(_pats)

# ── Demo-mode fake repos ────────────────────────────────────────────────
DEMO_REPOS = [
    "factorylm",
    "factorylm-core",
    "factorylm-plc-client",
    "remoteme-jarvis-node",
    "factorylm-landing",
]

_DEMO_TEMPLATES: dict[str, str] = {
    "README.md": (
        "# {repo}\n\n"
        "FactoryLM component — industrial AI for the factory floor.\n\n"
        "## Overview\n\n"
        "This repository contains the {repo} module of the FactoryLM platform.\n\n"
        "## Quick Start\n\n"
        "```bash\npip install -e .\npython -m {module}\n```\n\n"
        "## Architecture\n\n"
        "See `docs/ARCHITECTURE.md` for the full system design.\n"
    ),
    "CLAUDE.md": (
        "# CLAUDE.md — {repo}\n\n"
        "## Project Type\n\n"
        "Python package / microservice\n\n"
        "## Key Files\n\n"
        "- `src/` — main source\n"
        "- `tests/` — pytest suite\n"
        "- `docs/` — documentation\n\n"
        "## Conventions\n\n"
        "- Use `ruff` for linting\n"
        "- Type-annotate public APIs\n"
    ),
    "docs/ARCHITECTURE.md": (
        "# Architecture — {repo}\n\n"
        "## Layers\n\n"
        "| Layer | Purpose |\n"
        "|-------|--------|\n"
        "| L0 | Deterministic code + KB |\n"
        "| L1 | Edge LLM (0.5B) |\n"
        "| L2 | Local GPU (70B) |\n"
        "| L3 | Cloud AI (optional) |\n\n"
        "## Data Flow\n\n"
        "Sensors -> PLC -> Edge -> Cloud -> Dashboard\n"
    ),
    "docs/PRD.md": (
        "# PRD — {repo}\n\n"
        "## Problem\n\n"
        "Factory technicians spend 40% of their time diagnosing problems.\n\n"
        "## Solution\n\n"
        "Natural-language interface to factory equipment via AI.\n\n"
        "## Success Metrics\n\n"
        "- Diagnosis time reduced by 60%\n"
        "- Zero unplanned downtime events\n"
    ),
}


# =========================================================================
#  SyncState — persistent per-repo hash tracking
# =========================================================================

class SyncState:
    """Tracks last-sync timestamps and file hashes in a JSON sidecar."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._data: dict[str, Any] = {"repos": {}}
        self._load()

    def _load(self) -> None:
        if self._path.is_file():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, default=str), encoding="utf-8"
        )

    def get_hash(self, repo: str, filepath: str) -> str | None:
        return self._data.get("repos", {}).get(repo, {}).get("files", {}).get(filepath)

    def set_hash(self, repo: str, filepath: str, h: str) -> None:
        repos = self._data.setdefault("repos", {})
        rdata = repos.setdefault(repo, {"files": {}, "last_sync": None})
        rdata["files"][filepath] = h

    def set_synced(self, repo: str) -> None:
        repos = self._data.setdefault("repos", {})
        rdata = repos.setdefault(repo, {"files": {}, "last_sync": None})
        rdata["last_sync"] = datetime.now(timezone.utc).isoformat()

    def last_sync(self, repo: str) -> str | None:
        return self._data.get("repos", {}).get(repo, {}).get("last_sync")

    def file_count(self, repo: str) -> int:
        return len(self._data.get("repos", {}).get(repo, {}).get("files", {}))


# =========================================================================
#  GitHubAPIClient — httpx REST client (synchronous, for run.io_bound)
# =========================================================================

class GitHubAPIClient:
    """Thin wrapper around GitHub REST API v3 using httpx."""

    BASE = "https://api.github.com"

    def __init__(self, token: str, org: str):
        self._org = org
        self._client = httpx.Client(
            base_url=self.BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    # ── Rate-limit guard ──
    def _check_rate(self, resp: httpx.Response) -> None:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 10:
            reset_ts = int(resp.headers.get("X-RateLimit-Reset", "0"))
            wait = max(reset_ts - int(time.time()), 1)
            logger.warning("Rate limit low (%s remaining), sleeping %ds", remaining, wait)
            time.sleep(min(wait, 60))

    def list_repos(self) -> list[str]:
        """Return list of repo names for the user/org."""
        repos: list[str] = []
        page = 1
        while True:
            # Try /users/ first (personal accounts), fall back to /orgs/
            resp = self._client.get(
                f"/users/{self._org}/repos",
                params={"per_page": 100, "page": page, "type": "owner"},
            )
            if resp.status_code == 404:
                resp = self._client.get(
                    f"/orgs/{self._org}/repos",
                    params={"per_page": 100, "page": page, "type": "all"},
                )
            resp.raise_for_status()
            self._check_rate(resp)
            batch = resp.json()
            if not batch:
                break
            repos.extend(r["name"] for r in batch)
            page += 1
        return sorted(repos)

    def list_tree(self, repo: str) -> list[str]:
        """Return all blob paths via the recursive tree API."""
        resp = self._client.get(
            f"/repos/{self._org}/{repo}/git/trees/HEAD",
            params={"recursive": "1"},
        )
        if resp.status_code == 409:
            return []  # empty repo
        resp.raise_for_status()
        self._check_rate(resp)
        tree = resp.json().get("tree", [])
        return [item["path"] for item in tree if item["type"] == "blob"]

    def fetch_file(self, repo: str, path: str) -> bytes:
        """Fetch raw file content."""
        resp = self._client.get(
            f"/repos/{self._org}/{repo}/contents/{path}",
            headers={"Accept": "application/vnd.github.v3.raw"},
        )
        resp.raise_for_status()
        self._check_rate(resp)
        return resp.content


# =========================================================================
#  DemoScraper — fake data, zero network, real file writes
# =========================================================================

class DemoScraper:
    """Simulates scraping with synthetic data and realistic delays."""

    def __init__(self, cache_path: Path):
        self._cache = cache_path / "demo"

    def list_repos(self) -> list[str]:
        return list(DEMO_REPOS)

    def scrape_repo(
        self,
        repo: str,
        log_fn: Any = None,
        cancel_check: Any = None,
    ) -> dict[str, Any]:
        """Generate fake docs for one repo. Returns stats dict."""
        out_dir = self._cache / repo
        out_dir.mkdir(parents=True, exist_ok=True)

        module = repo.replace("-", "_")
        templates = list(_DEMO_TEMPLATES.items())
        # Pick a random subset (3-12 files, but max is len(templates))
        count = min(random.randint(3, 12), len(templates))
        picked = random.sample(templates, k=count)

        stats = {"repo": repo, "files_found": count, "files_written": 0, "files_skipped": 0}

        for relpath, template in picked:
            if cancel_check and cancel_check():
                break
            content = template.format(repo=repo, module=module)
            dest = out_dir / relpath
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            stats["files_written"] += 1
            if log_fn:
                log_fn(f"  [{repo}] wrote {relpath} ({len(content)} bytes)")
            time.sleep(random.uniform(0.2, 0.6))

        return stats


# =========================================================================
#  ScraperEngine — unified facade
# =========================================================================

class ScraperEngine:
    """Delegates to DemoScraper or GitHubAPIClient based on mode."""

    def __init__(self) -> None:
        self.demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")
        self.token: str = os.getenv("GITHUB_TOKEN", "")
        self.org: str = os.getenv("GITHUB_ORG", "Mikecranesync")
        self.cache_path: Path = Path(os.getenv("CACHE_PATH", "") or ".github_cache")
        self.cache_path.mkdir(parents=True, exist_ok=True)

        self._state = SyncState(self.cache_path / ".sync-state.json")
        self._demo = DemoScraper(self.cache_path)
        self._api: GitHubAPIClient | None = None
        self._cancel = False

    # ── Public helpers ──

    @property
    def token_ok(self) -> bool:
        return bool(self.token) and self.token != "your_token_here"

    @property
    def state(self) -> SyncState:
        return self._state

    def request_cancel(self) -> None:
        self._cancel = True

    def reset_cancel(self) -> None:
        self._cancel = False

    def _cancelled(self) -> bool:
        return self._cancel

    def apply_settings(
        self,
        demo_mode: bool,
        token: str,
        cache_path: str,
        org: str,
    ) -> None:
        self.demo_mode = demo_mode
        self.token = token
        self.org = org
        self.cache_path = Path(cache_path) if cache_path else Path(".github_cache")
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self._state = SyncState(self.cache_path / ".sync-state.json")
        self._demo = DemoScraper(self.cache_path)
        # Reset API client
        if self._api:
            self._api.close()
            self._api = None

    def _ensure_api(self) -> GitHubAPIClient:
        if self._api is None:
            self._api = GitHubAPIClient(self.token, self.org)
        return self._api

    # ── Repo listing ──

    def list_repos(self) -> list[str]:
        if self.demo_mode:
            return self._demo.list_repos()
        if not self.token_ok:
            logger.warning("No valid token — falling back to demo repo list")
            return self._demo.list_repos()
        try:
            return self._ensure_api().list_repos()
        except Exception as exc:
            logger.error("API error listing repos: %s — falling back to demo list", exc)
            return self._demo.list_repos()

    # ── Scrape ──

    def _matches_patterns(self, path: str) -> bool:
        """Check if a file path matches any content pattern."""
        for pattern in _ALL_PATTERNS:
            if fnmatch(path, pattern):
                return True
        return False

    def scrape_repo(
        self,
        repo: str,
        log_fn: Any = None,
    ) -> dict[str, Any]:
        if self.demo_mode:
            return self._demo.scrape_repo(repo, log_fn=log_fn, cancel_check=self._cancelled)

        api = self._ensure_api()
        all_paths = api.list_tree(repo)
        matched = [p for p in all_paths if self._matches_patterns(p)]

        stats = {
            "repo": repo,
            "files_found": len(matched),
            "files_written": 0,
            "files_skipped": 0,
        }

        for fpath in matched:
            if self._cancelled():
                break
            try:
                raw = api.fetch_file(repo, fpath)
                content_hash = hashlib.md5(raw).hexdigest()

                old_hash = self._state.get_hash(repo, fpath)
                if old_hash == content_hash:
                    stats["files_skipped"] += 1
                    if log_fn:
                        log_fn(f"  [{repo}] skip (unchanged) {fpath}")
                    continue

                dest = self.cache_path / repo / fpath
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                self._state.set_hash(repo, fpath, content_hash)
                stats["files_written"] += 1
                if log_fn:
                    log_fn(f"  [{repo}] wrote {fpath} ({len(raw)} bytes)")
            except Exception as exc:
                if log_fn:
                    log_fn(f"  [{repo}] ERROR {fpath}: {exc}")

        self._state.set_synced(repo)
        self._state.save()
        return stats

    def scrape_all(
        self,
        log_fn: Any = None,
        progress_fn: Any = None,
    ) -> list[dict[str, Any]]:
        repos = self.list_repos()
        results: list[dict[str, Any]] = []
        for i, repo in enumerate(repos):
            if self._cancelled():
                if log_fn:
                    log_fn("Cancelled by user.")
                break
            if log_fn:
                log_fn(f"[{i + 1}/{len(repos)}] Scraping {repo}...")
            stats = self.scrape_repo(repo, log_fn=log_fn)
            results.append(stats)
            if progress_fn:
                progress_fn((i + 1) / len(repos))
        return results


# =========================================================================
#  NiceGUI Application
# =========================================================================

engine = ScraperEngine()

# Per-tab log buffers so scrape and backfill don't steal each other's lines
_scrape_logs: list[str] = []
_backfill_logs: list[str] = []
_log_lock = threading.Lock()

# Shared progress float — worker thread writes, UI timer reads
_progress_value: float = 0.0
_scrape_running = False


def _make_log_fn(buf: list[str]):
    """Return a thread-safe append function for a specific log buffer."""
    def _log(msg: str) -> None:
        with _log_lock:
            buf.append(msg)
    return _log


def _drain(buf: list[str], widget: ui.log) -> None:
    """Drain a specific buffer into a specific log widget."""
    with _log_lock:
        batch = list(buf)
        buf.clear()
    for line in batch:
        widget.push(line)


@ui.page("/")
def main_page() -> None:
    global _scrape_running, _progress_value

    # ── Header ───────────────────────────────────────────────────────
    with ui.header().classes("items-center justify-between"):
        ui.label("FactoryLM GitHub Scraper").classes("text-h5 text-weight-bold")
        with ui.row().classes("items-center gap-2"):
            if engine.demo_mode:
                mode_badge = ui.badge("DEMO MODE — no GitHub token found", color="orange").props("outline")
            else:
                mode_badge = ui.badge(
                    f"Connected as {engine.org}" if engine.token_ok else "LIVE (no token)",
                    color="green" if engine.token_ok else "red",
                ).props("outline")
            token_badge = ui.badge(
                "Token OK" if engine.token_ok else "No Token",
                color="green" if engine.token_ok else "red",
            ).props("outline")

    # ── Tabs ─────────────────────────────────────────────────────────
    with ui.tabs().classes("w-full") as tabs:
        scrape_tab = ui.tab("Scrape")
        backfill_tab = ui.tab("Backfill")
        settings_tab = ui.tab("Settings")

    with ui.tab_panels(tabs, value=scrape_tab).classes("w-full"):

        # ============================================================
        #  SCRAPE TAB
        # ============================================================
        with ui.tab_panel(scrape_tab):
            progress = ui.linear_progress(value=0, show_value=False).classes("w-full")
            progress.visible = False

            scrape_log = ui.log(max_lines=500).classes("w-full h-64")

            # Timer: drain log buffer + sync progress bar from shared float
            def _tick() -> None:
                _drain(_scrape_logs, scrape_log)
                if progress.visible:
                    progress.value = _progress_value
            ui.timer(0.5, _tick)

            # ── Repo status table ──
            repo_table = ui.table(
                columns=[
                    {"name": "repo", "label": "Repository", "field": "repo", "align": "left"},
                    {"name": "last_sync", "label": "Last Sync", "field": "last_sync"},
                    {"name": "files", "label": "Cached Files", "field": "files"},
                ],
                rows=[],
            ).classes("w-full mt-4").props("dense flat bordered")

            def _refresh_table() -> None:
                rows = []
                try:
                    repos = engine.list_repos()
                except Exception:
                    repos = DEMO_REPOS
                for r in repos:
                    rows.append({
                        "repo": r,
                        "last_sync": engine.state.last_sync(r) or "never",
                        "files": engine.state.file_count(r),
                    })
                repo_table.rows = rows
                repo_table.update()

            # ── Controls ──
            # Dict options so .value is the repo name string, not an int index
            repo_options = {r: r for r in engine.list_repos()}
            repo_select = ui.select(
                options=repo_options,
                label="Select repo",
            ).classes("w-64")

            with ui.row().classes("gap-2 mt-2"):

                async def _scrape_all() -> None:
                    global _scrape_running, _progress_value
                    if _scrape_running:
                        return
                    _scrape_running = True
                    engine.reset_cancel()
                    _progress_value = 0.0
                    progress.visible = True
                    progress.value = 0
                    scrape_log.clear()

                    log_fn = _make_log_fn(_scrape_logs)
                    log_fn("Starting full scrape...")

                    def _set_progress(v: float) -> None:
                        global _progress_value
                        _progress_value = v

                    def _worker() -> list[dict[str, Any]]:
                        return engine.scrape_all(
                            log_fn=log_fn,
                            progress_fn=_set_progress,
                        )

                    try:
                        results = await run.io_bound(_worker)
                        total_written = sum(r["files_written"] for r in results)
                        total_skipped = sum(r.get("files_skipped", 0) for r in results)
                        log_fn(
                            f"Done. {len(results)} repos, "
                            f"{total_written} files written, {total_skipped} skipped."
                        )
                    except Exception as exc:
                        log_fn(f"ERROR: {exc}")
                    finally:
                        _scrape_running = False
                        _progress_value = 1.0
                        progress.value = 1.0
                        _refresh_table()

                ui.button("Scrape All", on_click=_scrape_all, icon="cloud_download").props(
                    "color=primary"
                )

                def _stop() -> None:
                    engine.request_cancel()
                    _make_log_fn(_scrape_logs)("Cancel requested...")

                ui.button("Stop", on_click=_stop, icon="stop").props("color=negative")

                async def _scrape_one() -> None:
                    global _scrape_running
                    repo = repo_select.value
                    if not repo or _scrape_running:
                        return
                    _scrape_running = True
                    engine.reset_cancel()
                    scrape_log.clear()

                    log_fn = _make_log_fn(_scrape_logs)
                    log_fn(f"Scraping {repo}...")

                    def _worker() -> dict[str, Any]:
                        return engine.scrape_repo(repo, log_fn=log_fn)

                    try:
                        stats = await run.io_bound(_worker)
                        log_fn(
                            f"Done: {stats['files_written']} written, "
                            f"{stats.get('files_skipped', 0)} skipped."
                        )
                    except Exception as exc:
                        log_fn(f"ERROR: {exc}")
                    finally:
                        _scrape_running = False
                        _refresh_table()

                ui.button("Scrape One", on_click=_scrape_one, icon="download").props(
                    "color=secondary"
                )

            _refresh_table()

        # ============================================================
        #  BACKFILL TAB
        # ============================================================
        with ui.tab_panel(backfill_tab):
            bf_progress = ui.linear_progress(value=0, show_value=False).classes("w-full")
            bf_progress.visible = False
            bf_log = ui.log(max_lines=500).classes("w-full h-64")

            def _bf_tick() -> None:
                _drain(_backfill_logs, bf_log)
                if bf_progress.visible:
                    bf_progress.value = _progress_value
            ui.timer(0.5, _bf_tick)

            async def _backfill_all() -> None:
                global _scrape_running, _progress_value
                if _scrape_running:
                    return
                _scrape_running = True
                engine.reset_cancel()
                _progress_value = 0.0
                bf_progress.visible = True
                bf_progress.value = 0
                bf_log.clear()

                log_fn = _make_log_fn(_backfill_logs)
                log_fn("Starting backfill (full re-scrape, ignoring hashes)...")

                def _set_progress(v: float) -> None:
                    global _progress_value
                    _progress_value = v

                def _worker() -> list[dict[str, Any]]:
                    engine.state._data = {"repos": {}}
                    return engine.scrape_all(
                        log_fn=log_fn,
                        progress_fn=_set_progress,
                    )

                try:
                    results = await run.io_bound(_worker)
                    total = sum(r["files_written"] for r in results)
                    log_fn(f"Backfill complete. {total} files written across {len(results)} repos.")
                except Exception as exc:
                    log_fn(f"ERROR: {exc}")
                finally:
                    _scrape_running = False
                    _progress_value = 1.0
                    bf_progress.value = 1.0

            ui.button("Backfill All", on_click=_backfill_all, icon="replay").props(
                "color=primary"
            )

        # ============================================================
        #  SETTINGS TAB
        # ============================================================
        with ui.tab_panel(settings_tab):
            ui.label("Configuration").classes("text-lg font-bold mb-2")

            demo_toggle = ui.switch("Demo Mode", value=engine.demo_mode)
            token_input = ui.input(
                "GitHub Token",
                value=engine.token,
                password=True,
                password_toggle_button=True,
            ).classes("w-full")
            cache_input = ui.input(
                "Cache Path",
                value=str(engine.cache_path),
            ).classes("w-full")
            org_input = ui.input(
                "GitHub Org",
                value=engine.org,
            ).classes("w-full")

            def _save_settings() -> None:
                engine.apply_settings(
                    demo_mode=demo_toggle.value,
                    token=token_input.value,
                    cache_path=cache_input.value,
                    org=org_input.value,
                )
                mode_badge.text = "DEMO" if engine.demo_mode else "LIVE"
                mode_badge._props["color"] = "orange" if engine.demo_mode else "green"
                mode_badge.update()
                token_badge.text = "Token OK" if engine.token_ok else "No Token"
                token_badge._props["color"] = "green" if engine.token_ok else "red"
                token_badge.update()
                repo_select.options = {r: r for r in engine.list_repos()}
                repo_select.update()
                ui.notify("Settings saved!", type="positive")

            ui.button("Save & Apply", on_click=_save_settings, icon="save").props(
                "color=primary"
            ).classes("mt-4")


# ── Entry point ──────────────────────────────────────────────────────────
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="FactoryLM GitHub Scraper",
        port=int(os.environ.get("SCRAPER_PORT", "8081")),
        reload=not getattr(sys, "frozen", False),
        show=True,
    )

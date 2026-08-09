"""Continuous, non-destructive adversarial UX reviews for FactoryLM Hub and MIRA."""

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

from workers.base_worker import BaseAgent, with_celery_tracing
from workers.celery_app import app
from observability.metrics import write_metric


SAFE_ACTIONS = frozenset({"navigate", "expand", "search", "validate"})
SAFE_BUTTON_WORDS = ("back", "close", "next", "previous", "learn", "more", "search", "filter", "show", "hide")
DESTRUCTIVE_WORDS = ("delete", "remove", "send", "submit", "save", "create", "upload", "publish", "run", "start", "stop", "approve")


@dataclass(frozen=True)
class ReviewTarget:
    name: str
    base_url: str


@dataclass
class UxFinding:
    kind: str
    severity: str
    target: str
    url: str
    detail: str
    control: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    occurrences: int = 1
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def fingerprint(self) -> str:
        payload = "|".join((self.kind, self.target, self.url, self.control, self.detail))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HubMiraUxReviewer(BaseAgent):
    """Safely exercises public and test-account UI paths and records UX defects."""

    def __init__(self, report_dir: Optional[Path] = None):
        super().__init__("HubMiraUxReviewer")
        self.report_dir = Path(report_dir or os.getenv("HUB_MIRA_UX_REPORT_DIR", "var/hub-mira-ux-reviews"))
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._findings: Dict[str, UxFinding] = {}

    def is_safe_action(self, action: str) -> bool:
        return action in SAFE_ACTIONS

    def record_finding(self, finding: UxFinding) -> UxFinding:
        fingerprint = finding.fingerprint()
        existing = self._findings.get(fingerprint)
        if existing:
            existing.occurrences += 1
            existing.last_seen = datetime.now(timezone.utc).isoformat()
            return existing
        self._findings[fingerprint] = finding
        return finding

    def record_mira_answer(self, question: str, answer: str, url: str = "") -> None:
        if not self._contains_citation(answer):
            self.record_finding(UxFinding(
                kind="missing_mira_citation",
                severity="high",
                target="mira",
                url=url,
                detail="MIRA answer did not expose a source citation.",
                control="MIRA answer",
                evidence={"question": question, "answer_excerpt": answer[:500]},
            ))

    @staticmethod
    def _contains_citation(answer: str) -> bool:
        lowered = answer.lower()
        return any(marker in lowered for marker in ("source", "citation", "manual §", "manual section", "[1]", "http://", "https://"))

    def _targets_from_environment(self) -> List[ReviewTarget]:
        configured = (("hub", os.getenv("FACTORYLM_HUB_URL", "")), ("mira", os.getenv("FACTORYLM_MIRA_URL", "")))
        return [ReviewTarget(name, url.rstrip("/")) for name, url in configured if url]

    def _same_origin(self, base_url: str, candidate: str) -> bool:
        return urlparse(base_url).netloc == urlparse(candidate).netloc

    def _safe_button(self, label: str) -> bool:
        lowered = label.strip().lower()
        return bool(lowered) and any(word in lowered for word in SAFE_BUTTON_WORDS) and not any(word in lowered for word in DESTRUCTIVE_WORDS)

    def _inspect_target(self, target: ReviewTarget, max_pages: int) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.record_finding(UxFinding("browser_unavailable", "critical", target.name, target.base_url, "Playwright is not installed."))
            return

        queue, visited = [target.base_url], set()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            storage_state = os.getenv("HUB_MIRA_UX_STORAGE_STATE_PATH", "")
            context_args: Dict[str, Any] = {"viewport": {"width": 1440, "height": 900}}
            if storage_state:
                context_args["storage_state"] = storage_state
            context = browser.new_context(**context_args)
            page = context.new_page()
            page_errors: List[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            try:
                while queue and len(visited) < max_pages:
                    url = queue.pop(0)
                    if url in visited:
                        continue
                    visited.add(url)
                    started = time.monotonic()
                    try:
                        response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    except Exception as exc:
                        self.record_finding(UxFinding("navigation_failure", "critical", target.name, url, str(exc)))
                        continue
                    latency_ms = round((time.monotonic() - started) * 1000, 2)
                    if response is None or response.status >= 400:
                        status = "no response" if response is None else f"HTTP {response.status}"
                        self.record_finding(UxFinding("navigation_failure", "high", target.name, url, status))
                        continue
                    if latency_ms > 5_000:
                        self.record_finding(UxFinding("slow_page", "medium", target.name, url, f"Page load took {latency_ms}ms."))
                    for error in page_errors:
                        self.record_finding(UxFinding("browser_error", "high", target.name, url, error))
                    page_errors.clear()
                    for link in page.locator("a[href]").evaluate_all("els => els.map(e => e.href)"):
                        if self._same_origin(target.base_url, link) and link not in visited:
                            queue.append(link)
                    self._inspect_controls(page, target, url)
            finally:
                context.close()
                browser.close()

    def _inspect_controls(self, page: Any, target: ReviewTarget, url: str) -> None:
        for button in page.locator("button, [role='button']").all():
            label = (button.get_attribute("aria-label") or button.inner_text() or "").strip()
            if not label:
                self.record_finding(UxFinding("inaccessible_control", "medium", target.name, url, "Interactive control has no accessible name."))
                continue
            if self._safe_button(label):
                try:
                    button.click(timeout=3_000)
                except Exception as exc:
                    self.record_finding(UxFinding("broken_interaction", "high", target.name, url, str(exc), label))
            elif any(word in label.lower() for word in DESTRUCTIVE_WORDS):
                self.record_finding(UxFinding("guarded_action_not_exercised", "info", target.name, url, "Skipped potentially state-changing control.", label))

    def run_review(self, targets: Optional[Iterable[ReviewTarget]] = None, max_pages: int = 250) -> Dict[str, Any]:
        review_targets = list(targets or self._targets_from_environment())
        if not review_targets:
            self.record_finding(UxFinding("configuration_missing", "critical", "reviewer", "", "Set FACTORYLM_HUB_URL and FACTORYLM_MIRA_URL before running reviews."))
        for target in review_targets:
            self._inspect_target(target, max_pages=max_pages)
        return self._write_report()

    def summary(self) -> Dict[str, Any]:
        findings = [asdict(item) for item in self._findings.values()]
        return {"unique_findings": len(findings), "findings": findings}

    def _write_report(self) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        summary = self.summary()
        run_file = self.report_dir / f"review-{timestamp}.json"
        run_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        markdown = ["# Hub and MIRA UX Review", "", f"Unique findings: {summary['unique_findings']}", ""]
        for finding in summary["findings"]:
            markdown.append(f"- **{finding['severity']} · {finding['kind']}** — {finding['detail']}")
        report_file = self.report_dir / "latest.md"
        report_file.write_text("\n".join(markdown) + "\n", encoding="utf-8")
        write_metric("hub_mira_ux_review", tags={"status": "complete"}, fields={"unique_findings": summary["unique_findings"]})
        return {**summary, "report_file": str(report_file), "run_file": str(run_file)}


reviewer = HubMiraUxReviewer()


@app.task(bind=True, name="hub_mira_ux.review_once")
@with_celery_tracing("hub_mira_ux.review_once")
def review_once(self, max_pages: int = 250) -> Dict[str, Any]:
    return reviewer.run_review(max_pages=max_pages)


@app.task(bind=True, name="hub_mira_ux.continuous")
@with_celery_tracing("hub_mira_ux.continuous")
def continuous(self, max_pages: int = 250) -> Dict[str, Any]:
    """One bounded review cycle; Celery Beat supplies continuous execution."""
    return reviewer.run_review(max_pages=max_pages)


@app.task(bind=True, name="hub_mira_ux.report")
def report(self) -> Dict[str, Any]:
    return reviewer.summary()


@app.task(bind=True, name="hub_mira_ux.health")
def health(self) -> Dict[str, Any]:
    return {"status": "ok", "agent": reviewer.name, "report_dir": str(reviewer.report_dir)}

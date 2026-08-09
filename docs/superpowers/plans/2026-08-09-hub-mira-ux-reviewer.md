# Hub and MIRA UX Reviewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separately named Celery worker that continuously performs safe, adversarial browser reviews of FactoryLM Hub and MIRA and emits actionable UX findings.

**Architecture:** The worker will use Playwright's synchronous Python API behind a small browser adapter. It will discover same-origin paths and controls, execute only an explicit safe-action allowlist, classify and deduplicate evidence-backed findings, and write run reports. Celery Beat triggers bounded cycles every fifteen minutes.

**Tech Stack:** Python, Celery, Playwright, requests-compatible observability helper, pytest/unittest.

## Global Constraints

- Preserve `workers/synthetic_user_tasks.py` unchanged.
- Never hard-code production URLs, credentials, or filesystem paths.
- Default task behavior must be non-destructive and report denied or unavailable paths rather than bypassing them.
- Keep the browser closed at the end of every run.

---

### Task 1: Create the review data model and safe-action policy

**Files:**
- Create: `workers/hub_mira_ux_reviewer_tasks.py`
- Test: `tests/test_hub_mira_ux_reviewer.py`

**Interfaces:**
- Produces: `UxFinding`, `ReviewTarget`, and `HubMiraUxReviewer`.

- [ ] **Step 1: Write the failing test**

```python
def test_reviewer_rejects_unsafe_actions(tmp_path):
    reviewer = HubMiraUxReviewer(report_dir=tmp_path)
    assert reviewer.is_safe_action("navigate") is True
    assert reviewer.is_safe_action("submit") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_reviewer_rejects_unsafe_actions -q`

- [ ] **Step 3: Write minimal implementation**

```python
SAFE_ACTIONS = frozenset({"navigate", "expand", "search", "validate"})

def is_safe_action(self, action: str) -> bool:
    return action in SAFE_ACTIONS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_reviewer_rejects_unsafe_actions -q`

### Task 2: Add browser path discovery and evidence capture

**Files:**
- Modify: `workers/hub_mira_ux_reviewer_tasks.py`
- Test: `tests/test_hub_mira_ux_reviewer.py`

**Interfaces:**
- Consumes: `ReviewTarget` and `UxFinding`.
- Produces: `run_review(targets)` returning a serializable summary.

- [ ] **Step 1: Write the failing test**

```python
def test_review_reports_a_broken_safe_control(tmp_path, fake_browser):
    reviewer = HubMiraUxReviewer(report_dir=tmp_path, browser=fake_browser)
    result = reviewer.run_review([ReviewTarget("hub", "https://hub.test")])
    assert result["findings"][0]["kind"] == "broken_interaction"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_review_reports_a_broken_safe_control -q`

- [ ] **Step 3: Write minimal implementation**

```python
for control in browser.safe_controls(url):
    outcome = browser.try_action(control)
    if not outcome.ok:
        findings.append(self.make_finding("broken_interaction", outcome))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_review_reports_a_broken_safe_control -q`

### Task 3: Add MIRA-specific answer review, reporting, and deduplication

**Files:**
- Modify: `workers/hub_mira_ux_reviewer_tasks.py`
- Test: `tests/test_hub_mira_ux_reviewer.py`

**Interfaces:**
- Produces: durable JSONL evidence and a current Markdown summary.

- [ ] **Step 1: Write the failing test**

```python
def test_missing_mira_citation_is_deduplicated(tmp_path):
    reviewer = HubMiraUxReviewer(report_dir=tmp_path)
    reviewer.record_mira_answer("same query", "answer without evidence")
    reviewer.record_mira_answer("same query", "answer without evidence")
    assert reviewer.summary()["unique_findings"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_missing_mira_citation_is_deduplicated -q`

- [ ] **Step 3: Write minimal implementation**

```python
fingerprint = sha256(f"{kind}|{target}|{control}|{detail}".encode()).hexdigest()
existing[fingerprint]["occurrences"] += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_missing_mira_citation_is_deduplicated -q`

### Task 4: Register the dedicated Celery tasks and bounded schedule

**Files:**
- Modify: `workers/celery_app.py`
- Test: `tests/test_hub_mira_ux_reviewer.py`

**Interfaces:**
- Produces: `hub_mira_ux.review_once`, `hub_mira_ux.continuous`, `hub_mira_ux.report`, and `hub_mira_ux.health`.

- [ ] **Step 1: Write the failing test**

```python
def test_celery_registers_the_hub_mira_reviewer():
    from workers.celery_app import app
    assert "workers.hub_mira_ux_reviewer_tasks" in app.conf.include
    assert app.conf.beat_schedule["hub-mira-ux-review-every-15-min"]["task"] == "hub_mira_ux.continuous"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_celery_registers_the_hub_mira_reviewer -q`

- [ ] **Step 3: Write minimal implementation**

```python
include.append("workers.hub_mira_ux_reviewer_tasks")
beat_schedule["hub-mira-ux-review-every-15-min"] = {"task": "hub_mira_ux.continuous", "schedule": 900.0}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py::test_celery_registers_the_hub_mira_reviewer -q`

### Task 5: Run focused verification

**Files:**
- Test: `tests/test_hub_mira_ux_reviewer.py`

- [ ] **Step 1: Run the reviewer tests**

Run: `python -m pytest tests/test_hub_mira_ux_reviewer.py -q`

- [ ] **Step 2: Verify task discovery without a live browser target**

Run: `python -c "from workers.celery_app import app; assert 'hub_mira_ux.health' in app.tasks"`

- [ ] **Step 3: Commit**

Run: `git add workers/hub_mira_ux_reviewer_tasks.py workers/celery_app.py tests/test_hub_mira_ux_reviewer.py docs/superpowers/plans/2026-08-09-hub-mira-ux-reviewer.md && git commit -m "feat: add Hub and MIRA UX reviewer"`

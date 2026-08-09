# Hub and MIRA UX Reviewer Design

## Goal

Create a dedicated Celery worker that continuously reviews FactoryLM Hub and MIRA as adversarial synthetic users. It must discover reachable, human-facing interaction paths, exercise safe interactions, and preserve actionable evidence of UX defects without changing plant or customer data.

## Scope

The existing `workers/synthetic_user_tasks.py` remains unchanged. A new `workers/hub_mira_ux_reviewer_tasks.py` reuses its Celery/BaseAgent conventions but owns its own configuration, data model, tasks, and Celery Beat entry.

## Reviewer behavior

1. Start from configured Hub and MIRA URLs.
2. Crawl same-origin, reachable links and inspect buttons, form controls, dialogs, and navigation controls.
3. Run persona-based, non-destructive journeys: anonymous prospect, new technician, maintenance manager, and skeptical buyer.
4. For every interaction, capture page URL, accessible control name, action, outcome, console errors, failed requests, screenshots, and elapsed time.
5. Classify findings into broken interaction, inaccessible control, misleading/dead-end journey, failure to explain MIRA's evidence/citations, unsafe action exposed without guardrails, and performance failure.
6. Fingerprint findings so repeat runs update occurrence counts instead of generating duplicate noise.
7. Persist JSONL evidence and a current Markdown report under a configurable report directory; emit summary metrics through the existing observability helper.

## Safety constraints

- Default configuration targets a dedicated test account.
- Interactions are allowlisted: navigation, expanding UI, search, non-persistent form validation, and MIRA questions.
- The worker must not submit destructive forms, send messages, create work orders, upload files, change settings, or invoke production machine actions.
- The reviewer records missing authentication and blocked paths as findings rather than attempting to bypass access controls.
- Configuration supplies base URLs and credentials; no production URLs or secrets are hard-coded.

## Architecture

`HubMiraUxReviewer` extends `BaseAgent`. It uses an injectable browser-session adapter so unit tests can supply deterministic DOM/action results, while deployment uses Playwright when installed. The runner emits a normalized `UxFinding` record for each defect and writes run summaries through a small report store. Celery exposes one-shot, continuous, report-status, and health tasks. Beat schedules a bounded cycle; Celery, not an infinite process, provides 24/7 repetition and recovery.

## Validation

Unit tests cover allowlisted-action enforcement, finding severity and deduplication, handling of failed navigation and MIRA responses without citations, report rendering, task registration, and Beat schedule registration. A local browser smoke test is optional and must use explicitly supplied test URLs.

## Explicit non-goals

The first version does not attempt credential stuffing, authorization bypass, destructive testing, CAPTCHA handling, cross-origin crawling, or autonomous fixes. It reports defects for human review.

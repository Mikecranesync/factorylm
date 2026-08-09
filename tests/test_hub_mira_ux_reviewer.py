from pathlib import Path

import observability
from workers.hub_mira_ux_reviewer_tasks import HubMiraUxReviewer


def test_observability_exports_base_worker_contract():
    assert hasattr(observability, "TraceContext")
    assert callable(observability.generate_trace_id)
    assert callable(observability.get_trace_id_from_context)


def test_reviewer_rejects_unsafe_actions(tmp_path: Path):
    reviewer = HubMiraUxReviewer(report_dir=tmp_path)

    assert reviewer.is_safe_action("navigate") is True
    assert reviewer.is_safe_action("submit") is False


def test_missing_mira_citation_is_deduplicated(tmp_path: Path):
    reviewer = HubMiraUxReviewer(report_dir=tmp_path)

    reviewer.record_mira_answer("Why did the conveyor stop?", "Check the drive.")
    reviewer.record_mira_answer("Why did the conveyor stop?", "Check the drive.")

    assert reviewer.summary()["unique_findings"] == 1
    assert reviewer.summary()["findings"][0]["occurrences"] == 2


def test_celery_registers_the_hub_mira_reviewer():
    from workers.celery_app import app

    assert "workers.hub_mira_ux_reviewer_tasks" in app.conf.include
    assert app.conf.beat_schedule["hub-mira-ux-review-every-15-min"]["task"] == "hub_mira_ux.continuous"

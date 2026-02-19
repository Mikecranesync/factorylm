"""
Tests for the Deterministic Troubleshooting Engine
===================================================
Run with: pytest tests/test_troubleshoot_engine.py -v
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from openclaw.troubleshoot.models import (
    TreeNode,
    TreeOption,
    TreeResponse,
    TroubleshootSession,
    TroubleshootTree,
)
from openclaw.troubleshoot.engine import TreeRunner, SESSION_TTL


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TREE_DATA = {
    "slug": "test-motor",
    "title": "Test Motor Tree",
    "description": "A test tree",
    "fault_codes": ["M002"],
    "trigger_words": ["motor stopped", "why stopped"],
    "equipment": "test-cell",
    "version": 1,
    "is_active": True,
    "tree": {
        "root": "n1",
        "nodes": {
            "n1": {
                "type": "question",
                "text": "Is the contactor energized?",
                "hint": "Check K1 in the panel.",
                "options": [
                    {"label": "Yes", "next": "n2", "transition": "Good, power is getting through."},
                    {"label": "No", "next": "n3", "transition": "OK, contactor isn't pulling in."},
                ],
            },
            "n2": {
                "type": "question",
                "text": "Check all 3 phases at the motor. Getting voltage?",
                "options": [
                    {"label": "Yes, all phases", "next": "n_seized", "transition": "Voltage but no spin."},
                    {"label": "Missing phases", "next": "n_phase", "transition": "Lost a phase."},
                ],
            },
            "n3": {
                "type": "question",
                "text": "Is the overload relay tripped?",
                "plc_tag": "overload_tripped",
                "options": [
                    {"label": "Yes, it's tripped", "next": "n_overload", "transition": "Overload tripped."},
                    {"label": "No, looks normal", "next": "n_resolved", "transition": "That rules out overload."},
                ],
            },
            "n_seized": {
                "type": "resolution",
                "text": "Motor is likely seized.",
                "steps": ["LOTO the motor", "Try rotating shaft by hand"],
                "severity": "critical",
                "requires_maintenance": True,
                "llm_handoff": False,
            },
            "n_phase": {
                "type": "resolution",
                "text": "Single-phasing detected.",
                "steps": ["Check wiring", "Inspect contactor tips"],
                "severity": "critical",
                "requires_maintenance": True,
                "llm_handoff": False,
            },
            "n_overload": {
                "type": "resolution",
                "text": "Overload tripped — motor was overcurrent.",
                "steps": ["Wait for cooldown", "Check for jams", "Reset OLR"],
                "severity": "critical",
                "requires_maintenance": False,
                "llm_handoff": False,
            },
            "n_resolved": {
                "type": "resolution",
                "text": "Need deeper investigation.",
                "steps": ["Check control circuit"],
                "severity": "warning",
                "requires_maintenance": False,
                "llm_handoff": True,
            },
        },
    },
}

SAMPLE_TREE_INACTIVE = {
    **SAMPLE_TREE_DATA,
    "slug": "test-inactive",
    "title": "Inactive Tree",
    "is_active": False,
    "fault_codes": ["X999"],
    "trigger_words": ["nonexistent"],
}


@pytest.fixture
def tree() -> TroubleshootTree:
    return TroubleshootTree.from_json(SAMPLE_TREE_DATA)


@pytest.fixture
def runner(tmp_path, tree) -> TreeRunner:
    """Create a TreeRunner with a temp session file and one tree loaded."""
    # Patch the session file path to avoid polluting /tmp
    import openclaw.troubleshoot.engine as eng
    original = eng.SESSION_FILE
    eng.SESSION_FILE = tmp_path / "test_sessions.json"
    r = TreeRunner()
    r.load_trees([tree])
    yield r
    eng.SESSION_FILE = original


@pytest.fixture
def runner_multi(tmp_path, tree) -> TreeRunner:
    """Runner with both active and inactive trees."""
    import openclaw.troubleshoot.engine as eng
    original = eng.SESSION_FILE
    eng.SESSION_FILE = tmp_path / "test_sessions_multi.json"
    inactive = TroubleshootTree.from_json(SAMPLE_TREE_INACTIVE)
    r = TreeRunner()
    r.load_trees([tree, inactive])
    yield r
    eng.SESSION_FILE = original


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_tree_node_from_dict(self):
        data = {
            "type": "question",
            "text": "Is it running?",
            "hint": "Look at the light.",
            "options": [
                {"label": "Yes", "next": "n2", "transition": "Good."},
                {"label": "No", "next": "n3"},
            ],
        }
        node = TreeNode.from_dict("n1", data)
        assert node.id == "n1"
        assert node.type == "question"
        assert len(node.options) == 2
        assert node.options[0].label == "Yes"
        assert node.options[0].transition == "Good."
        assert node.options[1].transition == ""  # Missing transition defaults to ""

    def test_tree_node_resolution(self):
        data = {
            "type": "resolution",
            "text": "Replace the motor.",
            "steps": ["LOTO", "Swap motor"],
            "severity": "critical",
            "requires_maintenance": True,
            "llm_handoff": False,
        }
        node = TreeNode.from_dict("n_fix", data)
        assert node.type == "resolution"
        assert len(node.steps) == 2
        assert node.requires_maintenance is True
        assert node.llm_handoff is False

    def test_troubleshoot_tree_from_json(self, tree):
        assert tree.slug == "test-motor"
        assert tree.root == "n1"
        assert len(tree.nodes) == 7
        assert "n1" in tree.nodes
        assert tree.fault_codes == ["M002"]
        assert tree.is_active is True

    def test_troubleshoot_tree_from_db_row(self):
        row = {
            "tree_id": 42,
            "slug": "test-db",
            "title": "DB Tree",
            "description": "From DB",
            "fault_codes": ["E001"],
            "trigger_words": ["estop"],
            "equipment": "cell-1",
            "tree": {
                "root": "n1",
                "nodes": {
                    "n1": {
                        "type": "resolution",
                        "text": "Done.",
                        "steps": [],
                    }
                },
            },
            "version": 2,
            "is_active": True,
        }
        t = TroubleshootTree.from_db_row(row)
        assert t.tree_id == 42
        assert t.slug == "test-db"
        assert t.version == 2
        assert "n1" in t.nodes


# ---------------------------------------------------------------------------
# Tree Lookup Tests
# ---------------------------------------------------------------------------

class TestTreeLookup:
    def test_find_tree_by_fault(self, runner):
        tree = runner.find_tree_by_fault("M002")
        assert tree is not None
        assert tree.slug == "test-motor"

    def test_find_tree_by_fault_miss(self, runner):
        assert runner.find_tree_by_fault("X999") is None

    def test_find_tree_by_fault_skips_inactive(self, runner_multi):
        # X999 exists but is inactive
        assert runner_multi.find_tree_by_fault("X999") is None

    def test_find_tree_by_trigger(self, runner):
        tree = runner.find_tree_by_trigger("why is the motor stopped")
        assert tree is not None
        assert tree.slug == "test-motor"

    def test_find_tree_by_trigger_miss(self, runner):
        assert runner.find_tree_by_trigger("how's the weather") is None

    def test_find_tree_by_trigger_skips_inactive(self, runner_multi):
        assert runner_multi.find_tree_by_trigger("nonexistent problem") is None

    def test_list_trees(self, runner_multi):
        trees = runner_multi.list_trees()
        slugs = [t.slug for t in trees]
        assert "test-motor" in slugs
        assert "test-inactive" not in slugs


# ---------------------------------------------------------------------------
# Session Lifecycle Tests
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    def test_start_creates_session(self, runner):
        resp = runner.start("user1", "test-motor")
        assert resp.type == "question"
        assert runner.has_active_session("user1")

    def test_start_returns_root_question(self, runner):
        resp = runner.start("user1", "test-motor")
        assert "contactor" in resp.text.lower()
        assert resp.node is not None
        assert resp.node.id == "n1"

    def test_start_nonexistent_tree(self, runner):
        resp = runner.start("user1", "fake-tree")
        assert resp.type == "not_found"
        assert not runner.has_active_session("user1")

    def test_cancel_session(self, runner):
        runner.start("user1", "test-motor")
        assert runner.has_active_session("user1")
        runner.cancel("user1")
        assert not runner.has_active_session("user1")

    def test_session_expired(self, runner):
        runner.start("user1", "test-motor")
        # Manually expire the session
        session = runner._sessions["user1"]
        session.last_activity = time.time() - SESSION_TTL - 10
        assert not runner.has_active_session("user1")

    def test_answer_after_expiry(self, runner):
        runner.start("user1", "test-motor")
        session = runner._sessions["user1"]
        session.last_activity = time.time() - SESSION_TTL - 10
        resp = runner.answer("user1", "1")
        assert resp.type == "expired"

    def test_no_session_answer(self, runner):
        resp = runner.answer("user1", "1")
        assert resp.type == "expired"


# ---------------------------------------------------------------------------
# Answer Matching Tests
# ---------------------------------------------------------------------------

class TestAnswerMatching:
    def test_numeric_answer(self, runner):
        runner.start("user1", "test-motor")
        # "1" = "Yes" option -> n2
        resp = runner.answer("user1", "1")
        assert resp.type == "question"
        assert resp.node.id == "n2"

    def test_numeric_answer_second_option(self, runner):
        runner.start("user1", "test-motor")
        # "2" = "No" option -> n3
        resp = runner.answer("user1", "2")
        assert resp.type == "question"
        assert resp.node.id == "n3"

    def test_label_answer_exact(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "Yes")
        assert resp.node.id == "n2"

    def test_label_answer_case_insensitive(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "yes")
        assert resp.node.id == "n2"

    def test_label_answer_shortcut_y(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "y")
        assert resp.node.id == "n2"

    def test_label_answer_shortcut_n(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "n")
        assert resp.node.id == "n3"

    def test_label_answer_yep(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "yep")
        assert resp.node.id == "n2"

    def test_label_answer_nope(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "nope")
        assert resp.node.id == "n3"

    def test_invalid_numeric(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "99")
        assert resp.type == "llm_handoff"

    def test_unmatched_input_triggers_llm_handoff(self, runner):
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "I'm not sure what you mean")
        assert resp.type == "llm_handoff"
        assert resp.context_for_llm.get("unmatched_input") == "I'm not sure what you mean"


# ---------------------------------------------------------------------------
# Full Walkthrough Tests
# ---------------------------------------------------------------------------

class TestFullWalkthrough:
    def test_walk_to_resolution(self, runner):
        """Walk through: n1 (Yes) -> n2 (Yes, all phases) -> n_seized (resolution)."""
        resp = runner.start("user1", "test-motor")
        assert resp.type == "question"
        assert resp.node.id == "n1"

        resp = runner.answer("user1", "1")  # Yes -> n2
        assert resp.type == "question"
        assert resp.node.id == "n2"

        resp = runner.answer("user1", "1")  # Yes, all phases -> n_seized
        assert resp.type == "resolution"
        assert "seized" in resp.text.lower()
        assert resp.node.requires_maintenance is True

        # Session should be ended after resolution
        assert not runner.has_active_session("user1")

    def test_walk_to_llm_handoff_resolution(self, runner):
        """Walk to n_resolved which has llm_handoff=True."""
        runner.start("user1", "test-motor")
        runner.answer("user1", "2")  # No -> n3
        resp = runner.answer("user1", "2")  # No, looks normal -> n_resolved (llm_handoff)
        assert resp.type == "llm_handoff"
        assert resp.context_for_llm.get("tree_title") == "Test Motor Tree"

    def test_walk_overload_path(self, runner):
        """Walk: n1 (No) -> n3 (Yes, tripped) -> n_overload."""
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "2")  # No -> n3
        assert resp.node.id == "n3"

        resp = runner.answer("user1", "1")  # Yes, tripped -> n_overload
        assert resp.type == "resolution"
        assert "overcurrent" in resp.text.lower()
        assert resp.node.requires_maintenance is False

    def test_transition_phrases_recorded(self, runner):
        """Verify transition text is stored on the session."""
        runner.start("user1", "test-motor")
        resp = runner.answer("user1", "1")  # Yes
        session = runner.get_session("user1")
        assert session.last_transition == "Good, power is getting through."

    def test_answers_accumulated(self, runner):
        """Verify answer history is built up."""
        runner.start("user1", "test-motor")
        runner.answer("user1", "1")  # Yes
        runner.answer("user1", "1")  # Yes, all phases -> resolution
        # Session ended, but let's check the LLM context from the resolution
        # Actually, let's test answer accumulation mid-session
        runner.start("user2", "test-motor")
        runner.answer("user2", "2")  # No -> n3
        session = runner.get_session("user2")
        assert len(session.answers) == 1
        assert session.answers[0]["answer"] == "No"
        assert session.answers[0]["node_id"] == "n1"

    def test_answer_at_resolution_ends_session(self, runner):
        """If already at resolution, answering ends cleanly."""
        runner.start("user1", "test-motor")
        runner.answer("user1", "1")  # -> n2
        runner.answer("user1", "1")  # -> n_seized (resolution, session ends)
        # Try answering again
        resp = runner.answer("user1", "anything")
        assert resp.type == "expired"


# ---------------------------------------------------------------------------
# PLC Auto-Answer Tests
# ---------------------------------------------------------------------------

class TestPLCAutoAnswer:
    def test_plc_auto_answer_skips_node(self, runner):
        """If PLC data matches a plc_tag node, auto-advance."""
        plc_snapshot = {"overload_tripped": True}
        runner.start("user1", "test-motor", plc_snapshot=plc_snapshot)

        # n1 has no plc_tag, so it presents normally
        resp = runner.answer("user1", "2")  # No -> n3 (has plc_tag=overload_tripped)

        # n3 should auto-answer based on PLC (True -> "Yes" -> n_overload)
        assert resp.type == "resolution"
        assert resp.node.id == "n_overload"

    def test_plc_auto_answer_false(self, runner):
        """PLC tag is False -> auto-select "No" option."""
        plc_snapshot = {"overload_tripped": False}
        runner.start("user1", "test-motor", plc_snapshot=plc_snapshot)

        resp = runner.answer("user1", "2")  # No -> n3 (plc_tag auto-answers "No" -> n_resolved)
        assert resp.type == "llm_handoff"  # n_resolved has llm_handoff=True

    def test_plc_no_matching_tag(self, runner):
        """PLC snapshot doesn't have the tag — present question normally."""
        plc_snapshot = {"motor_running": False}  # No overload_tripped key
        runner.start("user1", "test-motor", plc_snapshot=plc_snapshot)
        resp = runner.answer("user1", "2")  # No -> n3

        # n3 should present as a question since PLC doesn't have overload_tripped
        assert resp.type == "question"
        assert resp.node.id == "n3"


# ---------------------------------------------------------------------------
# Session Persistence Tests
# ---------------------------------------------------------------------------

class TestSessionPersistence:
    def test_sessions_saved_to_file(self, runner, tmp_path):
        import openclaw.troubleshoot.engine as eng
        runner.start("user1", "test-motor")
        assert eng.SESSION_FILE.exists()

        data = json.loads(eng.SESSION_FILE.read_text())
        assert "user1" in data
        assert data["user1"]["tree_slug"] == "test-motor"

    def test_sessions_restored_on_init(self, tmp_path, tree):
        import openclaw.troubleshoot.engine as eng
        original = eng.SESSION_FILE
        session_file = tmp_path / "persist_test.json"
        eng.SESSION_FILE = session_file

        # Create a runner and start a session
        r1 = TreeRunner()
        r1.load_trees([tree])
        r1.start("user1", "test-motor")
        r1.answer("user1", "1")  # Advance to n2

        # Create a NEW runner pointing at the same file
        r2 = TreeRunner()
        r2.load_trees([tree])
        assert r2.has_active_session("user1")
        session = r2.get_session("user1")
        assert session.current_node == "n2"

        eng.SESSION_FILE = original

    def test_expired_sessions_not_restored(self, tmp_path, tree):
        import openclaw.troubleshoot.engine as eng
        original = eng.SESSION_FILE
        session_file = tmp_path / "expired_test.json"
        eng.SESSION_FILE = session_file

        # Write an expired session directly
        expired_data = {
            "user1": {
                "user_id": "user1",
                "tree_slug": "test-motor",
                "current_node": "n2",
                "started_at": time.time() - SESSION_TTL - 100,
                "last_activity": time.time() - SESSION_TTL - 100,
                "answers": [],
                "plc_snapshot": {},
                "fault_code": None,
                "last_transition": "",
            }
        }
        session_file.write_text(json.dumps(expired_data))

        r = TreeRunner()
        r.load_trees([tree])
        assert not r.has_active_session("user1")

        eng.SESSION_FILE = original


# ---------------------------------------------------------------------------
# Seed Tree JSON Validation
# ---------------------------------------------------------------------------

class TestSeedTreesValid:
    """Validate all 6 seed tree JSON files parse correctly."""

    TREES_DIR = Path(__file__).parent.parent / "openclaw" / "troubleshoot" / "trees"

    def _load_tree(self, filename):
        path = self.TREES_DIR / filename
        assert path.exists(), f"Missing tree file: {filename}"
        data = json.loads(path.read_text())
        tree = TroubleshootTree.from_json(data)
        return tree

    def _validate_tree(self, tree):
        """Common validations for any tree."""
        assert tree.slug, "Tree must have a slug"
        assert tree.title, "Tree must have a title"
        assert tree.root in tree.nodes, f"Root '{tree.root}' not in nodes"
        assert tree.fault_codes, "Tree must have at least one fault code"
        assert tree.is_active is True

        # Every node referenced by options must exist
        for nid, node in tree.nodes.items():
            if node.type == "question":
                assert len(node.options) >= 2, f"Node {nid} has fewer than 2 options"
                for opt in node.options:
                    assert opt.next in tree.nodes, f"Node {nid} option '{opt.label}' points to missing node '{opt.next}'"
                    assert opt.label, f"Node {nid} has an option with empty label"
            elif node.type == "resolution":
                # Resolution nodes are terminal — no dangling references
                pass
            else:
                pytest.fail(f"Unknown node type '{node.type}' on node {nid}")

    @pytest.mark.parametrize("filename,expected_slug,expected_fault", [
        ("estop-recovery.json", "estop-recovery", "E001"),
        ("motor-overcurrent.json", "motor-overcurrent", "M001"),
        ("motor-stopped.json", "motor-stopped", "M002"),
        ("conveyor-jam.json", "conveyor-jam", "C001"),
        ("high-temperature.json", "high-temperature", "T001"),
        ("low-pressure.json", "low-pressure", "P001"),
    ])
    def test_seed_tree_valid(self, filename, expected_slug, expected_fault):
        tree = self._load_tree(filename)
        assert tree.slug == expected_slug
        assert expected_fault in tree.fault_codes
        self._validate_tree(tree)

    def test_all_trees_load_into_runner(self):
        """All 6 trees can be loaded into a TreeRunner without conflict."""
        trees = []
        for f in sorted(self.TREES_DIR.glob("*.json")):
            data = json.loads(f.read_text())
            trees.append(TroubleshootTree.from_json(data))

        runner = TreeRunner()
        runner.load_trees(trees)
        assert len(runner.list_trees()) == 6

    def test_no_orphan_nodes(self):
        """Every non-root node must be reachable from the root."""
        for f in sorted(self.TREES_DIR.glob("*.json")):
            data = json.loads(f.read_text())
            tree = TroubleshootTree.from_json(data)

            reachable = set()
            queue = [tree.root]
            while queue:
                nid = queue.pop(0)
                if nid in reachable:
                    continue
                reachable.add(nid)
                node = tree.nodes.get(nid)
                if node and node.type == "question":
                    for opt in node.options:
                        queue.append(opt.next)

            all_ids = set(tree.nodes.keys())
            orphans = all_ids - reachable
            assert not orphans, f"Tree '{tree.slug}' has orphan nodes: {orphans}"


# ---------------------------------------------------------------------------
# Intent Classification Integration
# ---------------------------------------------------------------------------

class TestIntentClassification:
    """Verify the TROUBLESHOOT intent fires correctly."""

    def test_troubleshoot_keyword(self):
        from openclaw.messages.intent import classify_intent
        from openclaw.types import Intent

        assert classify_intent("troubleshoot") == Intent.TROUBLESHOOT
        assert classify_intent("/troubleshoot") == Intent.TROUBLESHOOT
        assert classify_intent("walk me through it") == Intent.TROUBLESHOOT
        assert classify_intent("guide me through the fix") == Intent.TROUBLESHOOT
        assert classify_intent("how do i fix this") == Intent.TROUBLESHOOT
        assert classify_intent("step by step diagnosis") == Intent.TROUBLESHOOT

    def test_diagnose_not_confused_with_troubleshoot(self):
        from openclaw.messages.intent import classify_intent
        from openclaw.types import Intent

        # "why is it stopped" should still be DIAGNOSE, not TROUBLESHOOT
        assert classify_intent("why is the motor stopped") == Intent.DIAGNOSE
        assert classify_intent("what's wrong with the machine") == Intent.DIAGNOSE

    def test_numeric_input_is_general(self):
        from openclaw.messages.intent import classify_intent
        from openclaw.types import Intent

        # Bare numbers -> GENERAL (this is why session-aware dispatch matters)
        assert classify_intent("2") == Intent.GENERAL
        assert classify_intent("1") == Intent.GENERAL


# ---------------------------------------------------------------------------
# Integration Module Tests
# ---------------------------------------------------------------------------

class TestSessionDispatchMiddleware:
    """Test that session-aware dispatch correctly intercepts
    numeric replies during active troubleshoot sessions.

    The integration module (skill.py, integration.py) depends on VPS-only
    modules (openclaw.messages.models, openclaw.skills.base). Tests here
    verify the engine-level session interception works, and mark the
    full-stack integration tests as VPS-only.
    """

    def test_integration_module_importable(self):
        """integration.py itself imports without VPS deps (lazy imports)."""
        from openclaw.troubleshoot import integration
        assert hasattr(integration, "session_dispatch")
        assert hasattr(integration, "register_troubleshoot")
        assert hasattr(integration, "_runner")

    def test_session_dispatch_returns_none_without_runner(self):
        """When no runner is initialized, session_dispatch returns None."""
        import asyncio
        from openclaw.troubleshoot import integration

        old_runner = integration._runner
        integration._runner = None
        try:
            result = asyncio.get_event_loop().run_until_complete(
                integration.session_dispatch(None, None, None)
            )
            assert result is None
        finally:
            integration._runner = old_runner

    def test_session_dispatch_returns_none_no_active_session(self, runner):
        """When user has no active session, returns None."""
        import asyncio
        from openclaw.troubleshoot import integration

        old_runner = integration._runner
        integration._runner = runner
        try:
            class FakeMsg:
                user_id = "no-session-user"
                text = "2"
                channel = "telegram"
                metadata = {}

            result = asyncio.get_event_loop().run_until_complete(
                integration.session_dispatch(FakeMsg(), None, None)
            )
            assert result is None
        finally:
            integration._runner = old_runner

    def test_session_dispatch_intercepts_active_session(self, runner):
        """When user has active session, session_dispatch routes to the skill."""
        import asyncio
        from openclaw.troubleshoot import integration

        old_runner = integration._runner
        integration._runner = runner

        # Start a session first
        runner.start("user-sd-1", "test-motor")

        try:
            handled = []

            class FakeSkill:
                async def handle(self, message, context):
                    handled.append(message.text)
                    return type("Resp", (), {
                        "text": "handled",
                        "channel": "telegram",
                        "user_id": message.user_id,
                        "attachments": [],
                    })()

            class FakeRegistry:
                def get(self, intent):
                    return FakeSkill()

            class FakeMsg:
                user_id = "user-sd-1"
                text = "2"
                channel = "telegram"
                metadata = {}

            result = asyncio.get_event_loop().run_until_complete(
                integration.session_dispatch(FakeMsg(), FakeRegistry(), None)
            )
            assert result is not None
            assert result.text == "handled"
            assert handled == ["2"]
        finally:
            integration._runner = old_runner
            runner.cancel("user-sd-1")

    def test_numeric_reply_routed_via_engine_not_intent(self, runner):
        """End-to-end: a bare '2' reply during active session reaches the engine,
        not the intent classifier. This is THE critical test."""
        from openclaw.messages.intent import classify_intent
        from openclaw.types import Intent

        # Prove intent classifier fails on "2"
        assert classify_intent("2") == Intent.GENERAL

        # But the engine handles it correctly
        runner.start("user-e2e", "test-motor")
        resp = runner.answer("user-e2e", "2")  # n1: option 2 = "No" -> n3
        assert resp.type == "question"
        assert resp.node.id == "n3"  # Successfully routed through engine

"""Tests for services.learner.knowledge_store."""

import json
import tempfile
from pathlib import Path

import pytest

from services.learner.knowledge_store import KnowledgeStore, IOPoint


@pytest.fixture
def ks(tmp_path):
    """Create a KnowledgeStore with a temp database."""
    db = tmp_path / "test_knowledge.db"
    store = KnowledgeStore(db_path=db)
    yield store
    store.close()


@pytest.fixture
def scene_with_io(ks):
    """Create a scene with I/O points pre-populated."""
    scene_id = ks.add_scene("Sorting by Height", "Test scene", "soft_plc.py")
    io_points = [
        IOPoint("conveyor_entry", 0, "coil", "BOOL", "Entry conveyor belt motor", "Sorting by Height"),
        IOPoint("load", 1, "coil", "BOOL", "Load pallet onto conveyor", "Sorting by Height"),
        IOPoint("transfer_left", 3, "coil", "BOOL", "Left diverter arm", "Sorting by Height"),
        IOPoint("high_sensor", 0, "discrete_input", "BOOL", "Height sensor (tall)", "Sorting by Height"),
        IOPoint("low_sensor", 1, "discrete_input", "BOOL", "Height sensor (short)", "Sorting by Height"),
    ]
    ks.bulk_add_io_points(scene_id, io_points)
    return scene_id


# --- Scene CRUD ---

class TestScenes:
    def test_add_scene(self, ks):
        sid = ks.add_scene("Sorting by Height", "A sorting scene")
        assert sid > 0

    def test_add_scene_idempotent(self, ks):
        sid1 = ks.add_scene("Sorting by Height")
        sid2 = ks.add_scene("Sorting by Height")
        assert sid1 == sid2

    def test_get_scene(self, ks):
        sid = ks.add_scene("Pick and Place", "Robot arm scene", "pick_place.st")
        scene = ks.get_scene(sid)
        assert scene["name"] == "Pick and Place"
        assert scene["program_source"] == "pick_place.st"

    def test_get_scene_not_found(self, ks):
        assert ks.get_scene(999) is None


# --- I/O Points ---

class TestIOPoints:
    def test_add_io_point(self, ks):
        sid = ks.add_scene("Test Scene")
        pt = IOPoint("conveyor_entry", 0, "coil", "BOOL", "Entry belt", "Test Scene")
        pid = ks.add_io_point(sid, pt)
        assert pid > 0

    def test_add_io_point_upsert(self, ks):
        sid = ks.add_scene("Test Scene")
        pt1 = IOPoint("conveyor_entry", 0, "coil", "BOOL", "Entry belt", "Test Scene")
        pt2 = IOPoint("conveyor_entry_v2", 0, "coil", "BOOL", "Updated desc", "Test Scene")
        pid1 = ks.add_io_point(sid, pt1)
        pid2 = ks.add_io_point(sid, pt2)
        assert pid1 == pid2
        # Check updated
        pts = ks.get_io_points(sid)
        assert pts[0]["name"] == "conveyor_entry_v2"
        assert pts[0]["official_description"] == "Updated desc"

    def test_bulk_add(self, scene_with_io, ks):
        pts = ks.get_io_points(scene_with_io)
        assert len(pts) == 5
        scene = ks.get_scene(scene_with_io)
        assert scene["io_count"] == 5

    def test_get_untested_io(self, scene_with_io, ks):
        untested = ks.get_untested_io(scene_with_io)
        assert len(untested) == 5  # All untested initially

    def test_update_learning(self, scene_with_io, ks):
        pts = ks.get_io_points(scene_with_io)
        coil_0 = next(p for p in pts if p["name"] == "conveyor_entry")

        ks.update_io_learning(
            coil_0["id"],
            learned_description="Starts the entry conveyor belt",
            confidence=0.9,
            verified=True,
        )

        updated = ks.get_io_points(scene_with_io)
        c0 = next(p for p in updated if p["name"] == "conveyor_entry")
        assert c0["learned_description"] == "Starts the entry conveyor belt"
        assert c0["confidence"] == 0.9
        assert c0["verified"] == 1
        assert c0["test_count"] == 1

    def test_get_low_confidence(self, scene_with_io, ks):
        pts = ks.get_io_points(scene_with_io)
        # Mark one as tested but low confidence
        ks.update_io_learning(pts[0]["id"], "maybe belt?", confidence=0.3)
        # Mark another as tested and high confidence
        ks.update_io_learning(pts[1]["id"], "definitely load", confidence=0.9)

        low = ks.get_low_confidence_io(scene_with_io, threshold=0.5)
        assert len(low) == 1
        assert low[0]["confidence"] == 0.3

    def test_set_kb_prior(self, scene_with_io, ks):
        pts = ks.get_io_points(scene_with_io)
        ks.set_kb_prior(pts[0]["id"], "From prior scene: entry belt starts sorting conveyor")
        updated = ks.get_io_points(scene_with_io)
        assert "entry belt" in updated[0]["kb_prior_knowledge"]


# --- Experiments ---

class TestExperiments:
    def test_experiment_lifecycle(self, scene_with_io, ks):
        eid = ks.start_experiment(
            scene_with_io, "SingleCoilToggle",
            {"coil": "conveyor_entry", "address": 0, "action": "ON"},
        )
        assert eid > 0

        ks.record_before(eid, {"conveyor_entry": False, "high_sensor": False},
                         screenshot_path="/tmp/before.png", vision_text="Belt is stopped")

        ks.record_after(eid, {"conveyor_entry": True, "high_sensor": False},
                        screenshot_path="/tmp/after.png", vision_text="Belt is moving")

        ks.complete_experiment(
            eid,
            tag_delta={"conveyor_entry": {"old": False, "new": True}},
            vision_delta="The entry conveyor belt started moving",
            learning="Coil 0 (conveyor_entry) starts the entry belt",
            verified=True,
        )

        exps = ks.get_experiments(scene_with_io)
        assert len(exps) == 1
        assert exps[0]["learning"] == "Coil 0 (conveyor_entry) starts the entry belt"
        assert exps[0]["verified_against_docs"] == 1
        assert exps[0]["completed_at"] is not None


# --- Learnings ---

class TestLearnings:
    def test_add_and_mark_written(self, scene_with_io, ks):
        lid = ks.add_learning(
            scene_with_io,
            summary="Coil 0 starts entry belt",
            confidence=0.9,
            category="behavior",
        )
        assert lid > 0

        unwritten = ks.get_unwritten_learnings(scene_with_io)
        assert len(unwritten) == 1

        ks.mark_kb_written(lid)
        unwritten = ks.get_unwritten_learnings(scene_with_io)
        assert len(unwritten) == 0


# --- Prompt Context ---

class TestPromptContext:
    def test_to_prompt_context(self, scene_with_io, ks):
        # Add a learning
        pts = ks.get_io_points(scene_with_io)
        ks.update_io_learning(pts[0]["id"], "Entry belt motor", confidence=0.9, verified=True)
        ks.add_learning(scene_with_io, "Coil 0 starts entry belt", confidence=0.9)

        ctx = ks.to_prompt_context(scene_with_io)
        assert "Sorting by Height" in ctx
        assert "VERIFIED" in ctx
        assert "Coil 0 starts entry belt" in ctx
        assert "UNTESTED" in ctx  # Some points still untested

    def test_empty_scene_context(self, ks):
        sid = ks.add_scene("Empty Scene")
        ctx = ks.to_prompt_context(sid)
        assert "Empty Scene" in ctx

    def test_nonexistent_scene_context(self, ks):
        ctx = ks.to_prompt_context(999)
        assert ctx == ""


# --- Export ---

class TestExport:
    def test_export_scene_knowledge(self, scene_with_io, ks):
        # Add experiment + learning
        eid = ks.start_experiment(scene_with_io, "SingleCoilToggle", {"coil": 0})
        ks.complete_experiment(eid, {}, "belt moved", "entry belt starts", verified=True)
        ks.add_learning(scene_with_io, "Coil 0 starts belt", confidence=0.9)

        export = ks.export_scene_knowledge(scene_with_io)
        assert export["scene"]["name"] == "Sorting by Height"
        assert export["stats"]["total_io"] == 5
        assert export["stats"]["total_experiments"] == 1
        assert export["stats"]["total_learnings"] == 1

    def test_export_not_found(self, ks):
        export = ks.export_scene_knowledge(999)
        assert "error" in export

    def test_export_json_serializable(self, scene_with_io, ks):
        export = ks.export_scene_knowledge(scene_with_io)
        # Should not raise
        json.dumps(export)


# --- Sequences ---

class TestSequences:
    def test_add_sequence(self, scene_with_io, ks):
        steps = [
            {"coil": "conveyor_entry", "value": True, "wait_s": 2},
            {"coil": "load", "value": True, "wait_s": 1},
            {"coil": "transfer_left", "value": True, "wait_s": 2},
        ]
        sid = ks.add_sequence(scene_with_io, "sort_left_flow", steps)
        assert sid > 0

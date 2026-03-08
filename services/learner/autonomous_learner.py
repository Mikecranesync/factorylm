"""Autonomous Scene Learner — main orchestrator.

Drives the 4-phase experiment loop across a queue of Factory I/O scenes:
  Phase 0: Setup + prior knowledge (KB search, scene description)
  Phase 1: Systematic verification (every coil + register)
  Phase 2: Interaction discovery (combinations, sequences)
  Phase 3: Curiosity-driven (AI-planned experiments)
  Phase 4: Consolidation + KB export

Usage:
    python -m services.learner.autonomous_learner
    python -m services.learner.autonomous_learner --scenes "Sorting by Height,Pick and Place"
    python -m services.learner.autonomous_learner --max-experiments 50 --max-hours 1
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

# Ensure monorepo root importable
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from services.learner.knowledge_store import KnowledgeStore, IOPoint
from services.learner import scene_manager as sm
from services.learner import scene_observer as observer
from services.learner import experiment_engine as engine

logger = logging.getLogger("factorylm.learner")

CONFIG_PATH = REPO_ROOT / "config" / "learner.yaml"


def load_config() -> dict:
    """Load learner config from config/learner.yaml."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


# ---------------------------------------------------------------------------
# Status reporting (to Matrix API dashboard)
# ---------------------------------------------------------------------------

_status: dict = {}


def update_status(**kwargs):
    """Update the global learner status dict."""
    _status.update(kwargs)
    _status["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def report_status_to_matrix(matrix_url: str):
    """POST learner status to Matrix API for dashboard display."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(f"{matrix_url}/api/learner/status", json=_status)
    except Exception:
        pass  # Dashboard reporting is best-effort


# ---------------------------------------------------------------------------
# Phase 0: Setup + Prior Knowledge
# ---------------------------------------------------------------------------

async def phase_0_setup(scene_name: str, ks: KnowledgeStore) -> tuple[int, list[dict]]:
    """Setup scene, parse I/O, pre-populate knowledge store, search KB."""
    update_status(phase="setup", scene=scene_name, status="initializing")

    # Add scene to store
    scene_id = ks.add_scene(scene_name, program_source="factoryio.yaml")

    # Parse I/O map from config
    io_points = sm.parse_program_io(scene_name)
    if not io_points:
        logger.warning("No I/O points found for '%s' — trying web API discovery", scene_name)
        io_points = sm.parse_program_io(scene_name, config=None)

    if not io_points:
        logger.error("No I/O points discovered for '%s'", scene_name)
        return scene_id, []

    # Pre-populate knowledge store with official descriptions
    ks.bulk_add_io_points(scene_id, io_points)
    logger.info("Pre-populated %d I/O points for '%s'", len(io_points), scene_name)

    # Search KB for prior knowledge about each tag
    io_records = ks.get_io_points(scene_id)
    kb_found = 0
    for pt in io_records:
        query = f"Factory I/O {scene_name} {pt['name']} {pt.get('official_description', '')}"
        prior = await observer.search_kb(query)
        if prior:
            ks.set_kb_prior(pt["id"], "\n".join(prior))
            kb_found += 1
    logger.info("KB prior knowledge found for %d/%d I/O points", kb_found, len(io_records))

    # Reset scene to clean state
    try:
        sm.reset_to_clean(scene_name)
    except Exception as exc:
        logger.warning("Scene reset failed (may not be running): %s", exc)

    # Capture and describe initial scene state
    screenshot = sm.capture_screenshot("scene_idle")
    if screenshot:
        result = await observer.describe_scene(screenshot)
        description = result.get("content", "")
        if description:
            ks.add_learning(scene_id, f"Scene description: {description[:200]}",
                            confidence=0.8, category="behavior")

    update_status(phase="setup", status="complete",
                  io_count=len(io_records), kb_prior=kb_found)

    return scene_id, io_records


# ---------------------------------------------------------------------------
# Phase 1: Systematic Verification
# ---------------------------------------------------------------------------

async def phase_1_verification(
    scene_id: int,
    io_records: list[dict],
    ks: KnowledgeStore,
    max_experiments: int = 100,
    settle_time: float = 2.0,
) -> list[engine.ExperimentResult]:
    """Toggle every writable coil and sweep every register."""
    update_status(phase="verification", status="running")
    results = []

    io_map = {r["name"]: (r["address"], r["io_type"]) for r in io_records}

    # Test all coils
    coils = [r for r in io_records if r["io_type"] == "coil"]
    for i, coil in enumerate(coils):
        if len(results) >= max_experiments:
            break
        update_status(experiment=f"coil {i+1}/{len(coils)}: {coil['name']}",
                      experiments_done=len(results))

        result = await engine.run_single_coil_toggle(
            scene_id, coil, io_map, ks, settle_time,
        )
        if result:
            results.append(result)

    # Test all registers
    registers = [r for r in io_records if r["io_type"] == "register"]
    for i, reg in enumerate(registers):
        if len(results) >= max_experiments:
            break
        update_status(experiment=f"register {i+1}/{len(registers)}: {reg['name']}",
                      experiments_done=len(results))

        result = await engine.run_register_sweep(
            scene_id, reg, io_map, ks, settle_time=settle_time,
        )
        if result:
            results.append(result)

    update_status(phase="verification", status="complete",
                  experiments_done=len(results))
    return results


# ---------------------------------------------------------------------------
# Phase 2: Interaction Discovery
# ---------------------------------------------------------------------------

async def phase_2_interactions(
    scene_id: int,
    io_records: list[dict],
    ks: KnowledgeStore,
    phase_1_results: list[engine.ExperimentResult],
    max_experiments: int = 30,
) -> list[engine.ExperimentResult]:
    """Find interactions — test "no effect" coils in combinations."""
    update_status(phase="interactions", status="running")
    results = []

    io_map = {r["name"]: (r["address"], r["io_type"]) for r in io_records}

    # Identify coils that had no tag delta in Phase 1
    no_effect_coils = []
    for r in phase_1_results:
        if r.experiment_type == "SingleCoilToggle" and not r.tag_delta:
            matching = [io for io in io_records if io["name"] == r.coil_name]
            if matching:
                no_effect_coils.append(matching[0])

    if not no_effect_coils:
        logger.info("No 'no-effect' coils found — skipping Phase 2 combinations")
        return results

    logger.info("Testing %d 'no-effect' coils in pairwise combinations", len(no_effect_coils))

    # Pairwise combinations (limit to avoid explosion)
    pairs = list(itertools.combinations(no_effect_coils, 2))[:max_experiments]
    for i, pair in enumerate(pairs):
        if len(results) >= max_experiments:
            break
        update_status(experiment=f"combo {i+1}/{len(pairs)}",
                      experiments_done=len(results))

        result = await engine.run_multi_coil(
            scene_id, list(pair), io_map, ks,
        )
        if result:
            results.append(result)

    update_status(phase="interactions", status="complete",
                  experiments_done=len(results))
    return results


# ---------------------------------------------------------------------------
# Phase 3: Curiosity-Driven
# ---------------------------------------------------------------------------

async def phase_3_curiosity(
    scene_id: int,
    io_records: list[dict],
    ks: KnowledgeStore,
    max_experiments: int = 20,
) -> list[engine.ExperimentResult]:
    """AI-planned experiments based on what we know so far."""
    update_status(phase="curiosity", status="running")
    results = []

    io_map = {r["name"]: (r["address"], r["io_type"]) for r in io_records}

    # Re-test low-confidence I/O points
    low_conf = ks.get_low_confidence_io(scene_id, threshold=0.5)
    for pt in low_conf[:max_experiments]:
        if len(results) >= max_experiments:
            break
        update_status(experiment=f"retest {pt['name']} (conf={pt['confidence']:.1f})",
                      experiments_done=len(results))

        if pt["io_type"] == "coil":
            result = await engine.run_single_coil_toggle(scene_id, pt, io_map, ks)
        elif pt["io_type"] == "register":
            result = await engine.run_register_sweep(scene_id, pt, io_map, ks)
        else:
            continue

        if result:
            results.append(result)

    update_status(phase="curiosity", status="complete",
                  experiments_done=len(results))
    return results


# ---------------------------------------------------------------------------
# Phase 4: Consolidation + KB Export
# ---------------------------------------------------------------------------

def export_training_jsonl(export: dict, scene_name: str, output_path: Path) -> int:
    """Convert scene knowledge to JSONL training records for Qwen fine-tuning.

    Returns number of records written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    instruction = (
        "You are a Factory I/O automation expert. Given the PLC I/O state, "
        "explain what happens when the specified output is activated."
    )

    for exp in export.get("experiments", []):
        learning = exp.get("learning", "")
        if not learning:
            continue

        before = exp.get("before_tags", {})
        tag_delta = exp.get("tag_delta", {})
        coil = exp.get("coil_name", exp.get("io_point", "unknown"))
        exp_type = exp.get("experiment_type", "SingleCoilToggle")

        # Build input description
        before_str = ", ".join(f"{k}: {v}" for k, v in before.items()) if before else "unknown"
        delta_str = ", ".join(
            f"{k}: {v['old']} -> {v['new']}" for k, v in tag_delta.items()
        ) if tag_delta else "no changes observed"

        input_text = (
            f"Scene: {scene_name}\n"
            f"Experiment: {exp_type}\n"
            f"Output: {coil}\n"
            f"Before: {{{before_str}}}\n"
            f"Tag changes: {delta_str}"
        )

        record = {
            "instruction": instruction,
            "input": input_text,
            "output": learning,
            "metadata": {
                "scene": scene_name,
                "experiment_id": exp.get("experiment_id", 0),
                "confidence": exp.get("confidence", 0.0),
                "verified": exp.get("verified", False),
            },
        }

        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        count += 1

    return count


async def phase_4_consolidation(scene_id: int, ks: KnowledgeStore,
                                 training_config: Optional[dict] = None) -> dict:
    """Summarize learnings, write to KB, export JSON + JSONL."""
    update_status(phase="consolidation", status="running")

    context = ks.to_prompt_context(scene_id)
    scene = ks.get_scene(scene_id)
    scene_name = scene["name"] if scene else f"scene_{scene_id}"

    # Ask model to consolidate (degrades gracefully if LLM unavailable)
    try:
        result = await observer.consolidate_scene(context)
        consolidation = result.get("content", "")
        if consolidation:
            ks.add_learning(scene_id, f"Scene summary: {consolidation[:500]}",
                            confidence=0.9, category="behavior")
    except Exception as exc:
        logger.warning("Consolidation model unavailable: %s", exc)
        consolidation = ""

    # Write unwritten learnings to KB
    unwritten = ks.get_unwritten_learnings(scene_id)
    kb_written = 0
    for learning in unwritten:
        io_name = ""
        if learning.get("io_point_id"):
            io_pts = ks.get_io_points(scene_id)
            match = [p for p in io_pts if p["id"] == learning["io_point_id"]]
            if match:
                io_name = match[0]["name"]

        success = await observer.capture_learning(
            scene_name, io_name or "scene",
            learning["summary"], learning["confidence"],
            learning.get("experiment_id", 0),
        )
        if success:
            ks.mark_kb_written(learning["id"])
            kb_written += 1

    # Export knowledge JSON
    export = ks.export_scene_knowledge(scene_id)
    export_path = REPO_ROOT / "data" / "learner" / f"{scene_name.lower().replace(' ', '_')}_knowledge.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with open(export_path, "w") as f:
        json.dump(export, f, indent=2, default=str)
    logger.info("Exported knowledge to %s", export_path)

    # If LLM was unavailable, note that raw data is still preserved
    if not consolidation:
        failsafe = REPO_ROOT / "data" / "learner" / "experiment_log.jsonl"
        if failsafe.exists():
            n_records = sum(1 for _ in open(failsafe))
            logger.info("LLM unavailable — raw experiment data saved to %s (%d records). "
                        "Re-run Phase 4 later when LLM is available.", failsafe, n_records)

    # Export JSONL training data
    jsonl_count = 0
    if training_config:
        jsonl_path = REPO_ROOT / training_config.get("output_path", "data/training/qwen_plc_v1.jsonl")
        jsonl_count = export_training_jsonl(export, scene_name, jsonl_path)
        logger.info("Exported %d training records to %s", jsonl_count, jsonl_path)

    update_status(phase="consolidation", status="complete",
                  kb_written=kb_written, export_path=str(export_path),
                  training_records=jsonl_count)

    return export


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_scene(scene_name: str, ks: KnowledgeStore,
                    max_experiments: int = 100,
                    max_hours: float = 2.0,
                    settle_time: float = 2.0,
                    training_config: Optional[dict] = None) -> dict:
    """Run the full 4-phase experiment loop on a single scene."""
    t_start = time.time()
    deadline = t_start + (max_hours * 3600)
    logger.info("=== Starting scene: %s (max %d experiments, %.1f hours) ===",
                scene_name, max_experiments, max_hours)

    # Phase 0
    scene_id, io_records = await phase_0_setup(scene_name, ks)
    if not io_records:
        return {"scene": scene_name, "error": "No I/O points discovered", "experiments": 0}

    all_results = []
    remaining = max_experiments

    def _check_cost():
        if observer.cost_exceeded():
            logger.warning("COST CEILING HIT: $%.4f — stopping experiments",
                           observer.accumulated_cost)
            return True
        return False

    # Phase 1
    if time.time() < deadline and remaining > 0 and not _check_cost():
        p1 = await phase_1_verification(
            scene_id, io_records, ks,
            max_experiments=remaining, settle_time=settle_time,
        )
        all_results.extend(p1)
        remaining -= len(p1)

    # Phase 2
    if time.time() < deadline and remaining > 0 and not _check_cost():
        p2 = await phase_2_interactions(
            scene_id, io_records, ks, p1,
            max_experiments=min(remaining, 30),
        )
        all_results.extend(p2)
        remaining -= len(p2)

    # Phase 3
    if time.time() < deadline and remaining > 0 and not _check_cost():
        p3 = await phase_3_curiosity(
            scene_id, io_records, ks,
            max_experiments=min(remaining, 20),
        )
        all_results.extend(p3)

    # Phase 4
    export = await phase_4_consolidation(scene_id, ks, training_config)

    elapsed = time.time() - t_start
    stats = export.get("stats", {})
    logger.info("=== Scene '%s' complete: %d experiments in %.1f min ===",
                scene_name, len(all_results), elapsed / 60)

    return {
        "scene": scene_name,
        "scene_id": scene_id,
        "experiments": len(all_results),
        "verified": sum(1 for r in all_results if r.verified),
        "elapsed_min": round(elapsed / 60, 1),
        "stats": stats,
    }


async def run_all_scenes(scenes: list[str], ks: KnowledgeStore,
                          max_experiments: int = 100,
                          max_hours: float = 2.0,
                          training_config: Optional[dict] = None) -> list[dict]:
    """Run the learner across a queue of scenes."""
    results = []
    for i, scene_name in enumerate(scenes):
        logger.info("=== Scene %d/%d: %s ===", i + 1, len(scenes), scene_name)
        update_status(scene_index=i + 1, total_scenes=len(scenes))

        result = await run_scene(scene_name, ks, max_experiments, max_hours,
                                 training_config=training_config)
        results.append(result)

        # Cleanup between scenes
        sm.clear_all_coils()

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Factory I/O Scene Learner",
    )
    parser.add_argument(
        "--scenes",
        default=None,
        help="Comma-separated scene names (default: from config/learner.yaml)",
    )
    parser.add_argument("--max-experiments", type=int, default=None)
    parser.add_argument("--max-hours", type=float, default=None)
    parser.add_argument("--settle-time", type=float, default=None)
    parser.add_argument("--db", default=None, help="Path to knowledge.db")
    parser.add_argument("--session-type", default=None,
                        choices=["interactive_session", "overnight_batch", "cosmos_planning_session"],
                        help="Session type for cost ceiling selection")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Load config
    config = load_config()
    learner_cfg = config.get("learner", {})

    # Wire connection settings from config to module vars
    conns = config.get("connections", {})
    if conns.get("fio_api"):
        sm.FIO_API_BASE = conns["fio_api"]
    if conns.get("modbus_host"):
        sm.MODBUS_HOST = conns["modbus_host"]
    if conns.get("modbus_port"):
        sm.MODBUS_PORT = int(conns["modbus_port"])
    if conns.get("litellm_url"):
        observer.LITELLM_URL = conns["litellm_url"]
    if conns.get("vllm_url"):
        observer.VLLM_URL = conns["vllm_url"]

    # Wire inference config (free models only)
    inference_cfg = config.get("inference", {})
    session_type = (args.session_type
                    or os.getenv("FACTORYLM_SESSION_TYPE", "interactive_session"))
    if inference_cfg:
        observer.configure(inference_cfg, session_type=session_type)
        logger.info("Inference: vision=%s, text=%s, blocked=%s, session=%s, ceiling=$%.2f",
                     observer.VISION_MODELS, observer.TEXT_MODELS, observer.BLOCKED_MODELS,
                     observer._session_type, observer._max_cost)
    else:
        logger.info("No inference config — using defaults: vision=%s, text=%s",
                     observer.VISION_MODELS, observer.TEXT_MODELS)

    # Resolve settings (CLI > config > defaults)
    scenes = (
        [s.strip() for s in args.scenes.split(",")]
        if args.scenes
        else learner_cfg.get("scenes", ["Sorting by Height"])
    )
    max_exp = args.max_experiments or learner_cfg.get("max_experiments_per_scene", 100)
    max_hrs = args.max_hours or learner_cfg.get("max_hours_per_scene", 2.0)
    settle = args.settle_time or learner_cfg.get("settle_time_s", 2.0)

    # Init knowledge store
    ks = KnowledgeStore(db_path=args.db)

    # Training export config
    training_cfg = config.get("training_export")

    logger.info("Autonomous Scene Learner starting")
    logger.info("Scenes: %s", scenes)
    logger.info("Max experiments/scene: %d, Max hours/scene: %.1f", max_exp, max_hrs)
    logger.info("Modbus: %s:%s | FIO API: %s", sm.MODBUS_HOST, sm.MODBUS_PORT, sm.FIO_API_BASE)
    logger.info("Cost ceiling: $%.2f", observer._max_cost)
    logger.info("DB: %s", ks.db_path)

    # Run
    results = asyncio.run(run_all_scenes(scenes, ks, max_exp, max_hrs,
                                          training_config=training_cfg))

    # Summary
    print("\n" + "=" * 60)
    print("SCENE LEARNER RESULTS")
    print("=" * 60)
    for r in results:
        status = "ERROR" if "error" in r else "OK"
        print(f"  {r['scene']}: {status} — {r.get('experiments', 0)} experiments, "
              f"{r.get('verified', 0)} verified, {r.get('elapsed_min', 0)} min")
    print(f"  Total inference cost: ${observer.accumulated_cost:.4f}")
    print("=" * 60)

    ks.close()


if __name__ == "__main__":
    main()

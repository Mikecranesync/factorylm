"""Experiment Engine — execute experiments, capture before/after, compute delta.

Experiment types:
- SingleCoilToggle: Turn one coil ON, observe, turn OFF
- RegisterSweep: Write 0→25→50→75→100, observe each step
- MultiCoilCombination: Toggle 2-3 coils together
- SequenceDiscovery: Try ordered activation sequences
- SensorCorrelation: Toggle coil, monitor sensors for 5s
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from services.learner.knowledge_store import KnowledgeStore
from services.learner.safety import pre_write_check
from services.learner import scene_manager as sm
from services.learner import scene_observer as observer

logger = logging.getLogger("factorylm.learner.experiment")


@dataclass
class ExperimentResult:
    """Result of a single experiment."""
    experiment_id: int
    experiment_type: str
    coil_name: str
    before_tags: dict
    after_tags: dict
    tag_delta: dict
    before_screenshot: str
    after_screenshot: str
    vision_delta: str
    learning: str
    verified: bool
    mismatch_note: str
    confidence: float


# ---------------------------------------------------------------------------
# SingleCoilToggle
# ---------------------------------------------------------------------------

async def run_single_coil_toggle(
    scene_id: int,
    io_point: dict,
    io_map: Optional[dict],
    ks: KnowledgeStore,
    settle_time: float = 2.0,
) -> Optional[ExperimentResult]:
    """Toggle a single coil ON, observe, toggle OFF.

    Steps:
    1. Read current tags + screenshot (BEFORE)
    2. Write coil ON
    3. Wait for physics to settle
    4. Read tags + screenshot (AFTER)
    5. Compute tag delta
    6. Ask vision: what changed?
    7. Verify against official docs
    8. Extract learning
    9. Cleanup: write coil OFF
    """
    coil_name = io_point["name"]
    address = io_point["address"]
    official_desc = io_point.get("official_description", "")

    logger.info("Experiment: SingleCoilToggle on %s (addr=%d)", coil_name, address)

    # Safety check
    current_tags = sm.read_all_tags(io_map)
    safe, reason = pre_write_check(coil_name, current_tags)
    if not safe:
        logger.warning("Skipping %s: %s", coil_name, reason)
        return None

    # Start experiment record
    exp_id = ks.start_experiment(scene_id, "SingleCoilToggle", {
        "coil": coil_name, "address": address, "action": "toggle_on_off",
    })

    # BEFORE: capture state
    before_tags = sm.read_all_tags(io_map)
    before_screenshot = sm.capture_screenshot(f"before_{coil_name}") or ""
    ks.record_before(exp_id, before_tags, before_screenshot)

    vision_before = ""
    if before_screenshot:
        result = await observer.describe_scene(before_screenshot)
        vision_before = result.get("content", "")
        ks.record_before(exp_id, before_tags, before_screenshot, vision_before)

    # TOGGLE ON
    success = sm.write_coil(address, True, tag_name=coil_name, current_tags=before_tags)
    if not success:
        logger.error("Failed to write coil %s", coil_name)
        ks.complete_experiment(exp_id, {}, "Write failed", "Coil write failed")
        return None

    # Wait for physics to settle
    await asyncio.sleep(settle_time)
    after_tags = sm.wait_for_stable(io_map, timeout_s=5.0)

    # AFTER: capture state
    after_screenshot = sm.capture_screenshot(f"after_{coil_name}") or ""
    ks.record_after(exp_id, after_tags, after_screenshot)

    # Compute delta
    tag_delta = sm.compute_tag_delta(before_tags, after_tags)

    # Vision: describe change
    vision_delta = ""
    if after_screenshot:
        result = await observer.describe_change(
            before_screenshot, after_screenshot, coil_name, official_desc,
        )
        vision_delta = result.get("content", "")

    # Verify against official docs
    verified = False
    mismatch_note = ""
    if official_desc and after_screenshot:
        delta_summary = _format_delta_text(tag_delta)
        verify_result = await observer.verify_behavior(
            after_screenshot, coil_name, official_desc, delta_summary,
        )
        verify_text = verify_result.get("content", "")
        verified = verify_text.upper().startswith("MATCH")
        if not verified:
            mismatch_note = verify_text

    # Extract learning
    learning = ""
    if after_screenshot:
        learn_result = await observer.extract_learning(after_screenshot, coil_name, tag_delta)
        learning = learn_result.get("content", "")

    # Confidence scoring
    confidence = _compute_confidence(tag_delta, vision_delta, verified)

    # Complete experiment
    ks.complete_experiment(exp_id, tag_delta, vision_delta, learning, verified)

    # Update I/O point
    ks.update_io_learning(
        io_point["id"], learning, confidence, verified, mismatch_note,
    )

    # Store learning
    ks.add_learning(
        scene_id, learning, confidence,
        category="behavior",
        io_point_id=io_point["id"],
        experiment_id=exp_id,
    )

    # CLEANUP: toggle OFF
    sm.write_coil(address, False, tag_name=coil_name, current_tags=after_tags)
    await asyncio.sleep(0.5)

    logger.info("Experiment complete: %s → %s (conf=%.1f, verified=%s)",
                coil_name, learning[:60] if learning else "no learning", confidence, verified)

    return ExperimentResult(
        experiment_id=exp_id,
        experiment_type="SingleCoilToggle",
        coil_name=coil_name,
        before_tags=before_tags,
        after_tags=after_tags,
        tag_delta=tag_delta,
        before_screenshot=before_screenshot,
        after_screenshot=after_screenshot,
        vision_delta=vision_delta,
        learning=learning,
        verified=verified,
        mismatch_note=mismatch_note,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# RegisterSweep
# ---------------------------------------------------------------------------

async def run_register_sweep(
    scene_id: int,
    io_point: dict,
    io_map: Optional[dict],
    ks: KnowledgeStore,
    values: tuple[int, ...] = (0, 25, 50, 75, 100),
    settle_time: float = 2.0,
) -> Optional[ExperimentResult]:
    """Sweep a register through a range of values and observe effects."""
    reg_name = io_point["name"]
    address = io_point["address"]
    official_desc = io_point.get("official_description", "")

    logger.info("Experiment: RegisterSweep on %s (addr=%d) values=%s", reg_name, address, values)

    current_tags = sm.read_all_tags(io_map)
    safe, reason = pre_write_check(reg_name, current_tags)
    if not safe:
        logger.warning("Skipping %s: %s", reg_name, reason)
        return None

    exp_id = ks.start_experiment(scene_id, "RegisterSweep", {
        "register": reg_name, "address": address, "values": list(values),
    })

    # Capture before (at current value)
    before_tags = current_tags
    before_screenshot = sm.capture_screenshot(f"before_{reg_name}") or ""
    ks.record_before(exp_id, before_tags, before_screenshot)

    # Sweep through values
    observations = []
    last_tags = before_tags
    for val in values:
        sm.write_register(address, val, tag_name=reg_name, current_tags=last_tags)
        await asyncio.sleep(settle_time)
        snapshot = sm.wait_for_stable(io_map, timeout_s=3.0)
        delta = sm.compute_tag_delta(last_tags, snapshot)
        observations.append({"value": val, "delta": delta})
        last_tags = snapshot

    # Capture after (at last value)
    after_tags = last_tags
    after_screenshot = sm.capture_screenshot(f"after_{reg_name}") or ""
    ks.record_after(exp_id, after_tags, after_screenshot)

    # Combined delta from start to end
    full_delta = sm.compute_tag_delta(before_tags, after_tags)

    # Vision description
    vision_delta = ""
    if after_screenshot:
        result = await observer.describe_change(
            before_screenshot, after_screenshot, reg_name, official_desc,
        )
        vision_delta = result.get("content", "")

    # Extract learning
    learning = ""
    if after_screenshot:
        learn_result = await observer.extract_learning(after_screenshot, reg_name, full_delta)
        learning = learn_result.get("content", "")

    confidence = _compute_confidence(full_delta, vision_delta, False)

    ks.complete_experiment(exp_id, full_delta, vision_delta, learning, False)
    ks.update_io_learning(io_point["id"], learning, confidence)
    ks.add_learning(scene_id, learning, confidence, "behavior",
                    io_point["id"], exp_id)

    # Cleanup: reset to 0
    sm.write_register(address, 0, tag_name=reg_name, current_tags=after_tags)
    await asyncio.sleep(0.5)

    return ExperimentResult(
        experiment_id=exp_id, experiment_type="RegisterSweep",
        coil_name=reg_name, before_tags=before_tags, after_tags=after_tags,
        tag_delta=full_delta, before_screenshot=before_screenshot,
        after_screenshot=after_screenshot, vision_delta=vision_delta,
        learning=learning, verified=False, mismatch_note="", confidence=confidence,
    )


# ---------------------------------------------------------------------------
# MultiCoilCombination
# ---------------------------------------------------------------------------

async def run_multi_coil(
    scene_id: int,
    io_points: list[dict],
    io_map: Optional[dict],
    ks: KnowledgeStore,
    settle_time: float = 3.0,
) -> Optional[ExperimentResult]:
    """Toggle multiple coils simultaneously to find interactions."""
    names = [p["name"] for p in io_points]
    addresses = [p["address"] for p in io_points]
    logger.info("Experiment: MultiCoilCombination on %s", names)

    current_tags = sm.read_all_tags(io_map)
    for name in names:
        safe, reason = pre_write_check(name, current_tags)
        if not safe:
            logger.warning("Skipping multi-coil: %s blocked by %s", names, reason)
            return None

    exp_id = ks.start_experiment(scene_id, "MultiCoilCombination", {
        "coils": names, "addresses": addresses,
    })

    before_tags = current_tags
    before_screenshot = sm.capture_screenshot(f"before_multi_{'_'.join(names[:3])}") or ""
    ks.record_before(exp_id, before_tags, before_screenshot)

    # Toggle all ON
    for addr, name in zip(addresses, names):
        sm.write_coil(addr, True, tag_name=name, current_tags=before_tags)
        await asyncio.sleep(0.2)

    await asyncio.sleep(settle_time)
    after_tags = sm.wait_for_stable(io_map, timeout_s=5.0)
    after_screenshot = sm.capture_screenshot(f"after_multi_{'_'.join(names[:3])}") or ""
    ks.record_after(exp_id, after_tags, after_screenshot)

    tag_delta = sm.compute_tag_delta(before_tags, after_tags)

    vision_delta = ""
    if after_screenshot:
        combo_desc = ", ".join(names)
        result = await observer.describe_change(
            before_screenshot, after_screenshot, combo_desc, "multiple coils",
        )
        vision_delta = result.get("content", "")

    learning = f"Combination [{', '.join(names)}]: {vision_delta[:100]}" if vision_delta else ""
    confidence = _compute_confidence(tag_delta, vision_delta, False)

    ks.complete_experiment(exp_id, tag_delta, vision_delta, learning, False)
    ks.add_learning(scene_id, learning, confidence, "interaction", experiment_id=exp_id)

    # Cleanup: all OFF
    for addr, name in zip(addresses, names):
        sm.write_coil(addr, False, tag_name=name, current_tags=after_tags)
    await asyncio.sleep(0.5)

    return ExperimentResult(
        experiment_id=exp_id, experiment_type="MultiCoilCombination",
        coil_name="|".join(names), before_tags=before_tags, after_tags=after_tags,
        tag_delta=tag_delta, before_screenshot=before_screenshot,
        after_screenshot=after_screenshot, vision_delta=vision_delta,
        learning=learning, verified=False, mismatch_note="", confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_delta_text(tag_delta: dict) -> str:
    """Format tag delta as human-readable text."""
    if not tag_delta:
        return "No tag changes observed."
    parts = []
    for name, change in tag_delta.items():
        parts.append(f"{name}: {change['old']} -> {change['new']}")
    return "; ".join(parts)


def _compute_confidence(tag_delta: dict, vision_delta: str, verified: bool) -> float:
    """Heuristic confidence score for an experiment."""
    score = 0.1  # Base

    # Tag changes observed = more confidence
    if tag_delta:
        score += 0.2
        if len(tag_delta) >= 2:
            score += 0.1

    # Vision model gave a response
    if vision_delta and len(vision_delta) > 20:
        score += 0.2

    # Verified against docs
    if verified:
        score += 0.3

    return min(score, 1.0)

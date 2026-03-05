#!/usr/bin/env python3
"""
FactoryLM Visual Test Loop — AI-Driven Fault Diagnosis Demo
============================================================
Cosmos R2 watches Factory I/O, diagnoses faults, and prescribes code fixes.

Loop: record clip -> read FIO tags -> send to Cosmos R2 -> display diagnosis

Usage:
    python cookoff/visual_test_loop.py                        # Interactive menu
    python cookoff/visual_test_loop.py --scenario jam         # Single scenario
    python cookoff/visual_test_loop.py --all                  # Run all scenarios
    python cookoff/visual_test_loop.py --dry-run              # Skip Cosmos call
    python cookoff/visual_test_loop.py --vllm-url http://...  # Custom vLLM endpoint
    python cookoff/visual_test_loop.py --fio-url http://...   # Custom FIO API

Requires:
    - Factory I/O running with Web API enabled (default :7410)
    - vLLM serving Cosmos R2 (default localhost:8000)
"""

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding (skip if already wrapped by diagnosis_engine)
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    if getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cookoff.capture_fio import capture_clip, capture_screenshot, chunk_session, record_session, stop_recording
from cookoff.diagnosis_engine import (
    diagnose,
    encode_media,
    format_fault_analysis,
    format_plc_registers,
    load_prompts,
    VLLM_URL,
    MODEL_NAME,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
)
from sim.sorting_controller import FactoryIOClient
from sim.fault_injector import FaultInjector, FAULTS

import requests
import yaml


# ---------------------------------------------------------------------------
# Fault scenarios for the visual test loop
# ---------------------------------------------------------------------------
SCENARIOS = {
    "normal": {
        "id": None,
        "note": "Baseline -- healthy operation",
        "settle_time": 2.0,
    },
    "pile_up": {
        "id": "jam",
        "note": "Pallet sensor stuck ON -- boxes pile up",
        "settle_time": 3.0,
    },
    "blind": {
        "id": "sensor",
        "note": "Height sensors dead -- all boxes route wrong",
        "settle_time": 2.0,
    },
    "estop": {
        "id": "estop",
        "note": "Emergency stop engaged -- immediate halt",
        "settle_time": 1.0,
    },
    "stuck_left": {
        "id": "sorter_stuck_left",
        "note": "Left transfer arm locked -- all boxes go left",
        "settle_time": 2.0,
    },
    "no_parts": {
        "id": "emitter_off",
        "note": "No new parts entering system",
        "settle_time": 3.0,
    },
}


# ---------------------------------------------------------------------------
# Visual Test Loop
# ---------------------------------------------------------------------------
class VisualTestLoop:
    """Three-mode visual testing harness for Cosmos R2 + Factory I/O.

    Modes:
        1. Observe-only (--dry-run): capture + tags, no Cosmos call
        2. Diagnose: capture + tags + Cosmos R2 diagnosis
        3. Prescribe: capture + tags + code snippet + Cosmos R2 diagnosis + fix
    """

    def __init__(
        self,
        vllm_url: str = VLLM_URL,
        fio_url: str = "http://localhost:7410",
        controller_path: str = "sim/sorting_controller.py",
        dry_run: bool = False,
        obs_clip: str | None = None,
        clip_duration: float = 8,
        chunk_duration: float = 8,
    ):
        self.vllm_url = vllm_url
        self.fio_url = fio_url
        self.controller_path = Path(REPO_ROOT) / controller_path
        self.dry_run = dry_run
        self.obs_clip = obs_clip
        self.clip_duration = clip_duration
        self.chunk_duration = chunk_duration
        self.iteration = 0
        self.results: list[dict] = []

        # Initialize Factory I/O client and fault injector
        self.fio = FactoryIOClient(base_url=fio_url)
        self.injector = FaultInjector(self.fio)

    def check_prerequisites(self) -> bool:
        """Verify Factory I/O is reachable."""
        if not self.fio.check_connection():
            print(f"ERROR: Cannot connect to Factory I/O at {self.fio_url}")
            print("Make sure Factory I/O is running with Web API enabled (Edit > Options > Web API).")
            return False
        print(f"Factory I/O connected: {self.fio_url}")

        if not self.dry_run:
            try:
                r = requests.get(
                    self.vllm_url.replace("/chat/completions", "/models"),
                    timeout=5,
                )
                if r.status_code == 200:
                    print(f"vLLM connected: {self.vllm_url}")
                else:
                    print(f"WARNING: vLLM returned {r.status_code} -- diagnoses may fail")
            except requests.ConnectionError:
                print(f"WARNING: Cannot reach vLLM at {self.vllm_url}")
                print("Diagnoses will fail. Use --dry-run for capture-only mode.")

        return True

    def run_iteration(self, scenario_name: str) -> dict:
        """One full observe -> diagnose -> prescribe cycle."""
        self.iteration += 1
        scenario = SCENARIOS.get(scenario_name)
        if not scenario:
            print(f"ERROR: Unknown scenario '{scenario_name}'. Available: {list(SCENARIOS.keys())}")
            return {"error": f"Unknown scenario: {scenario_name}"}

        fault_id = scenario["id"]
        settle_time = scenario.get("settle_time", 2.0)

        print(f"\n{'='*70}")
        print(f"  VISUAL TEST LOOP -- Iteration {self.iteration}")
        print(f"  Scenario: {scenario_name} ({scenario['note']})")
        print(f"{'='*70}\n")

        # 1. Inject fault (if any)
        if fault_id:
            print(f"[1/6] Injecting fault: {fault_id}")
            self.injector.inject(fault_id)
            print(f"  Settling for {settle_time}s...")
            time.sleep(settle_time)
        else:
            print("[1/6] No fault injection (baseline)")

        # 2. Record clip (or use pre-recorded)
        if self.obs_clip:
            print(f"[2/6] Using pre-recorded clip: {self.obs_clip}")
            frame_path = Path(self.obs_clip)
        else:
            print(f"[2/6] Recording {self.clip_duration}s clip...")
            frame_path = capture_clip(
                duration_seconds=self.clip_duration,
                label=f"iter{self.iteration}_{scenario_name}",
            )
        print(f"  Media: {frame_path}")

        # 3. Read live FIO tags
        print("[3/6] Reading Factory I/O tags...")
        tags = self.fio.read_all_values()
        if tags:
            # Show compact tag summary
            bool_tags = {k: v for k, v in tags.items() if isinstance(v, bool)}
            on_tags = [k for k, v in bool_tags.items() if v]
            print(f"  {len(tags)} tags read. Active: {on_tags or 'none'}")
        else:
            print("  WARNING: Could not read tags")
            tags = {}

        # 4. Extract controller code snippet
        print("[4/6] Extracting tick() method...")
        code_snippet = self._extract_tick_method()
        print(f"  {len(code_snippet.splitlines())} lines extracted")

        # 5. Call Cosmos R2 (or skip in dry-run)
        result = {
            "iteration": self.iteration,
            "scenario": scenario_name,
            "fault_id": fault_id,
            "note": scenario["note"],
            "frame_path": str(frame_path),
            "tags": tags,
            "code_lines": len(code_snippet.splitlines()),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if self.dry_run:
            print("[5/6] DRY RUN -- skipping Cosmos R2 call")
            result["reasoning"] = "(dry run)"
            result["diagnosis"] = "(dry run -- no Cosmos R2 call)"
            result["prescription"] = "(dry run)"
            result["confidence"] = "N/A"
            result["elapsed_s"] = 0
            result["tokens"] = 0
        else:
            print("[5/6] Sending to Cosmos R2...")
            cosmos_result = self._call_cosmos(frame_path, tags, code_snippet, scenario_name)
            result.update(cosmos_result)

        # 6. Print formatted output
        print(f"\n[6/6] Results:")
        self._print_result(result)

        # 7. Clear fault
        if fault_id:
            self.injector.clear(fault_id)
            print(f"\nFault '{fault_id}' cleared.")

        # 8. Log to results
        self.results.append(result)
        return result

    def _call_cosmos(self, frame_path: Path, tags: dict, code_snippet: str, scenario_name: str) -> dict:
        """Send frame + tags + code to Cosmos R2 and parse response."""
        prompts = load_prompts()
        system_prompt = prompts["system"]

        # Build the prescribe prompt
        user_template = prompts.get("user_prescribe", prompts["user_diagnosis"])
        plc_registers = format_plc_registers(tags) if tags else "No PLC data available"
        fault_analysis = format_fault_analysis(tags) if tags else "No fault data available"

        try:
            user_prompt = user_template.format(
                plc_registers=plc_registers,
                fault_analysis=fault_analysis,
                code_snippet=code_snippet,
            )
        except KeyError:
            # Fall back to diagnosis template if prescribe template missing code_snippet
            user_prompt = prompts["user_diagnosis"].format(
                plc_registers=plc_registers,
                fault_analysis=fault_analysis,
            )

        # Encode frame/clip — encode_media returns correct MIME for .mp4 vs .png
        b64, mime = encode_media(str(frame_path))
        if mime.startswith("video"):
            media_content = {
                "type": "video_url",
                "video_url": {"url": f"data:{mime};base64,{b64}"},
            }
        else:
            media_content = {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        user_content = [media_content, {"type": "text", "text": user_prompt}]

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": DEFAULT_MAX_TOKENS,
            "temperature": DEFAULT_TEMPERATURE,
            "top_p": DEFAULT_TOP_P,
        }

        # Tell vLLM how to sample video frames
        if mime.startswith("video"):
            payload["media_io_kwargs"] = {"video": {"fps": 1.0}}

        t_start = time.time()
        try:
            response = requests.post(
                self.vllm_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            elapsed = time.time() - t_start

            if response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code}: {response.text[:500]}",
                    "elapsed_s": round(elapsed, 1),
                    "reasoning": "",
                    "diagnosis": f"Error: HTTP {response.status_code}",
                    "prescription": "",
                    "confidence": "N/A",
                    "tokens": 0,
                }

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            # Parse <think> blocks
            reasoning = ""
            diagnosis_text = content
            if "<think>" in content and "</think>" in content:
                think_start = content.index("<think>") + len("<think>")
                think_end = content.index("</think>")
                reasoning = content[think_start:think_end].strip()
                diagnosis_text = content[think_end + len("</think>"):].strip()

            # Try to extract confidence from response
            confidence = "UNKNOWN"
            for level in ["HIGH", "MEDIUM", "LOW"]:
                if level in diagnosis_text.upper():
                    confidence = level
                    break

            return {
                "reasoning": reasoning,
                "diagnosis": diagnosis_text,
                "prescription": self._extract_prescription(diagnosis_text),
                "confidence": confidence,
                "elapsed_s": round(elapsed, 1),
                "tokens": usage.get("completion_tokens", 0),
                "raw_response": content,
            }

        except requests.ConnectionError as e:
            return {
                "error": f"Connection failed: {e}",
                "elapsed_s": 0,
                "reasoning": "",
                "diagnosis": "Error: Cannot connect to vLLM",
                "prescription": "",
                "confidence": "N/A",
                "tokens": 0,
            }

    def _extract_prescription(self, diagnosis_text: str) -> str:
        """Extract the PRESCRIPTION section from diagnosis text."""
        lines = diagnosis_text.splitlines()
        in_prescription = False
        prescription_lines = []

        for line in lines:
            upper = line.strip().upper()
            if upper.startswith("PRESCRIPTION") or upper.startswith("**PRESCRIPTION"):
                in_prescription = True
                continue
            elif in_prescription and (
                upper.startswith("CONFIDENCE") or upper.startswith("**CONFIDENCE")
                or upper.startswith("DIAGNOSIS") or upper.startswith("**DIAGNOSIS")
            ):
                break
            elif in_prescription:
                prescription_lines.append(line)

        return "\n".join(prescription_lines).strip() if prescription_lines else "(no prescription section found)"

    def _extract_tick_method(self) -> str:
        """Extract the tick() method from sorting_controller.py for the prompt."""
        try:
            source = self.controller_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return "# Controller file not found"

        lines = source.splitlines()
        # Find "def tick(self):" and extract until next "def " at same indent level
        start = None
        for i, line in enumerate(lines):
            if "def tick(self)" in line:
                start = i
                break

        if start is None:
            return "# tick() method not found in controller"

        end = len(lines)
        for i in range(start + 1, len(lines)):
            # Next method at same indent level (4 spaces for class method)
            stripped = lines[i]
            if stripped.startswith("    def ") and i > start + 5:
                end = i
                break

        # Cap at ~120 lines to avoid blowing context
        if end - start > 120:
            end = start + 120

        return "\n".join(lines[start:end])

    def _print_result(self, result: dict):
        """Print formatted iteration result."""
        print(f"\n{'- '*35}")
        print(f"Scenario: {result['scenario']} ({result.get('note', '')})")
        print(f"Frame:    {result['frame_path']}")

        if result.get("reasoning") and result["reasoning"] != "(dry run)":
            print(f"\nCOSMOS R2 CHAIN-OF-THOUGHT:")
            # Truncate reasoning for display
            reasoning = result["reasoning"]
            if len(reasoning) > 500:
                reasoning = reasoning[:500] + "..."
            for line in reasoning.splitlines():
                print(f"  {line}")

        if result.get("diagnosis") and result["diagnosis"] != "(dry run -- no Cosmos R2 call)":
            print(f"\nDIAGNOSIS:")
            print(f"  {result['diagnosis'][:300]}")

        if result.get("prescription") and result["prescription"] != "(dry run)":
            print(f"\nPRESCRIPTION:")
            for line in result["prescription"].splitlines()[:10]:
                print(f"  {line}")

        confidence = result.get("confidence", "N/A")
        elapsed = result.get("elapsed_s", 0)
        tokens = result.get("tokens", 0)
        print(f"\nConfidence: {confidence} | Elapsed: {elapsed}s | Tokens: {tokens}")

        if result.get("error"):
            print(f"\nERROR: {result['error']}")

    def run_session(self):
        """Record continuous session, chunk it, diagnose each chunk."""
        if self.obs_clip:
            # Pre-recorded file -- still needs chunking
            session_path = Path(self.obs_clip)
            print(f"Using pre-recorded session: {session_path}")
            print(f"\nSplitting into {self.chunk_duration}s chunks...")
            chunks = chunk_session(session_path, chunk_duration=self.chunk_duration)
            print(f"Split into {len(chunks)} chunks.\n")
            if not chunks:
                print("ERROR: No chunks produced. Recording may be too short.")
                return
            chunk_paths = [Path(c["chunk_file"]) for c in chunks]
        else:
            # Live recording -- already produces rolling chunks
            print("Recording rolling chunks. To stop:")
            print("  python cookoff/capture_fio.py stop")
            chunk_paths = record_session(
                label="session",
                chunk_duration=self.chunk_duration,
            )

        if not chunk_paths:
            print("ERROR: No chunks produced.")
            return

        # Diagnose each chunk
        for i, chunk_path in enumerate(chunk_paths):
            print(f"\n{'='*70}")
            print(f"  CHUNK {i+1}/{len(chunk_paths)}: {chunk_path.name}")
            print(f"{'='*70}")

            # Read live tags
            tags = self.fio.read_all_values() or {}
            if tags:
                on_tags = [k for k, v in tags.items() if isinstance(v, bool) and v]
                print(f"  Tags: {len(tags)} total, active: {on_tags or 'none'}")

            if self.dry_run:
                print(f"  DRY RUN -- skipping R2 for {chunk_path.name}")
                self.results.append({
                    "iteration": i + 1,
                    "scenario": f"chunk_{i+1}",
                    "frame_path": str(chunk_path),
                    "tags": tags,
                    "diagnosis": "(dry run)",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                continue

            code_snippet = self._extract_tick_method()
            cosmos_result = self._call_cosmos(chunk_path, tags, code_snippet, f"chunk_{i+1}")

            result = {
                "iteration": i + 1,
                "scenario": f"chunk_{i+1}",
                "frame_path": str(chunk_path),
                "tags": tags,
                "code_lines": len(code_snippet.splitlines()),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                **cosmos_result,
            }
            self.results.append(result)
            self._print_result(result)

        self._print_summary()

    def run_all(self):
        """Run all scenarios sequentially."""
        for name in SCENARIOS:
            self.run_iteration(name)
            if name != list(SCENARIOS.keys())[-1]:
                print("\n  Waiting 3s before next scenario...")
                time.sleep(3.0)
        self._print_summary()

    def run_interactive(self):
        """Interactive menu for running scenarios."""
        print("\n" + "="*70)
        print("  FACTORYLM VISUAL TEST LOOP -- Interactive Mode")
        print("="*70)
        print(f"\n  Factory I/O: {self.fio_url}")
        print(f"  vLLM:        {self.vllm_url}")
        print(f"  Controller:  {self.controller_path}")
        print(f"  Dry run:     {self.dry_run}")
        print()

        while True:
            print("\nAvailable scenarios:")
            for i, (name, sc) in enumerate(SCENARIOS.items(), 1):
                fault = sc["id"] or "none"
                print(f"  {i}. {name:<15} (fault: {fault}) -- {sc['note']}")

            print(f"\n  a. Run ALL scenarios")
            print(f"  s. Show summary")
            print(f"  q. Quit")

            try:
                choice = input("\nSelect scenario (name, number, a/s/q): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if choice in ("q", "quit", "exit"):
                break
            elif choice in ("a", "all"):
                self.run_all()
            elif choice in ("s", "summary"):
                self._print_summary()
            elif choice in SCENARIOS:
                self.run_iteration(choice)
                self._prompt_apply_fix()
            elif choice.isdigit():
                idx = int(choice) - 1
                names = list(SCENARIOS.keys())
                if 0 <= idx < len(names):
                    self.run_iteration(names[idx])
                    self._prompt_apply_fix()
                else:
                    print(f"  Invalid number. Choose 1-{len(names)}.")
            else:
                print(f"  Unknown: '{choice}'")

        self._print_summary()

    def _prompt_apply_fix(self):
        """Ask operator whether to apply the prescribed fix."""
        if self.dry_run or not self.results:
            return
        last = self.results[-1]
        if last.get("prescription") and last["prescription"] != "(no prescription section found)":
            try:
                answer = input("\nApply fix? (y/n/skip): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if answer == "y":
                print("  -> Manual fix application mode: review prescription above and edit code.")
                print("     (Automatic code mutation not implemented -- safe by design)")
            elif answer == "n":
                print("  -> Fix skipped.")

    def _print_summary(self):
        """Print summary of all iterations."""
        if not self.results:
            print("\nNo iterations completed yet.")
            return

        print(f"\n{'='*70}")
        print(f"  SESSION SUMMARY -- {len(self.results)} iterations")
        print(f"{'='*70}")

        for r in self.results:
            status = "OK" if not r.get("error") else "ERR"
            conf = r.get("confidence", "N/A")
            elapsed = r.get("elapsed_s", 0)
            print(f"  [{status}] iter{r['iteration']} {r['scenario']:<15} "
                  f"confidence={conf:<7} elapsed={elapsed}s")

        # Save results to JSON
        out_path = REPO_ROOT / "cookoff" / "clips" / f"session_{time.strftime('%Y%m%d_%H%M%S')}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            # Strip raw_response and tags to keep file small
            slim = []
            for r in self.results:
                entry = {k: v for k, v in r.items() if k not in ("raw_response", "tags")}
                slim.append(entry)
            json.dump(slim, f, indent=2, default=str)
        print(f"\n  Results saved: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="FactoryLM Visual Test Loop -- Cosmos R2 + Factory I/O",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scenario", help="Run a single scenario by name")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--dry-run", action="store_true", help="Skip Cosmos R2 call")
    parser.add_argument("--vllm-url", default=os.getenv("VLLM_URL", VLLM_URL),
                        help="vLLM endpoint URL")
    parser.add_argument("--fio-url", default=os.getenv("FACTORYIO_URL", "http://localhost:7410"),
                        help="Factory I/O Web API URL")
    parser.add_argument("--controller", default="sim/sorting_controller.py",
                        help="Path to sorting controller (relative to repo root)")
    parser.add_argument("--obs-clip", default=None,
                        help="Path to a pre-recorded clip (skip live capture)")
    parser.add_argument("--clip-duration", type=float, default=8,
                        help="Seconds to record per clip (default: 8)")
    parser.add_argument("--session", action="store_true",
                        help="Record continuous session, chunk it, diagnose each chunk")
    parser.add_argument("--chunk-duration", type=float, default=8,
                        help="Seconds per chunk in session mode (default: 8)")
    args = parser.parse_args()

    loop = VisualTestLoop(
        vllm_url=args.vllm_url,
        fio_url=args.fio_url,
        controller_path=args.controller,
        dry_run=args.dry_run,
        obs_clip=args.obs_clip,
        clip_duration=args.clip_duration,
        chunk_duration=args.chunk_duration,
    )

    if not loop.check_prerequisites():
        sys.exit(1)

    if args.session:
        loop.run_session()
    elif args.all:
        loop.run_all()
    elif args.scenario:
        loop.run_iteration(args.scenario)
    else:
        loop.run_interactive()


if __name__ == "__main__":
    main()

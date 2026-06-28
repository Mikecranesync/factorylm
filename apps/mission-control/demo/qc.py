#!/usr/bin/env python3
"""
Mission Control — Promo Video QC Gate (deterministic, no LLM)

Catches the defects an LLM-as-judge should NEVER be spent on (Cluster Law 2:
binary checks = plain script). Run this BEFORE the LLM judge — it fails loud
and cheap, and it extracts the timecode-aligned frames the judge then reads.

Checks per tab:
  - exists      : the merged .mp4 is present
  - motion      : if the script.md has a SCROLL/CLICK/etc action, the video must
                  actually move (intra-video pixel diff > MIN_INTRA). PAUSE-only
                  scripts are legitimately static, so motion is NOT required there.
                  A frozen recording of a scripted-scroll tab scores ~0 => FAIL.
  - av_sync     : |video_duration - audio_duration| within tolerance
  - distinct    : tab's frame is not a near-duplicate of another tab
                  (8x8 average-hash + Hamming distance — this single check catches
                   "all 8 tabs recorded the same screen")

Side effect: writes timecode-aligned frames to qc/<slug>/seg_NN.jpg and a
machine-readable qc/report.json that the /judge-demo skill consumes.

Beyond the pass/fail gate it also reports PRODUCTION-QUALITY measures that feed the
RUBRIC.md production tier (resolution, WPM, integrated LUFS + true peak, intro/outro
sting heuristic, caption CPS/CPL). These never FAIL the gate — they inform the tier.

Usage (from apps/mission-control/):
  python3 demo/qc.py            # all 8 tabs
  python3 demo/qc.py 01_command_board 08_scan   # specific tabs

Env (gate):   AV_TOLERANCE_S (0.75)  MIN_INTRA (1.0)  DUP_PIXDIFF (1.0)
Env (tier):   WPM_MIN (110)  WPM_MAX (155)  LUFS_TARGET (-16)  LUFS_TOL (2)
              TP_MAX (-1)  CPS_MAX (17)  CPL_MAX (42)
"""
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
TABS_DIR = os.path.join(DEMO_DIR, "tabs")
QC_DIR = os.path.join(DEMO_DIR, "qc")

ALL_TABS = [
    "01_command_board", "02_command_center", "03_namespace", "04_knowledge",
    "05_channels", "06_assets", "07_workorders", "08_scan",
]

AV_TOLERANCE_S = float(os.environ.get("AV_TOLERANCE_S", "0.75"))
MIN_INTRA = float(os.environ.get("MIN_INTRA", "1.0"))      # min intra-video per-pixel mean-abs diff to count as "moved" (frozen ~0)
DUP_PIXDIFF = float(os.environ.get("DUP_PIXDIFF", "1.0"))  # cross-tab mean-abs diff BELOW this => same screen recorded twice
# Calibrated 2026-06-28: genuinely-distinct sections that share sidebar chrome
# diff 1.87-5.87; a true duplicate (recorder stuck on one screen) diffs ~0.

# Production-quality thresholds (report-only; feed the RUBRIC.md Tier, never FAIL the gate)
WPM_MIN = float(os.environ.get("WPM_MIN", "110"))
WPM_MAX = float(os.environ.get("WPM_MAX", "155"))
LUFS_TARGET = float(os.environ.get("LUFS_TARGET", "-16"))
LUFS_TOL = float(os.environ.get("LUFS_TOL", "2"))
TP_MAX = float(os.environ.get("TP_MAX", "-1"))
CPS_MAX = float(os.environ.get("CPS_MAX", "17"))
CPL_MAX = int(os.environ.get("CPL_MAX", "42"))
BRAND_COLORS = ((26, 35, 126), (14, 165, 233))  # #1a237e logo bg, #0ea5e9 primary


def run(cmd: List[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def mp4_path(slug: str) -> str:
    name = slug.split("_", 1)[1]  # 01_chat_relay -> chat_relay
    return os.path.join(TABS_DIR, slug, name + ".mp4")


def probe_duration(path: str, stream: str) -> Optional[float]:
    out = run(["ffprobe", "-v", "error", "-select_streams", stream,
               "-show_entries", "stream=duration", "-of", "csv=p=0", path]).strip()
    try:
        return float(out)
    except ValueError:
        return None


def scene_changes(path: str) -> int:
    out = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path,
         "-vf", "select='gt(scene,0.1)',showinfo", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    return out.count("pts_time")


def gray_frame(path: str, at: float, size: int = 32) -> Optional[bytes]:
    """size x size grayscale raw bytes — fine enough to see a scroll that the
    8x8 average-hash blurs away on a uniform-background page."""
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", str(at), "-i", path,
         "-frames:v", "1", "-vf", "scale=%d:%d,format=gray" % (size, size),
         "-f", "rawvideo", "-"], capture_output=True).stdout
    return raw[:size * size] if len(raw) >= size * size else None


def mean_abs_diff(a: bytes, b: bytes) -> float:
    n = min(len(a), len(b))
    if not n:
        return 0.0
    return sum(abs(a[i] - b[i]) for i in range(n)) / n


def intra_motion(path: str, vdur: float) -> float:
    """Max per-pixel mean-abs difference (0-255) across sampled frames. ~0 =>
    frozen video; higher => the screen changed (scroll/click/animation).
    Sensitive to gradual scroll that scene-cut detection and 8x8 hashing miss."""
    if vdur <= 0:
        return 0.0
    frames = [gray_frame(path, vdur * f) for f in (0.12, 0.32, 0.52, 0.72, 0.9)]
    frames = [f for f in frames if f is not None]
    m = 0.0
    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            m = max(m, mean_abs_diff(frames[i], frames[j]))
    return round(m, 2)


def script_expects_motion(slug: str) -> bool:
    """True if the tab's script.md contains an action that should visibly move
    the screen (SCROLL/CLICK/HOVER/FILL/NAV). PAUSE-only scripts legitimately
    produce a static video, so motion must NOT be required for them."""
    sp = os.path.join(TABS_DIR, slug, "script.md")
    if not os.path.exists(sp):
        return False
    import re
    with open(sp) as f:
        for line in f:
            m = re.match(r"^\[\d{2}:\d{2}:\d{2}\]\s+\[([^\]]+)\]", line)
            if m and m.group(1).split(":")[0] in ("SCROLL", "CLICK", "HOVER", "FILL", "NAV"):
                return True
    return False


# ---------------------------------------------------------------------------
# Production-quality measures (report-only; feed RUBRIC.md production tier)
# ---------------------------------------------------------------------------

def probe_resolution(path: str) -> Optional[str]:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height",
               "-of", "csv=p=0:s=x", path]).strip()
    return out or None


def script_word_count(slug: str) -> int:
    """Count narration words in script.md (skips action tags and the END marker)."""
    sp = os.path.join(TABS_DIR, slug, "script.md")
    if not os.path.exists(sp):
        return 0
    words = 0
    with open(sp) as f:
        for line in f:
            m = re.match(r"^\[\d{2}:\d{2}:\d{2}\]\s+\[([^\]]+)\]\s*(.*)$", line)
            if not m:
                continue
            action, text = m.group(1).split(":")[0], m.group(2).strip()
            if action == "END" or not text:
                continue
            words += len(text.split())
    return words


def measure_loudness(path: str) -> Dict[str, Optional[float]]:
    """Integrated loudness (LUFS) + true peak (dBTP) via ffmpeg ebur128 summary.
    'I:' appears in running lines too, so take the LAST match (the Summary block)."""
    err = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-i", path,
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    i_m = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", err)
    p_m = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", err)
    return {"integrated_lufs": float(i_m[-1]) if i_m else None,
            "true_peak_dbtp": float(p_m[-1]) if p_m else None}


def rgb_frame(path: str, at: float, size: int = 8) -> Optional[bytes]:
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", str(at), "-i", path,
         "-frames:v", "1", "-vf", "scale=%d:%d,format=rgb24" % (size, size),
         "-f", "rawvideo", "-"], capture_output=True).stdout
    return raw[:size * size * 3] if len(raw) >= size * size * 3 else None


def brand_fraction(frame: Optional[bytes], dist: float = 70.0) -> float:
    """Fraction of pixels near a brand color — a branded title card scores high,
    the app UI (white bg + slate sidebar) scores low."""
    if not frame:
        return 0.0
    n = len(frame) // 3
    hits = 0
    for k in range(n):
        r, g, b = frame[3 * k], frame[3 * k + 1], frame[3 * k + 2]
        for (br, bg, bb) in BRAND_COLORS:
            if ((r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2) ** 0.5 <= dist:
                hits += 1
                break
    return hits / n if n else 0.0


def detect_sting(path: str, vdur: float) -> Dict:
    """Heuristic: is the first/last ~1s a branded card (>=50% brand-color pixels)?
    Heuristic only — the LLM/human judge confirms quality."""
    intro = brand_fraction(rgb_frame(path, min(1.0, vdur * 0.1)))
    outro = brand_fraction(rgb_frame(path, max(0.0, vdur - 1.0)))
    return {"has_intro": intro >= 0.5, "has_outro": outro >= 0.5,
            "intro_frac": round(intro, 2), "outro_frac": round(outro, 2)}


def _srt_seconds(s: str) -> float:
    hh, mm, rest = s.split(":")
    ss, ms = rest.split(",")
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def parse_captions(slug: str) -> Dict:
    """Parse sidecar tabs/<slug>/captions.srt for CPS / CPL / lines vs RUBRIC limits.
    Absent => {'present': False} (current state: no tab has captions yet)."""
    cap = os.path.join(TABS_DIR, slug, "captions.srt")
    if not os.path.exists(cap):
        return {"present": False}
    text = open(cap, encoding="utf-8").read()
    max_cps, max_cpl, max_lines = 0.0, 0, 0
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        tline = next((ln for ln in lines if "-->" in ln), None)
        if not tline:
            continue
        cue = lines[lines.index(tline) + 1:]
        if not cue:
            continue
        start, end = [t.strip() for t in tline.split("-->")]
        dur = max(0.001, _srt_seconds(end) - _srt_seconds(start))
        max_cps = max(max_cps, sum(len(ln) for ln in cue) / dur)
        max_cpl = max(max_cpl, max(len(ln) for ln in cue))
        max_lines = max(max_lines, len(cue))
    return {"present": True, "max_cps": round(max_cps, 1), "max_cpl": max_cpl,
            "max_lines": max_lines,
            "wcag_ok": max_cps <= CPS_MAX and max_cpl <= CPL_MAX and max_lines <= 2}


def extract_segment_frames(slug: str, vdur: float) -> List[Dict]:
    """One frame per narration segment, at the segment midpoint."""
    tc_path = os.path.join(TABS_DIR, slug, "timecodes.json")
    if not os.path.exists(tc_path):
        return []
    with open(tc_path) as f:
        segs = json.load(f)
    out_dir = os.path.join(QC_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    frames = []
    for i, seg in enumerate(segs, 1):
        t = float(seg.get("t", 0))
        d = float(seg.get("duration_s", 0))
        mid = t + (d / 2.0 if d > 0 else 2.0)
        if mid >= vdur:
            mid = max(0.0, vdur - 0.5)
        fp = os.path.join(out_dir, "seg_%02d.jpg" % i)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", str(mid),
             "-i", mp4_path(slug), "-frames:v", "1", "-vf", "scale=960:-1",
             fp, "-y"], capture_output=True)
        frames.append({"seg": i, "t": t, "at": round(mid, 1),
                       "frame": os.path.relpath(fp, DEMO_DIR),
                       "narration": seg.get("narration", "")})
    return frames


def main() -> int:
    slugs = [s for s in sys.argv[1:] if s in ALL_TABS] or ALL_TABS
    os.makedirs(QC_DIR, exist_ok=True)
    report: Dict[str, Dict] = {}

    for slug in slugs:
        path = mp4_path(slug)
        rec: Dict = {"slug": slug, "mp4": os.path.relpath(path, DEMO_DIR),
                     "gates": {}, "frames": []}
        if not os.path.exists(path):
            rec["gates"]["exists"] = False
            rec["verdict"] = "FAIL_MISSING"
            report[slug] = rec
            continue
        rec["gates"]["exists"] = True

        vdur = probe_duration(path, "v:0") or 0.0
        adur = probe_duration(path, "a:0")
        rec["video_s"] = round(vdur, 2)
        rec["audio_s"] = round(adur, 2) if adur is not None else None

        drift = abs(vdur - adur) if adur is not None else None
        rec["av_drift_s"] = round(drift, 2) if drift is not None else None
        rec["gates"]["av_sync"] = (drift is not None and drift <= AV_TOLERANCE_S)

        rec["scene_changes"] = scene_changes(path)  # info only
        intra = intra_motion(path, vdur)
        expects = script_expects_motion(slug)
        rec["intra_motion"] = intra
        rec["expects_motion"] = expects
        # Motion is required ONLY when the script asks the screen to move.
        rec["gates"]["motion"] = (not expects) or (intra >= MIN_INTRA)

        rec["_mid"] = gray_frame(path, vdur / 2.0, 32)  # for cross-tab dup check
        rec["frames"] = extract_segment_frames(slug, vdur)

        # Production-quality measures (report-only; feed RUBRIC.md Tier)
        rec["resolution"] = probe_resolution(path)
        words = script_word_count(slug)
        rec["script_words"] = words
        # WPM = true speaking rate, measured from the narration source (audio/full_narration.mp3)
        # NOT the final mp4 audio — once an intro/outro is added the mp4 audio includes silence,
        # which would understate WPM. Fall back to the mp4 audio only if the narration is absent.
        nar = os.path.join(TABS_DIR, slug, "audio", "full_narration.mp3")
        speak_s = (probe_duration(nar, "a:0") if os.path.exists(nar) else None) or adur
        rec["narration_s"] = round(speak_s, 2) if speak_s else None
        rec["wpm"] = round(words / (speak_s / 60.0), 1) if (speak_s and speak_s > 0) else None
        rec["loudness"] = measure_loudness(path)
        rec["sting"] = detect_sting(path, vdur)
        rec["captions"] = parse_captions(slug)
        report[slug] = rec

    # Pairwise distinctness via 32x32 pixel mean-abs diff. Catches "recorder
    # landed multiple tabs on the same screen" (diff ~0) without false-flagging
    # distinct pages that merely share the sidebar chrome (diff >= 1.87).
    mids = [(s, report[s]["_mid"]) for s in slugs
            if report[s].get("_mid") is not None]
    dup_of: Dict[str, List[str]] = {s: [] for s, _ in mids}
    for i in range(len(mids)):
        for j in range(i + 1, len(mids)):
            (sa, fa), (sb, fb) = mids[i], mids[j]
            if mean_abs_diff(fa, fb) < DUP_PIXDIFF:
                dup_of[sa].append(sb)
                dup_of[sb].append(sa)

    for slug in slugs:
        rec = report[slug]
        rec.pop("_mid", None)
        if rec.get("verdict") == "FAIL_MISSING":
            continue
        dups = dup_of.get(slug, [])
        rec["duplicate_of"] = dups
        rec["gates"]["distinct"] = (len(dups) == 0)
        g = rec["gates"]
        if not g["distinct"]:
            rec["verdict"] = "FAIL_DUPLICATE"
        elif not g["motion"]:
            rec["verdict"] = "FAIL_STATIC"
        elif not g["av_sync"]:
            rec["verdict"] = "WARN_AVDRIFT"
        else:
            rec["verdict"] = "PASS_GATES"  # gates clean -> hand to LLM judge

    out_path = os.path.join(QC_DIR, "report.json")
    with open(out_path, "w") as f:
        json.dump({"tabs": report, "config": {
            "av_tolerance_s": AV_TOLERANCE_S, "min_intra": MIN_INTRA,
            "dup_pixdiff": DUP_PIXDIFF, "wpm_min": WPM_MIN, "wpm_max": WPM_MAX,
            "lufs_target": LUFS_TARGET, "lufs_tol": LUFS_TOL, "tp_max": TP_MAX,
            "cps_max": CPS_MAX, "cpl_max": CPL_MAX}}, f, indent=2)

    # Human summary
    print("\nMission Control — Promo QC Gate")
    print("=" * 64)
    print("%-18s %-15s %6s %6s %5s  %s" %
          ("TAB", "VERDICT", "v(s)", "a(s)", "mot", "dup"))
    print("-" * 64)
    fails = 0
    for slug in slugs:
        r = report[slug]
        v = r.get("verdict", "?")
        if v.startswith("FAIL"):
            fails += 1
        mot = r.get("intra_motion", "-")
        if r.get("expects_motion") is False:
            mot = "%s~" % mot  # ~ = motion not required (PAUSE-only script)
        print("%-18s %-15s %6s %6s %5s  %s" % (
            slug, v, r.get("video_s", "-"), r.get("audio_s", "-"),
            mot, ",".join(r.get("duplicate_of", [])) or "-"))
    print("-" * 64)

    # Production-quality measures (feed RUBRIC.md tier; '!' = outside target, NOT a gate fail)
    print("\nProduction measures (feed RUBRIC.md tier — '!' = off-target, not a gate fail)")
    print("=" * 78)
    print("%-18s %-9s %6s %7s %6s %5s %5s %6s" %
          ("TAB", "res", "wpm", "LUFS", "TP", "intro", "outro", "caps"))
    print("-" * 78)
    for slug in slugs:
        r = report[slug]
        if r.get("verdict") == "FAIL_MISSING":
            continue
        ld = r.get("loudness") or {}
        wpm = r.get("wpm")
        wpm_s = "-" if wpm is None else ("%.0f%s" % (wpm, "" if WPM_MIN <= wpm <= WPM_MAX else "!"))
        lufs = ld.get("integrated_lufs")
        lufs_s = "-" if lufs is None else ("%.1f%s" % (lufs, "" if abs(lufs - LUFS_TARGET) <= LUFS_TOL else "!"))
        tp = ld.get("true_peak_dbtp")
        tp_s = "-" if tp is None else ("%.1f%s" % (tp, "" if tp <= TP_MAX else "!"))
        st = r.get("sting") or {}
        caps = r.get("captions") or {}
        caps_s = "none" if not caps.get("present") else ("ok" if caps.get("wcag_ok") else "BAD!")
        print("%-18s %-9s %6s %7s %6s %5s %5s %6s" % (
            slug, r.get("resolution", "-"), wpm_s, lufs_s, tp_s,
            "Y" if st.get("has_intro") else "-",
            "Y" if st.get("has_outro") else "-", caps_s))
    print("-" * 78)
    print("  targets: wpm %g-%g, LUFS %g±%g, TP<=%g dBTP, caps<=%g CPS/<=%d CPL. See RUBRIC.md.\n"
          % (WPM_MIN, WPM_MAX, LUFS_TARGET, LUFS_TOL, TP_MAX, CPS_MAX, CPL_MAX))

    print("Frames + report.json -> %s" % os.path.relpath(QC_DIR, DEMO_DIR))
    print("%d FAIL, %d total. LLM judge should read PASS_GATES/WARN tabs only.\n"
          % (fails, len(slugs)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

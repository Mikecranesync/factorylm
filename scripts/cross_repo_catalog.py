"""
MoP2 Cross-Repo Duplicate Analyst
Scans all 6 Tier-1 repo discovery JSONs to find:
  - Exact cross-repo duplicates (same AST fingerprint, different repos)
  - Near-name cross-repo matches (same name+kind, different implementations)
Produces:
  - output/cross-repo-catalog.json
  - output/cross-repo-catalog.md
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE = Path("C:/Users/hharp/OneDrive/Desktop/FactoryLM")
OUTPUT = BASE / "output"

REPO_FILES = {
    "rivet-pro":            OUTPUT / "rivet-pro-discovery.json",
    "agent-factory":        OUTPUT / "agent-factory-discovery.json",
    "factorylm":            OUTPUT / "factorylm-discovery.json",
    "openclaw":             OUTPUT / "openclaw-discovery.json",
    "master-of-puppets":    OUTPUT / "master-of-puppets-discovery.json",
    "remoteme-jarvis-node": OUTPUT / "remoteme-jarvis-node-discovery.json",
}

# Noise filters
SKIP_DUNDERS = {
    "__init__", "__str__", "__repr__", "__eq__", "__hash__",
    "__lt__", "__le__", "__gt__", "__ge__", "__ne__",
    "__len__", "__contains__", "__iter__", "__next__",
    "__enter__", "__exit__", "__call__", "__del__",
    "__bool__", "__int__", "__float__", "__bytes__",
    "__getitem__", "__setitem__", "__delitem__",
    "__add__", "__sub__", "__mul__", "__truediv__",
    "__and__", "__or__", "__xor__", "__mod__",
    "__getattr__", "__setattr__", "__delattr__",
}

# Fingerprints that correspond to trivial bodies (pass, return None, etc.)
# We detect these by fingerprint being shared among 50+ entries — trivial stubs
TRIVIAL_FINGERPRINT_THRESHOLD = 50  # if a fingerprint appears this many times total it's likely trivial

TEST_PATH_PATTERNS = re.compile(r'(test_|/tests/|\\tests\\|/test/|\\test\\|_test\.py)', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Load & normalize
# ---------------------------------------------------------------------------

def load_all_repos():
    all_symbols = []
    repo_meta = {}
    for repo, path in REPO_FILES.items():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("meta", {})
        repo_meta[repo] = {
            "repo": repo,
            "scanned_at": meta.get("scanned_at", ""),
            "total_symbols": len(data.get("symbols", [])),
            "file": str(path),
        }
        for sym in data.get("symbols", []):
            sym["repo"] = repo
            all_symbols.append(sym)
    return all_symbols, repo_meta


def should_skip(sym: dict, trivial_fps: set) -> bool:
    name = sym.get("name", "")
    fp   = sym.get("fingerprint", "")
    file_path = sym.get("file", "")

    # Skip dunder methods
    if name in SKIP_DUNDERS:
        return True

    # Skip test files
    if TEST_PATH_PATTERNS.search(file_path):
        return True

    # Skip trivial fingerprints (pass / return None stubs)
    if fp in trivial_fps:
        return True

    return False


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def find_trivial_fingerprints(all_symbols):
    """Fingerprints that appear so frequently they must be trivial stubs."""
    fp_counts = defaultdict(int)
    for sym in all_symbols:
        fp = sym.get("fingerprint", "")
        if fp:
            fp_counts[fp] += 1
    return {fp for fp, count in fp_counts.items() if count >= TRIVIAL_FINGERPRINT_THRESHOLD}


def find_exact_cross_repo_dupes(filtered_symbols):
    """Group by fingerprint; keep groups that span multiple repos."""
    fp_groups = defaultdict(list)
    for sym in filtered_symbols:
        fp = sym.get("fingerprint", "")
        if fp:
            fp_groups[fp].append(sym)

    cross_repo_exact = []
    for fp, syms in fp_groups.items():
        repos_involved = set(s["repo"] for s in syms)
        if len(repos_involved) < 2:
            continue
        cross_repo_exact.append({
            "fingerprint": fp,
            "repos_count": len(repos_involved),
            "occurrences": len(syms),
            "repos": sorted(repos_involved),
            # Collect unique names (usually identical, but capture all)
            "names": sorted(set(s["name"] for s in syms)),
            "kinds": sorted(set(s["kind"] for s in syms)),
            "signature": syms[0].get("signature") or "",
            "locations": [
                {
                    "repo":      s["repo"],
                    "file":      s["file"],
                    "line":      s.get("line", 0),
                    "name":      s["name"],
                    "kind":      s["kind"],
                    "signature": s.get("signature") or "",
                }
                for s in syms
            ],
        })

    # Sort: repos_count desc, occurrences desc
    cross_repo_exact.sort(key=lambda g: (-g["repos_count"], -g["occurrences"]))
    return cross_repo_exact


def find_near_name_cross_repo(filtered_symbols, min_repos=2):
    """Group by (name, kind); keep groups that span multiple repos."""
    nk_groups = defaultdict(list)
    for sym in filtered_symbols:
        key = (sym["name"], sym.get("kind", ""))
        nk_groups[key].append(sym)

    near_name = []
    for (name, kind), syms in nk_groups.items():
        repos_involved = set(s["repo"] for s in syms)
        if len(repos_involved) < min_repos:
            continue
        # Gather unique signatures per repo (normalize None -> "")
        repo_sigs = defaultdict(set)
        for s in syms:
            sig = s.get("signature") or ""
            repo_sigs[s["repo"]].add(sig)

        # Check if fingerprints differ (i.e. not already an exact dupe)
        fps = set(s.get("fingerprint", "") for s in syms)
        is_exact = len(fps) == 1

        near_name.append({
            "name":            name,
            "kind":            kind,
            "repos_count":     len(repos_involved),
            "occurrences":     len(syms),
            "repos":           sorted(repos_involved),
            "is_exact_dupe":   is_exact,
            "repo_signatures": {repo: sorted(sigs) for repo, sigs in repo_sigs.items()},
            "locations": [
                {
                    "repo":        s["repo"],
                    "file":        s["file"],
                    "line":        s.get("line", 0),
                    "signature":   s.get("signature", ""),
                    "fingerprint": s.get("fingerprint", ""),
                }
                for s in syms
            ],
        })

    near_name.sort(key=lambda g: (-g["repos_count"], -g["occurrences"]))
    return near_name


def build_recommendations(exact_dupes, near_name_matches):
    """Produce top-10 refactoring recommendations ranked by impact."""
    recs = []
    seen_symbols = set()

    # Near-name matches spanning 4+ repos get CRITICAL priority (most blast radius)
    for group in near_name_matches:
        if group["is_exact_dupe"]:
            continue
        if group["repos_count"] < 4:
            continue
        key = (group["name"], group["kind"])
        if key in seen_symbols:
            continue
        seen_symbols.add(key)
        repos = ", ".join(group["repos"])
        # Pick the most common signature as the canonical one
        all_sigs = []
        for sigs in group["repo_signatures"].values():
            all_sigs.extend(sigs)
        canonical_sig = max(set(all_sigs), key=all_sigs.count) if all_sigs else ""
        recs.append({
            "priority": "CRITICAL",
            "type": "NEAR_NAME_ALL_REPOS",
            "symbol": group["name"],
            "kind": group["kind"],
            "repos_count": group["repos_count"],
            "repos": repos,
            "occurrences": group["occurrences"],
            "suggested_signature": canonical_sig,
            "action": (
                f"Define a shared `{group['name']}` ({group['kind']}) interface/base in "
                f"`factorylm-core`. Found in {group['repos_count']} repos ({repos}). "
                f"With {group['occurrences']} implementations, standardizing this contract "
                f"will reduce cross-repo drift immediately."
            ),
        })

    # From exact dupes: HIGH priority — identical code copied verbatim
    for group in exact_dupes:
        names = "/".join(group["names"])
        key = (names, "/".join(group["kinds"]))
        if key in seen_symbols:
            continue
        seen_symbols.add(key)
        repos = ", ".join(group["repos"])
        recs.append({
            "priority": "HIGH",
            "type": "EXACT_DUPLICATE",
            "symbol": names,
            "kind": "/".join(group["kinds"]),
            "repos_count": group["repos_count"],
            "repos": repos,
            "occurrences": group["occurrences"],
            "suggested_signature": group["signature"],
            "action": (
                f"Extract `{names}` into a shared library (appears identically in "
                f"{group['repos_count']} repos: {repos}). "
                f"Single source of truth eliminates {group['occurrences'] - 1} redundant copies."
            ),
        })

    # Near-name (non-exact, 3+ repos): MEDIUM — different implementations, same contract
    for group in near_name_matches:
        if group["is_exact_dupe"]:
            continue
        if group["repos_count"] < 3 or group["repos_count"] >= 4:
            continue
        key = (group["name"], group["kind"])
        if key in seen_symbols:
            continue
        seen_symbols.add(key)
        repos = ", ".join(group["repos"])
        recs.append({
            "priority": "MEDIUM",
            "type": "NEAR_NAME_CROSS_REPO",
            "symbol": group["name"],
            "kind": group["kind"],
            "repos_count": group["repos_count"],
            "repos": repos,
            "occurrences": group["occurrences"],
            "suggested_signature": "",
            "action": (
                f"Consolidate `{group['name']}` ({group['kind']}) across "
                f"{group['repos_count']} repos ({repos}). Implementations differ — "
                f"review signatures and unify into shared adapter or abstract base class."
            ),
        })

    # Sort: CRITICAL > HIGH > MEDIUM, then repos_count desc, occurrences desc
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    recs.sort(key=lambda r: (priority_order.get(r["priority"], 9), -r["repos_count"], -r["occurrences"]))
    return recs[:10]


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _loc_str(loc):
    return f"`{loc['repo']}`:`{loc['file']}`:{loc['line']}"


def render_markdown(
    repo_meta,
    all_symbols,
    filtered_symbols,
    trivial_fps,
    exact_dupes,
    near_name_matches,
    recommendations,
):
    lines = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines.append("# MoP2 Cross-Repo Duplicate Catalog")
    lines.append(f"_Generated: {now}_\n")

    # --- Section 1: Summary ---
    lines.append("## 1. Summary\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Repos scanned | {len(REPO_FILES)} |")
    lines.append(f"| Total symbols loaded | {len(all_symbols):,} |")
    lines.append(f"| Symbols after noise filter | {len(filtered_symbols):,} |")
    lines.append(f"| Trivial fingerprints skipped | {len(trivial_fps)} |")
    lines.append(f"| **Exact cross-repo duplicate groups** | **{len(exact_dupes)}** |")
    lines.append(f"| Near-name cross-repo groups (2+ repos) | {len(near_name_matches)} |")
    near3 = sum(1 for g in near_name_matches if g['repos_count'] >= 3)
    lines.append(f"| Near-name groups spanning 3+ repos | {near3} |")
    lines.append("")

    lines.append("### Repo Breakdown\n")
    lines.append("| Repo | Symbols |")
    lines.append("|------|---------|")
    for repo, meta in repo_meta.items():
        lines.append(f"| {repo} | {meta['total_symbols']:,} |")
    lines.append("")

    # --- Section 2: Exact Cross-Repo Duplicates ---
    lines.append("## 2. Exact Cross-Repo Duplicates\n")
    lines.append(
        "_Same AST fingerprint appearing in multiple repos. "
        "These are the highest-confidence copy-paste candidates._\n"
    )

    if not exact_dupes:
        lines.append("_No exact cross-repo duplicates found after noise filtering._\n")
    else:
        for i, group in enumerate(exact_dupes, 1):
            name_display = " / ".join(group["names"])
            kind_display = " / ".join(group["kinds"])
            lines.append(f"### {i}. `{name_display}` ({kind_display})")
            lines.append(f"**Repos:** {group['repos_count']} — {', '.join(group['repos'])}")
            lines.append(f"**Occurrences:** {group['occurrences']}")
            lines.append(f"**Fingerprint:** `{group['fingerprint'][:16]}...`")
            if group["signature"]:
                lines.append(f"**Signature:** `{group['signature']}`")
            lines.append("")
            lines.append("| Repo | File | Line |")
            lines.append("|------|------|------|")
            for loc in group["locations"]:
                lines.append(f"| `{loc['repo']}` | `{loc['file']}` | {loc['line']} |")
            lines.append("")

    # --- Section 3: Near-Name Cross-Repo Matches (3+ repos) ---
    lines.append("## 3. Near-Name Cross-Repo Matches (3+ Repos)\n")
    lines.append(
        "_Same name + kind across 3+ repos, possibly different implementations. "
        "Consolidation candidates even when logic varies._\n"
    )

    three_plus = [g for g in near_name_matches if g["repos_count"] >= 3 and not g["is_exact_dupe"]]
    if not three_plus:
        lines.append("_No near-name groups spanning 3+ repos found (after excluding exact dupes)._\n")
    else:
        for i, group in enumerate(three_plus, 1):
            lines.append(f"### {i}. `{group['name']}` ({group['kind']})")
            lines.append(f"**Repos:** {group['repos_count']} — {', '.join(group['repos'])}")
            lines.append(f"**Occurrences:** {group['occurrences']}")
            lines.append("")
            lines.append("**Signatures by repo:**")
            for repo, sigs in group["repo_signatures"].items():
                for sig in sigs:
                    lines.append(f"- `{repo}`: `{sig}`")
            lines.append("")
            lines.append("| Repo | File | Line |")
            lines.append("|------|------|------|")
            for loc in group["locations"]:
                lines.append(f"| `{loc['repo']}` | `{loc['file']}` | {loc['line']} |")
            lines.append("")

    # Also show 2-repo near-name for completeness (collapsed)
    two_only = [g for g in near_name_matches if g["repos_count"] == 2 and not g["is_exact_dupe"]]
    if two_only:
        lines.append("### Near-Name Matches (2 Repos Only)\n")
        lines.append("| Symbol | Kind | Repos | Occurrences |")
        lines.append("|--------|------|-------|-------------|")
        for group in two_only[:40]:
            repos_str = ", ".join(group["repos"])
            lines.append(f"| `{group['name']}` | {group['kind']} | {repos_str} | {group['occurrences']} |")
        if len(two_only) > 40:
            lines.append(f"\n_...and {len(two_only) - 40} more two-repo matches._")
        lines.append("")

    # --- Section 4: Recommendations ---
    lines.append("## 4. Refactoring Recommendations\n")
    lines.append("_Top 10 actionable consolidation targets, ranked by impact._\n")

    priority_emoji = {"CRITICAL": "[CRITICAL]", "HIGH": "[HIGH]", "MEDIUM": "[MEDIUM]", "LOW": "[LOW]"}
    for i, rec in enumerate(recommendations, 1):
        badge = priority_emoji.get(rec["priority"], rec["priority"])
        lines.append(f"### {i}. {badge} `{rec['symbol']}` ({rec['kind']})")
        lines.append(f"**Priority:** {rec['priority']}  **Type:** {rec['type']}")
        lines.append(f"**Repos affected:** {rec['repos_count']} — {rec['repos']}")
        lines.append(f"**Total occurrences:** {rec['occurrences']}")
        sig = rec.get("suggested_signature", "")
        if sig:
            lines.append(f"**Suggested canonical signature:** `{sig}`")
        lines.append(f"**Action:** {rec['action']}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading all repo discovery files...")
    all_symbols, repo_meta = load_all_repos()
    print(f"  Loaded {len(all_symbols):,} total symbols from {len(REPO_FILES)} repos")

    print("Identifying trivial fingerprints...")
    trivial_fps = find_trivial_fingerprints(all_symbols)
    print(f"  Trivial fingerprints to skip: {len(trivial_fps)}")

    print("Applying noise filters...")
    filtered = [s for s in all_symbols if not should_skip(s, trivial_fps)]
    print(f"  Filtered symbols: {len(filtered):,} (removed {len(all_symbols) - len(filtered):,})")

    print("Finding exact cross-repo duplicates...")
    exact_dupes = find_exact_cross_repo_dupes(filtered)
    print(f"  Exact cross-repo duplicate groups: {len(exact_dupes)}")

    print("Finding near-name cross-repo matches...")
    near_name_matches = find_near_name_cross_repo(filtered, min_repos=2)
    print(f"  Near-name cross-repo groups (2+ repos): {len(near_name_matches)}")
    print(f"  Near-name groups spanning 3+ repos: {sum(1 for g in near_name_matches if g['repos_count'] >= 3)}")

    print("Building recommendations...")
    recommendations = build_recommendations(exact_dupes, near_name_matches)

    # --- Save JSON ---
    json_out = OUTPUT / "cross-repo-catalog.json"
    result = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat(),
            "repos_scanned": list(REPO_FILES.keys()),
            "total_symbols_loaded": len(all_symbols),
            "filtered_symbols": len(filtered),
            "trivial_fingerprints_skipped": len(trivial_fps),
        },
        "summary": {
            "exact_cross_repo_groups": len(exact_dupes),
            "near_name_groups_2plus": len(near_name_matches),
            "near_name_groups_3plus": sum(1 for g in near_name_matches if g["repos_count"] >= 3),
        },
        "repo_meta": repo_meta,
        "exact_cross_repo_duplicates": exact_dupes,
        "near_name_cross_repo_matches": near_name_matches,
        "recommendations": recommendations,
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON saved: {json_out}")

    # --- Save Markdown ---
    md_out = OUTPUT / "cross-repo-catalog.md"
    md_content = render_markdown(
        repo_meta, all_symbols, filtered, trivial_fps,
        exact_dupes, near_name_matches, recommendations
    )
    with open(md_out, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  Markdown saved: {md_out}")

    # --- Quick console summary ---
    print("\n" + "="*60)
    print("CROSS-REPO CATALOG SUMMARY")
    print("="*60)
    print(f"Total symbols analyzed : {len(filtered):,}")
    print(f"Exact duplicate groups : {len(exact_dupes)}")
    print(f"Near-name groups       : {len(near_name_matches)}")
    print(f"Top recommendations    : {len(recommendations)}")
    print()
    if exact_dupes:
        print("TOP EXACT DUPLICATES:")
        for g in exact_dupes[:5]:
            names = " / ".join(g["names"])
            repos = ", ".join(g["repos"])
            print(f"  [{g['repos_count']} repos] {names} ({'/'.join(g['kinds'])}) -> {repos}")
    print()
    if recommendations:
        print("TOP RECOMMENDATIONS:")
        for r in recommendations[:5]:
            print(f"  [{r['priority']}] {r['symbol']} ({r['kind']}) - {r['repos_count']} repos")
    print("="*60)


if __name__ == "__main__":
    main()

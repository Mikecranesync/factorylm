#!/usr/bin/env python3
"""
Jesus H Christ - Repo Resurrector

Scans GitHub repos for buried treasure: abandoned features, 
patterns, and commercial opportunities.

Usage:
    python resurrector.py scan-all [--org <org>]
    python resurrector.py analyze <repo-name>
    python resurrector.py report <repo-name>
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path

def get_repos(org: str = "mikecranesync") -> list:
    """Fetch all repos for an org/user."""
    result = subprocess.run(
        ["gh", "repo", "list", org, "--limit", "100", "--json", "name,description,pushedAt,isArchived"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error fetching repos: {result.stderr}")
        return []
    return json.loads(result.stdout)

def analyze_repo(org: str, repo: str) -> dict:
    """Analyze a single repo for resurrection potential."""
    full_name = f"{org}/{repo}"
    
    # Get repo details
    result = subprocess.run(
        ["gh", "repo", "view", full_name, "--json", 
         "name,description,pushedAt,isArchived,languages,issues,pullRequests"],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        return {"error": result.stderr}
    
    data = json.loads(result.stdout)
    
    # Search for valuable patterns
    patterns = {
        "has_readme": False,
        "has_tests": False,
        "has_ci": False,
        "languages": data.get("languages", []),
        "last_push": data.get("pushedAt", "unknown"),
        "open_issues": data.get("issues", {}).get("totalCount", 0),
        "open_prs": data.get("pullRequests", {}).get("totalCount", 0),
    }
    
    return {
        "repo": full_name,
        "description": data.get("description", ""),
        "archived": data.get("isArchived", False),
        "patterns": patterns,
        "resurrection_score": calculate_score(patterns),
    }

def calculate_score(patterns: dict) -> int:
    """Calculate resurrection worthiness score (0-100)."""
    score = 50  # Base score
    
    # Penalize very old repos
    # Boost repos with tests, CI
    if patterns.get("has_tests"):
        score += 15
    if patterns.get("has_ci"):
        score += 10
    
    # Boost repos with activity
    if patterns.get("open_issues", 0) > 0:
        score += 5
    if patterns.get("open_prs", 0) > 0:
        score += 10
        
    return min(100, max(0, score))

def scan_all(org: str = "mikecranesync"):
    """Scan all repos and generate report."""
    print(f"🔍 Scanning all repos for {org}...")
    repos = get_repos(org)
    
    results = []
    for repo in repos:
        name = repo["name"]
        print(f"  Analyzing {name}...")
        analysis = analyze_repo(org, name)
        results.append(analysis)
    
    # Sort by resurrection score
    results.sort(key=lambda x: x.get("resurrection_score", 0), reverse=True)
    
    # Save report
    report_path = Path(__file__).parent.parent / "reports" / f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Scan complete! Report saved to {report_path}")
    print(f"\n🏆 Top 5 Resurrection Candidates:")
    for r in results[:5]:
        print(f"  - {r['repo']}: {r.get('resurrection_score', 0)}/100")
    
    return results

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1]
    
    if command == "scan-all":
        org = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--org" else "mikecranesync"
        scan_all(org)
    elif command == "analyze" and len(sys.argv) > 2:
        result = analyze_repo("mikecranesync", sys.argv[2])
        print(json.dumps(result, indent=2))
    else:
        print(__doc__)

if __name__ == "__main__":
    main()

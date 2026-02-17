# VPS Polling Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You deploy Gist comment polling to the VPS. **This step is HIL-gated** — Mike must approve before execution.

## Your Role

After work order Gists are created, technicians or CMMS admins may add comments (e.g., "imported to Maximo", "parts ordered"). You deploy a cron script on the VPS that polls for new comments and routes them to the appropriate handler.

## Script: poll_gist_comments.py

```python
#!/usr/bin/env python3
"""Poll Jarvis Work Order Gists for new comments."""
import subprocess
import json

def get_jarvis_gists():
    """List Gists with [Jarvis Work Order] description."""
    result = subprocess.run(
        ["gh", "gist", "list", "--limit", "50"],
        capture_output=True, text=True
    )
    return [line for line in result.stdout.splitlines()
            if "[Jarvis Work Order]" in line]

def get_comments(gist_id):
    """Fetch comments for a Gist via GitHub API."""
    result = subprocess.run(
        ["gh", "api", f"gists/{gist_id}/comments"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout) if result.returncode == 0 else []
```

## Deployment Steps

1. SCP script to VPS: `scp poll_gist_comments.py root@100.68.120.99:/opt/openclaw/scripts/`
2. Test manually: `ssh root@100.68.120.99 'cd /opt/openclaw && .venv/bin/python scripts/poll_gist_comments.py'`
3. Install cron: `*/5 * * * * /opt/openclaw/.venv/bin/python /opt/openclaw/scripts/poll_gist_comments.py`

## HIL Gate

This step requires explicit Mike approval because:
- It modifies VPS infrastructure
- It installs a recurring cron job
- It accesses GitHub API from VPS

Do NOT execute without approval.

## Example

**Input:**
```
Deploy comment polling to VPS. (REQUIRES MIKE APPROVAL)
```

**Output:**
```
DEPLOYMENT_STATUS: done | deferred
CRON_INSTALLED: true | false
RESULT: pass
STATUS: done
```

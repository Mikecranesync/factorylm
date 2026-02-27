# /gist — Gist Polling & Interaction

Trigger: `/gist`, `check gist`, `poll gist`, `gist comments`, `watch gist`

## Operations

### `/gist` or `/gist poll`
Run one poll cycle — check all WO gists and watched gists for new comments.

```bash
cd C:/Users/hharp/Desktop/factorylm-monorepo
GIST_WATCH_IDS="${GIST_WATCH_IDS:-}" python -c "
from openclaw.gist_poller import poll_all_gists
notifications = poll_all_gists()
if not notifications:
    print('No new comments found.')
else:
    for n in notifications:
        print(f\"[{n['type'].upper()}] {n['wo_id']} — {n.get('field', '')} {n.get('value', n.get('body', '')[:80])} (by {n['user']})\")
"
```

### `/gist comments <id>`
Show all comments on a specific gist.

```bash
"C:/Program Files/GitHub CLI/gh.exe" api "/gists/<id>/comments" --jq '.[] | "[\(.user.login)] \(.created_at): \(.body)"'
```

### `/gist comment <id> <text>`
Post a comment to a gist.

```bash
"C:/Program Files/GitHub CLI/gh.exe" api -X POST "/gists/<id>/comments" -f body="<text>"
```

### `/gist watch <id>`
Explain how to add a gist to the watch list. The `GIST_WATCH_IDS` env var accepts comma-separated gist IDs:

```
export GIST_WATCH_IDS="id1,id2,id3"
```

To persist, add it to `.env` or the service config.

### `/gist list`
Show watched gists and recent WO gists.

```bash
echo "=== WO Gists ==="
"C:/Program Files/GitHub CLI/gh.exe" gist list --limit 20 | grep "Jarvis Work Order"

echo ""
echo "=== Watched Gists (GIST_WATCH_IDS) ==="
```
Then for each ID in `GIST_WATCH_IDS`, fetch metadata via:
```bash
"C:/Program Files/GitHub CLI/gh.exe" api "/gists/<id>" --jq '{id: .id, description: .description, updated: .updated_at, files: [.files | keys[]]}'
```

## Key Context
- The gh CLI on this Windows machine is at `C:/Program Files/GitHub CLI/gh.exe` (not in bash PATH)
- The Conveyor of Destiny gist is `c5c226f17c8499204636b85d7bbeb7e0`
- WO gists follow the `[Jarvis Work Order] WO-YYYY-MMDD-NNN` naming convention
- `GIST_WATCH_IDS` env var adds arbitrary gists to the poll cycle

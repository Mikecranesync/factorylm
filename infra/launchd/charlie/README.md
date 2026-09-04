# CHARLIE LaunchAgents (tracked copies)

Source of truth for the user LaunchAgents that run on CHARLIE
(`CharlieNodes-Mac-mini`, user `charlienode`). The live files are in
`~/Library/LaunchAgents/`; this directory is what they should match.

| Label | Program | Schedule | Tracked here |
|---|---|---|---|
| `com.factorylm.health-monitor` | `scripts/health-check.sh` | every 300 s | yes |
| `com.factorylm.brain-ingest` | uvicorn `services.brain.ingest:app` :8500 | KeepAlive | yes |
| `com.factorylm.brain-mcp` | `services.mcp.brain_server` :8501 (streamable-http) | KeepAlive | yes |
| `com.factorylm.vastai-tunnel` | autossh to a rented vast.ai box | KeepAlive | **unloaded 2026-09-02** (#222) |
| `com.mira.slack-agent` | `slack run` in `mira-bots/mira-maintenance-agent` | KeepAlive | **unloaded 2026-09-02** (#222) |

## The runtime checkout (why nothing here runs from `~/factorylm`)

All three tracked agents run from **`~/.factorylm/runtime/factorylm`**, a
shallow detached clone that only `scripts/deploy-charlie-runtime.sh` moves.
`~/factorylm` is a developer working tree: several Claude/Codex sessions switch
its branch, and one half-resolved merge there put brain-mcp into a 37k-respawn
loop that nothing noticed (#220, #223). A service that must run unattended
cannot depend on which branch a human last left a checkout on.

## Install / update

```bash
bash scripts/deploy-charlie-runtime.sh          # main
bash scripts/deploy-charlie-runtime.sh v1.2.3   # or any ref
```

That clones or fast-forwards the runtime, installs brain deps into
`~/brain-venv`, copies the plists from this directory *as they exist at the
deployed ref*, restarts the three agents, and verifies each from the outside
(ingest `/health`, an MCP `initialize` on :8501, the working directory launchd
reports, the monitor's exit code). Every deploy appends `<time> <ref> <sha>` to
`~/.factorylm/runtime/DEPLOYED`. Roll back by deploying the previous sha.

The health monitor writes one status line per run to
`/tmp/factorylm-health.log` and appends to `/tmp/factorylm-health.alerts`
only when the failure set changes. To also post alerts to Discord/Slack, put a
single webhook URL in `~/.factorylm/health/webhook_url` (mode 600). It is read
at runtime and never committed. State (per-agent `runs` counters, last failure
set) lives in `~/.factorylm/health/`; delete it to reset crash-loop baselines.

Secrets are not in these plists: the brain agents get theirs from
`doppler run -p factorylm -c dev` at start.

## Why two agents were unloaded (#222)

Both were in permanent `KeepAlive` restart loops writing unbounded stderr to
`/tmp` (≈160k lines combined) — 52k and 17k spawns respectively:

- **vastai-tunnel** — no vast.ai instance is rented, so `ssh6.vast.ai:26566`
  refuses every connection. Load it on demand as part of renting a GPU, not at
  login.
- **slack-agent** — `mira-bots/mira-maintenance-agent` is an untracked May-2026
  experiment with no `.slack/hooks.json`; the Slack CLI rejects it as an
  invalid project on every start. The production Slack adapter is
  `mira-bots/slack/bot.py` on the VPS, not this.

The plists were moved to `~/Library/LaunchAgents.disabled/` rather than
deleted, so `mv` them back and `launchctl bootstrap` to re-enable. The
health monitor's check 2 would flag either of them within five minutes if
they came back looping.

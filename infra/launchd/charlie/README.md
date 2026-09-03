# CHARLIE LaunchAgents (tracked copies)

Source of truth for the user LaunchAgents that run on CHARLIE
(`CharlieNodes-Mac-mini`, user `charlienode`). The live files are in
`~/Library/LaunchAgents/`; this directory is what they should match.

| Label | Program | Schedule | Tracked here |
|---|---|---|---|
| `com.factorylm.health-monitor` | `scripts/health-check.sh` | every 300 s | yes |
| `com.factorylm.brain-ingest` | uvicorn `services.brain.ingest:app` :8500 | KeepAlive | no — written by `scripts/deploy-charlie-brain.sh` |
| `com.factorylm.brain-mcp` | `services.mcp.brain_server` :8501 (streamable-http) | KeepAlive | no — carries a Doppler-injected env; see #223 |
| `com.factorylm.vastai-tunnel` | autossh to a rented vast.ai box | KeepAlive | **unloaded 2026-09-02** (#222) |
| `com.mira.slack-agent` | `slack run` in `mira-bots/mira-maintenance-agent` | KeepAlive | **unloaded 2026-09-02** (#222) |

## Install / update the health monitor

The agent runs a **copy** of the script from `~/.factorylm/bin/`, not the
checkout, so it keeps working whatever branch `~/factorylm` happens to be on
(brain-mcp runs straight from the checkout, which is how a half-resolved merge
on one branch took it down — #220). Re-run this after changing the script.

```bash
mkdir -p ~/.factorylm/bin
cp scripts/health-check.sh ~/.factorylm/bin/health-check.sh
cp infra/launchd/charlie/com.factorylm.health-monitor.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.factorylm.health-monitor 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.factorylm.health-monitor.plist
launchctl kickstart -k gui/$(id -u)/com.factorylm.health-monitor
tail -3 /tmp/factorylm-health.log
```

The script writes one status line per run to `/tmp/factorylm-health.log` and
appends to `/tmp/factorylm-health.alerts` only when the failure set changes.
To also post those alerts to Discord/Slack, put a single webhook URL in
`~/.factorylm/health/webhook_url` (mode 600). It is read at runtime and is
never committed.

State (per-agent `runs` counters, last failure set) lives in
`~/.factorylm/health/`. Delete it to reset crash-loop baselines.

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

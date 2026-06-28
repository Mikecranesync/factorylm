# Mission Control — Full Feature Walkthrough Script

Format: `[HH:MM:SS] [ACTION] Narration text`
Duration per segment = next timestamp minus current timestamp.

Actions:
- `NAV:/route` — navigate to route
- `CLICK:selector` — click element matching selector
- `FILL:selector:value` — type into input
- `HOVER:selector` — hover over element
- `SCROLL:+N` — scroll down N pixels
- `SCROLL:-N` — scroll up N pixels
- `PAUSE` — no UI interaction, just hold

---

[00:00:00] [PAUSE] Welcome to Mission Control — FactoryLM's central command interface for your industrial automation cluster. Here's everything it can do.

[00:00:10] [NAV:/] Chat Relay is the core of Mission Control. It routes natural language prompts directly to Claude Code running on any Jarvis node in your cluster.

[00:00:18] [CLICK:select] This dropdown lets you target a specific machine — Alpha, Bravo, Charlie, or the VPS.

[00:00:24] [CLICK:input[type="text"]] Set the working directory so Claude Code operates in the right project context.

[00:00:29] [CLICK:select:nth-of-type(2)] Choose how long to wait for a response: one, three, five, or ten minutes.

[00:00:34] [FILL:textarea:Tell me what tests are failing in this repo] Type your prompt in this field — exactly what you'd type into Claude Code at the terminal. Control-Enter dispatches it.

[00:00:41] [PAUSE] Results appear in the message history below — expandable cards with stdout, stderr, exit code, and elapsed time.

[00:00:48] [SCROLL:+300] The status indicator at the top right shows which Jarvis nodes are reachable in real time.

[00:00:54] [NAV:/dashboard] The Dashboard is your live system snapshot — everything happening across the cluster on a single screen.

[00:01:02] [PAUSE] Four stat cards show current workflow count, active worker pool size, agent count, and Ralph's live status.

[00:01:09] [SCROLL:+400] The Human-in-the-Loop queue is where autonomous actions wait before executing. Each item is color-coded by risk — green for safe, yellow for caution, red for destructive.

[00:01:19] [PAUSE] Action types include deployments, git pushes, force-pushes, deletes, PLC writes, and repo resurrections. You approve or reject each one individually.

[00:01:27] [SCROLL:+400] The right column shows every Jarvis node in the cluster and its current health status.

[00:01:33] [SCROLL:+300] Below that, PLC collector status — S7, Allen-Bradley, and Modbus — shows whether live industrial telemetry is flowing.

[00:01:40] [SCROLL:+300] Quick Actions let you fire common shell commands with one click. Each is tagged with a risk level so you know what you're touching before you hit it.

[00:01:48] [NAV:/terminal] The Terminal tab gives you a direct remote shell into any Jarvis node without leaving the browser.

[00:01:55] [CLICK:select] Pick your target node from the dropdown, then set a command timeout from ten seconds to two minutes.

[00:02:00] [FILL:input[placeholder*="command" i]:hostname && uptime] Results appear with stdout in green and stderr in red, plus exit code and elapsed time. Arrow keys navigate your command history just like a real terminal.

[00:02:08] [SCROLL:+500] The same Quick Actions grid is here for one-click access to preset commands.

[00:02:13] [NAV:/workers] Worker Swarm manages the Celery task pool that powers every autonomous operation in the cluster.

[00:02:20] [SCROLL:+400] Workers are organized into eight categories: Core Operations, Knowledge, Analysis, Integration, PLC, Content, Development, and Security — twenty-five workers total.

[00:02:28] [SCROLL:+400] Each card shows the worker's formatted name and live status — active, running, idle, or offline.

[00:02:34] [SCROLL:+400] The plus and minus buttons grow or shrink the pool for any worker by one instance. Scale up under load, scale down to save resources.

[00:02:41] [NAV:/ralph] Ralph is Mission Control's autonomous code evolution engine — it iterates on a codebase continuously, proposing and applying improvements in a loop.

[00:02:48] [PAUSE] The status badge tells you whether Ralph is running, paused, stopped, or has tripped an error state.

[00:02:54] [SCROLL:+300] Stats track total iterations completed, the current session identifier, and the circuit breaker state.

[00:03:01] [SCROLL:+300] You can start Ralph on any project path, then pause or stop mid-loop without losing state. Pause is non-destructive — it resumes exactly where it left off.

[00:03:08] [SCROLL:+300] The circuit breaker auto-halts Ralph when failure count exceeds a configured threshold. The health bar shows your current failure ratio at a glance.

[00:03:16] [SCROLL:+200] The safety warning is there for a reason — Ralph makes real changes to real code. Always point it at a feature branch, not main.

[00:03:23] [NAV:/agents] The Agents tab manages the four high-level autonomous agents that coordinate the entire worker layer.

[00:03:29] [PAUSE] Ralph handles code evolution. Cosmos runs the video production pipeline. MediaOffload handles media archival and compression. And Jesus H Christ is the repo resurrection specialist. Each agent can be started or stopped independently.

[00:03:39] [NAV:/tools] The Tools tab is where the monetized services live — starting with Jesus H Christ, Repo Resurrection.

[00:03:45] [PAUSE] JHC takes dead or abandoned GitHub repositories and brings them back to life — updated dependencies, repaired CI, and a working test suite.

[00:03:53] [FILL:input[placeholder*="GitHub org" i]:mikecranesync] Enter a GitHub org to scan for resurrection candidates. The engine scores each repo by how far it has decayed.

[00:04:00] [SCROLL:+300] To resurrect a specific repo, paste the URL and choose your aggression level.

[00:04:06] [CLICK:select] Gentle is documentation-only work at ninety-nine dollars. Moderate handles dependencies and CI at two-ninety-nine. Full aggressive refactor — the complete overhaul — is nine-ninety-nine.

[00:04:16] [SCROLL:+200] These checkboxes let you fine-tune what JHC is allowed to touch — dependency upgrades and CI configuration are controlled separately.

[00:04:22] [SCROLL:+200] Every resurrection queues an approval action in the HIL queue first. Nothing touches your codebase until you say so.

[00:04:29] [SCROLL:+500] Git Forensics runs static analysis on any local repository — full history reports and hotspot detection to find which files change most and why.

[00:04:37] [NAV:/hub] Finally, the Ladder Logic tab embeds a live reference view of the Micro 820 PLC's control program.

[00:04:44] [PAUSE] This is a direct window into the PLC logic — rungs, coils, and contacts — running live alongside your factory hardware.

[00:04:51] [NAV:/] That's Mission Control — eight tabs, forty-plus autonomous capabilities, one unified command surface for the entire FactoryLM cluster.

[00:04:59] [END]

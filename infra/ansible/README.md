# Ansible Fleet Sync — FactoryLM Mac Mini Cluster

Keeps all 3 Mac minis (Alpha, Bravo, Charlie) identical: same packages, same config, same repo.

## Prerequisites

Install Ansible on the machine you'll run from (travel laptop or any node):

```bash
# macOS
brew install ansible

# Windows (WSL)
sudo apt update && sudo apt install -y ansible

# Then install the Homebrew collection
ansible-galaxy collection install community.general
```

## Usage

```bash
cd ~/factorylm/infra/ansible

# Sync ALL Mac minis
ansible-playbook -i inventory.ini playbook.yml

# Sync one node only
ansible-playbook -i inventory.ini playbook.yml --limit bravo

# Dry run (show what would change)
ansible-playbook -i inventory.ini playbook.yml --check
```

## What It Does

| Task | Description |
|------|-------------|
| Homebrew packages | Installs everything in `Brewfile` (git, gh, tmux, jq, node, python, ollama, docker) |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| Python packages | pymodbus, qdrant-client, fastmcp, langgraph, etc. |
| Repo clone/update | Clones `factorylm` to `~/factorylm`, pulls latest |
| Node identity | Runs `bootstrap.sh` to detect node and write `~/.claude/CLAUDE.md` |
| Shell config | Universal env vars + aliases in `.zshrc` (preserves existing content) |
| tmux | Deploys shared `~/.tmux.conf`, auto-attaches on SSH login |
| Remote Login | Enables macOS SSH access |
| **SSH config (Tailscale-first)** | Deploys canonical `~/.ssh/config` pointing every alias (alpha/bravo/charlie/plc/travel/prod/pi) at Tailscale IPs. Source: `templates/ssh_config.j2` |
| **Claude Code permissions** | Merges canonical allow-list (ssh/scp/rsync/tailscale/nc/ping/dig/host) into every node's `~/.claude/settings.json` so agents never prompt for cluster-internal commands. Source: `files/merge_claude_permissions.py` |

### Canonical SSH Aliases (after sync)

```bash
ssh alpha       # 100.107.140.12  (factorylm@)
ssh bravo       # 100.86.236.11   (bravonode@)   # Tailscale default
ssh bravo-lan   # 192.168.1.11                    # same-subnet fallback
ssh charlie     # 100.70.49.126   (charlienode@)
ssh plc         # 100.72.2.99     (hharp@)
ssh travel      # 100.83.251.23   (hharp@)
ssh prod        # 100.68.120.99   (root@)        # VPS via Tailscale
ssh prod-public # 165.245.138.91                  # DigitalOcean fallback
ssh pi          # 100.66.216.6    (pi@)
```

The first time each node receives the template, Ansible writes a timestamped backup alongside (e.g. `~/.ssh/config.3854.2026-04-24@…~`) so a pre-existing hand-edit is never lost.

### Canonical Claude Code Permissions

Appended to every node's `~/.claude/settings.json` → `permissions.allow`:

```
Bash(ssh *)     Bash(scp *)     Bash(rsync *)
Bash(tailscale *)  Bash(/opt/homebrew/bin/tailscale *)
Bash(nc -z *)   Bash(ping -c* *)
Bash(dig *)     Bash(host *)
```

The merge is additive: only adds missing entries, preserves existing hooks / statusLine / model settings. A version marker at `~/.claude/.permissions-merged-v<N>` short-circuits re-runs at the same version.

To roll out a new canonical entry: edit `files/merge_claude_permissions.py`, raise `CANONICAL_VERSION`, commit, re-run the playbook.

## Adding New Packages

- **Homebrew:** Add to `Brewfile`, re-run playbook
- **Python:** Add to `pip_packages` in `playbook.yml`, re-run playbook
- **npm:** Add to `npm_packages` in `playbook.yml`, re-run playbook

## Adding a New Mac Mini

Add one line to `inventory.ini`:

```ini
newnode  ansible_host=100.x.x.x  ansible_user=newnodeuser
```

Run the playbook. Done.

## Network

Ansible connects over **Tailscale SSH** (100.x.x.x IPs). Services use **LAN IPs** (192.168.1.x) as defined in `CLUSTER.md`.

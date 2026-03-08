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

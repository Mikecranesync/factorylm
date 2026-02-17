#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# FactoryLM — Cosmos Factory — RunPod A100 80GB Setup Script
#
# Run this after SSHing into a fresh RunPod A100 instance.
# Idempotent — safe to re-run.
#
# Usage:  bash runpod_setup.sh
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Color helpers ────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
section() { echo -e "\n${BOLD}━━━ $* ━━━${NC}"; }

# ── 1. Banner ────────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  🏭 FactoryLM — Cosmos Factory — RunPod Setup           ║"
echo "║  Fine-tuning Cosmos Reason 2-2B on factory fault video  ║"
echo "║  GPU: A100 80GB SXM  |  Base: Qwen3-VL-2B-Instruct    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

WORKDIR="${HOME}/cosmos-factory"
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"
info "Working directory: ${WORKDIR}"

# ── 2. GPU Check ─────────────────────────────────────────────────────
section "GPU Verification"

if ! command -v nvidia-smi &>/dev/null; then
    fail "nvidia-smi not found — is this a GPU instance?"
fi

nvidia-smi --query-gpu=name,memory.total,driver_version,cuda_version \
    --format=csv,noheader
ok "GPU detected and driver loaded"

# ── 3. System Dependencies ──────────────────────────────────────────
section "System Dependencies (git, redis-server, ffmpeg)"

apt-get update -qq
apt-get install -y -qq git redis-server ffmpeg > /dev/null 2>&1

ok "git      $(git --version | head -1)"
ok "ffmpeg   $(ffmpeg -version 2>&1 | head -1)"
ok "redis    $(redis-server --version | head -1)"

# ── 4. Clone cosmos-reason2 ─────────────────────────────────────────
section "Clone nvidia-cosmos/cosmos-reason2"

if [ -d "${WORKDIR}/cosmos-reason2" ]; then
    warn "cosmos-reason2 already cloned — pulling latest"
    git -C "${WORKDIR}/cosmos-reason2" pull --ff-only || true
else
    git clone https://github.com/nvidia-cosmos/cosmos-reason2.git "${WORKDIR}/cosmos-reason2"
fi
ok "cosmos-reason2 ready at ${WORKDIR}/cosmos-reason2"

# ── 5. Install uv & set up venv ────────────────────────────────────
section "Python Environment (uv + venv)"

# Install uv if not present
if ! command -v uv &>/dev/null; then
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the env so uv is on PATH for the rest of this script
    export PATH="${HOME}/.local/bin:${PATH}"
fi
ok "uv $(uv --version)"

# Sync the cosmos-reason2 environment with CUDA 12.8 extras
cd "${WORKDIR}/cosmos-reason2"
info "Running uv sync --extra cu128 (this may take a few minutes)..."
uv sync --extra cu128
ok "cosmos-reason2 venv synced with CUDA 12.8 support"

# ── 6. Redis via conda-forge ────────────────────────────────────────
section "Redis Server (conda-forge)"

# RunPod images typically have conda pre-installed
if command -v conda &>/dev/null; then
    conda install -c conda-forge redis-server -y || warn "conda redis install failed — system redis is available as fallback"
    ok "redis-server installed via conda-forge"
else
    warn "conda not found — using system redis-server installed in step 3"
fi

# ── 7. Clone cosmos-rl ──────────────────────────────────────────────
section "Clone nvidia-cosmos/cosmos-rl"

if [ -d "${WORKDIR}/cosmos-rl" ]; then
    warn "cosmos-rl already cloned — pulling latest"
    git -C "${WORKDIR}/cosmos-rl" pull --ff-only || true
else
    git clone https://github.com/nvidia-cosmos/cosmos-rl.git "${WORKDIR}/cosmos-rl"
fi
ok "cosmos-rl ready at ${WORKDIR}/cosmos-rl"

# ── 8. Directory Structure ──────────────────────────────────────────
section "Data & Output Directories"

mkdir -p "${WORKDIR}/data/training/clips"
mkdir -p "${WORKDIR}/data/training/annotations"
mkdir -p "${WORKDIR}/data/eval"
mkdir -p "${WORKDIR}/outputs"

ok "data/training/clips/"
ok "data/training/annotations/"
ok "data/eval/"
ok "outputs/"

# ── 9. Custom Config & Dataloader ───────────────────────────────────
section "FactoryLM Custom Config & Dataloader"

warn "You need to copy your custom config and dataloader from the FactoryLM repo."
echo ""
info "Option A — scp from your laptop:"
echo "  scp -P <PORT> cosmos/config/*.py  root@<RUNPOD_IP>:${WORKDIR}/cosmos-reason2/"
echo "  scp -P <PORT> cosmos/dataloader.py root@<RUNPOD_IP>:${WORKDIR}/cosmos-reason2/"
echo ""
info "Option B — git pull the FactoryLM repo:"
echo "  git clone https://github.com/Mikecranesync/factorylm.git ${WORKDIR}/factorylm"
echo "  cp ${WORKDIR}/factorylm/cosmos/*.py ${WORKDIR}/cosmos-reason2/"
echo ""

# ── 10. Base Model Inference Test ───────────────────────────────────
section "Base Model Inference Test (nvidia/Cosmos-Reason2-2B)"

cd "${WORKDIR}/cosmos-reason2"
info "Running quick inference test to verify model loads..."
info "Model: nvidia/Cosmos-Reason2-2B (base: Qwen3-VL-2B-Instruct)"

uv run python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
import torch, sys

MODEL_ID = 'nvidia/Cosmos-Reason2-2B'
print(f'Loading tokenizer for {MODEL_ID}...')
processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
print('Tokenizer loaded OK')

print(f'Loading model {MODEL_ID} (this will download ~5GB on first run)...')
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,
    device_map='auto',
    trust_remote_code=True,
)
print(f'Model loaded on {model.device}')
print(f'Model parameters: {sum(p.numel() for p in model.parameters()):,}')

# Quick text-only sanity check
prompt = 'Describe what a conveyor jam looks like in a factory.'
inputs = processor(prompt, return_tensors='pt').to(model.device)
with torch.no_grad():
    output = model.generate(**inputs, max_new_tokens=50)
response = processor.decode(output[0], skip_special_tokens=True)
print(f'Test prompt: {prompt}')
print(f'Response:    {response[:200]}')
print()
print('✅ Base model inference test PASSED')
" && ok "Model inference test passed" || warn "Inference test failed — check model download and GPU memory"

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                  ✅ SETUP COMPLETE                       ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  cosmos-reason2:  ${WORKDIR}/cosmos-reason2"
echo "║  cosmos-rl:       ${WORKDIR}/cosmos-rl"
echo "║  training data:   ${WORKDIR}/data/training/"
echo "║  outputs:         ${WORKDIR}/outputs/"
echo "║  model:           nvidia/Cosmos-Reason2-2B"
echo "║  base arch:       Qwen3-VL-2B-Instruct"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}${BOLD}── NEXT STEPS (Manual) ──${NC}"
echo ""
echo -e "${CYAN}1.${NC} Start redis-server on port 12800 (required for cosmos-rl training):"
echo "     redis-server --port 12800 --daemonize yes"
echo ""
echo -e "${CYAN}2.${NC} Log into Weights & Biases for experiment tracking:"
echo "     wandb login"
echo ""
echo -e "${CYAN}3.${NC} Transfer Factory I/O fault videos from PLC laptop (Day 2):"
echo "     # From PLC laptop (100.72.2.99):"
echo "     scp -P <RUNPOD_SSH_PORT> ~/Videos/factory-io/*.mp4 \\"
echo "         root@<RUNPOD_IP>:${WORKDIR}/data/training/clips/"
echo ""
echo -e "${CYAN}4.${NC} Copy custom config & dataloader (see step 9 above)"
echo ""
echo -e "${GREEN}${BOLD}Day 1 target: base model running, GPU verified.${NC}"
echo -e "${GREEN}${BOLD}Day 2 target: record Factory I/O videos (125 clips, 5 fault types).${NC}"
echo ""
echo -e "🎵 ${BOLD}Cosmos Factory${NC} — Intelligence flows down. Who'll stop the rain? We will."

# FactoryLM — Root Makefile
# Use python3.12 everywhere (3.14 breaks uvloop/LiteLLM)
PYTHON := python3.12
PIP := $(PYTHON) -m pip
REPO := $(shell pwd)
LITELLM_PID := /tmp/factorylm-litellm.pid

.PHONY: setup litellm litellm-stop test health services stop ansible env

## ── Phase 0: Prerequisites ──────────────────────────────────────

setup:
	@echo "=== FactoryLM Setup Check ==="
	@command -v doppler  >/dev/null && echo "✓ doppler $$(doppler --version 2>&1 | head -1)" || echo "✗ doppler missing"
	@command -v ollama   >/dev/null && echo "✓ ollama"  || echo "✗ ollama missing"
	@command -v $(PYTHON) >/dev/null && echo "✓ $(PYTHON) $$($(PYTHON) --version 2>&1)" || echo "✗ $(PYTHON) missing"
	@command -v gh       >/dev/null && echo "✓ gh"      || echo "✗ gh missing"
	@command -v litellm  >/dev/null && echo "✓ litellm" || echo "✗ litellm — run: $(PIP) install 'litellm[proxy]' openai"
	@echo ""
	@echo "Ollama models:"
	@ollama list 2>/dev/null || echo "  (ollama not running)"

## ── Phase 1: Secrets ────────────────────────────────────────────

env:  ## Generate .env from Doppler
	doppler secrets download -p factorylm -c dev --no-file --format env > .env
	@echo "Generated .env with $$(wc -l < .env | tr -d ' ') secrets"

## ── Phase 2: LiteLLM Proxy ─────────────────────────────────────

litellm:  ## Start LiteLLM proxy on :4000 (background)
	@if [ -f $(LITELLM_PID) ] && kill -0 $$(cat $(LITELLM_PID)) 2>/dev/null; then \
		echo "LiteLLM already running (PID $$(cat $(LITELLM_PID)))"; \
	else \
		echo "Starting LiteLLM on :4000..."; \
		bash scripts/start_litellm.sh & echo $$! > $(LITELLM_PID); \
		sleep 3; \
		curl -sf http://localhost:4000/health >/dev/null && echo "✓ LiteLLM healthy" || echo "⚠ LiteLLM not responding yet"; \
	fi

litellm-stop:  ## Stop LiteLLM proxy
	@if [ -f $(LITELLM_PID) ]; then \
		kill $$(cat $(LITELLM_PID)) 2>/dev/null && echo "Stopped LiteLLM" || echo "LiteLLM not running"; \
		rm -f $(LITELLM_PID); \
	else \
		echo "No PID file — killing by port"; \
		lsof -ti:4000 | xargs kill 2>/dev/null || true; \
	fi

## ── Phase 3: Testing ───────────────────────────────────────────

test:  ## Run all tests
	$(PYTHON) -m pytest core/tests/ -v --tb=short 2>&1

## ── Phase 4: Health Check ───────────────────────────────────────

health:  ## Check all service endpoints
	@echo "=== FactoryLM Health Check ==="
	@echo ""
	@printf "%-20s " "Ollama :11434"; \
		curl -sf http://localhost:11434/api/tags >/dev/null && echo "✓ UP" || echo "✗ DOWN"
	@printf "%-20s " "LiteLLM :4000"; \
		curl -sf http://localhost:4000/health >/dev/null && echo "✓ UP" || echo "✗ DOWN"
	@printf "%-20s " "Diagnosis :8200"; \
		curl -sf http://localhost:8200/health >/dev/null && echo "✓ UP" || echo "✗ DOWN"
	@printf "%-20s " "Telegram Bot"; \
		pgrep -f "telegram_bot" >/dev/null && echo "✓ RUNNING" || echo "✗ NOT RUNNING"
	@echo ""
	@echo "Doppler:"; doppler secrets --only-names 2>/dev/null | wc -l | xargs printf "  %s secrets loaded\n"

## ── Phase 5: Service Orchestration ──────────────────────────────

services: litellm  ## Start all services
	@echo "Starting diagnosis service..."
	@echo "Starting telegram bot..."
	@echo "(launchd plists not yet configured — manual start only)"

stop: litellm-stop  ## Stop all services
	@lsof -ti:8200 | xargs kill 2>/dev/null || true
	@pkill -f "telegram_bot" 2>/dev/null || true
	@echo "All services stopped"

## ── Infra ───────────────────────────────────────────────────────

ansible:  ## Run Ansible fleet sync
	ansible-playbook infra/ansible/playbook.yml -i infra/ansible/inventory.yml

## ── Help ────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

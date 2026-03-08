# FactoryLM — Root Makefile
# Use python3.12 everywhere (3.14 breaks uvloop/LiteLLM)
PYTHON := python3.12
PIP := $(PYTHON) -m pip
REPO := $(shell pwd)
LITELLM_PID := /tmp/factorylm-litellm.pid

.PHONY: setup litellm litellm-stop test health services stop ansible env telegram telegram-stop whatsapp whatsapp-stop stack-up stack-down

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

## ── Phase 5: Telegram Bot ────────────────────────────────────────

telegram: litellm  ## Start Telegram bot (requires TELEGRAM_TOKEN)
	@if pgrep -f "services.telegram_bot" >/dev/null 2>&1; then \
		echo "Telegram bot already running"; \
	else \
		if [ -z "$$TELEGRAM_TOKEN" ]; then \
			echo "ERROR: TELEGRAM_TOKEN not set. Run: export TELEGRAM_TOKEN=<token>"; \
			exit 1; \
		fi; \
		echo "Starting Telegram bot..."; \
		PYTHONPATH=$(REPO) $(PYTHON) -m services.telegram_bot & \
		echo "✓ Telegram bot started (PID $$!)"; \
	fi

telegram-stop:  ## Stop Telegram bot
	@pkill -f "services.telegram_bot" 2>/dev/null && echo "Stopped Telegram bot" || echo "Telegram bot not running"

## ── Phase 5b: WhatsApp Adapter ───────────────────────────────────

whatsapp: litellm  ## Start WhatsApp adapter on :8200
	@if lsof -ti:8200 >/dev/null 2>&1; then \
		echo "WhatsApp adapter already running on :8200"; \
	else \
		echo "Starting WhatsApp adapter on :8200..."; \
		PYTHONPATH=$(REPO) $(PYTHON) -m uvicorn services.whatsapp.main:app --host 0.0.0.0 --port 8200 & \
		sleep 2; \
		curl -sf http://localhost:8200/health >/dev/null && echo "✓ WhatsApp adapter healthy" || echo "⚠ WhatsApp adapter not responding yet"; \
	fi

whatsapp-stop:  ## Stop WhatsApp adapter
	@lsof -ti:8200 | xargs kill 2>/dev/null && echo "Stopped WhatsApp adapter" || echo "WhatsApp adapter not running"

## ── Phase 6: Service Orchestration ──────────────────────────────

services: litellm telegram whatsapp  ## Start all services
	@echo "All services started"

stop: litellm-stop telegram-stop whatsapp-stop  ## Stop all services
	@echo "All services stopped"

## ── Phase 7: Docker Compose Stack ─────────────────────────────

stack-up:  ## Start full stack via Docker Compose (secrets via Doppler)
	doppler run -p factorylm -c dev -- docker compose up -d
	@echo "Stack started — run 'docker compose ps' to check"

stack-down:  ## Stop Docker Compose stack
	docker compose down
	@echo "Stack stopped"

## ── Infra ───────────────────────────────────────────────────────

ansible:  ## Run Ansible fleet sync
	ansible-playbook infra/ansible/playbook.yml -i infra/ansible/inventory.yml

## ── Help ────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

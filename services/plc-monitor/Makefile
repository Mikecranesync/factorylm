# PLC Monitor — service management
# Run `make help` to see available commands.

.PHONY: install start stop restart status logs run uninstall help

PLCMON := ./plcmon

install:   ## Install deps, plist, and CLI symlink
	@$(PLCMON) install

start:     ## Start the service via launchd
	@$(PLCMON) start

stop:      ## Stop the service
	@$(PLCMON) stop

restart:   ## Stop + start
	@$(PLCMON) restart

status:    ## Show service status dashboard
	@$(PLCMON) status

logs:      ## Tail stdout + stderr logs (follow mode)
	@$(PLCMON) logs

run:       ## Run in foreground (dev/debug)
	@$(PLCMON) run

uninstall: ## Remove plist and symlink
	@$(PLCMON) uninstall

help:      ## Show this help
	@printf '\033[1mPLC Monitor targets:\033[0m\n'
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

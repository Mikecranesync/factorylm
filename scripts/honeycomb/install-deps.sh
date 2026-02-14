#!/usr/bin/env bash
# install-deps.sh — Install OpenTelemetry npm packages globally (Linux VPS)
# Usage: bash install-deps.sh
set -euo pipefail

PACKAGES=(
  "@opentelemetry/sdk-node"
  "@opentelemetry/auto-instrumentations-node"
  "@opentelemetry/exporter-trace-otlp-http"
  "@opentelemetry/resources"
  "@opentelemetry/semantic-conventions"
)

echo "=== Installing OpenTelemetry packages globally ==="
echo ""

for pkg in "${PACKAGES[@]}"; do
  echo "→ npm install -g ${pkg}"
  npm install -g "${pkg}"
  echo ""
done

echo "=== Done. Installed packages: ==="
for pkg in "${PACKAGES[@]}"; do
  # Show installed version
  version=$(npm ls -g "${pkg}" --depth=0 2>/dev/null | grep "${pkg}" | head -1 || echo "  (check manually)")
  echo "  ${version}"
done
echo ""
echo "✓ All OTel dependencies installed globally."

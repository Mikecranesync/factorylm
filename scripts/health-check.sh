#!/usr/bin/env bash
# Minimal health check. Logs to /tmp/factorylm-health.log via plist redirect.
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
load=$(uptime | awk -F'load averages:' '{print $2}' | xargs)
disk=$(df -h /System/Volumes/Data | awk 'NR==2 {print $5}')
qdrant=$(curl -sm 3 -o /dev/null -w "%{http_code}" http://localhost:8000/healthz 2>/dev/null)
ollama_bravo=$(curl -sm 3 -o /dev/null -w "%{http_code}" http://192.168.1.11:11434/api/version 2>/dev/null)
echo "$ts load=$load disk=$disk qdrant=$qdrant ollama_bravo=$ollama_bravo"

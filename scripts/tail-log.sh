#!/usr/bin/env bash
#
# tail-log.sh - Zeigt das Live-Log des notlicht-monitor-Dienstes auf dem Pi.
#
# Voraussetzung: SSH-Alias "notlicht-pi" (s. ~/.ssh/config).
# Beenden mit Ctrl-C.
#
set -euo pipefail

SSH_HOST="${SSH_HOST:-notlicht-pi}"
LINES="${LINES:-50}"

echo ">> Letzte $LINES Zeilen + Follow (Ctrl-C zum Beenden)"
echo ">> Host: $SSH_HOST"
echo

exec ssh -t "$SSH_HOST" "journalctl -u notlicht-monitor.service -n $LINES -f"

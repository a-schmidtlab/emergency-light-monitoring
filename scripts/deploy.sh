#!/usr/bin/env bash
#
# deploy.sh - Synct die aktuelle Arbeitskopie auf den Pi und aktualisiert
#             Code + systemd-Units in /opt/notlicht-monitor bzw.
#             /etc/systemd/system.
#
# Voraussetzung: SSH-Alias "notlicht-pi" in ~/.ssh/config (passwortloser Login).
# Ueberschreibt NICHT /etc/notlicht-monitor/config.yaml (produktive Config
# bleibt unangetastet).
#
# Umgebungsvariablen (optional):
#   SSH_HOST       Host-Alias, Default: notlicht-pi
#   REMOTE_STAGE   Staging-Verzeichnis auf dem Pi, Default: /tmp/notlicht-monitor-src
#   RESTART_TIMER  "1" -> Timer nach Deploy restarten, Default: 0
#
set -euo pipefail

SSH_HOST="${SSH_HOST:-notlicht-pi}"
REMOTE_STAGE="${REMOTE_STAGE:-/tmp/notlicht-monitor-src}"
RESTART_TIMER="${RESTART_TIMER:-0}"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo ">> Projekt: $PROJECT_ROOT"
echo ">> Ziel:    $SSH_HOST:$REMOTE_STAGE"
echo

echo ">> [1/3] Arbeitskopie via rsync nach $SSH_HOST:$REMOTE_STAGE"
rsync -a --delete --info=stats1 \
  --exclude='.git/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='state.json' \
  --exclude='config.yaml' \
  ./ "$SSH_HOST:$REMOTE_STAGE/"

echo
echo ">> [2/3] Code in /opt/notlicht-monitor installieren (sudo)"
ssh "$SSH_HOST" "sudo install -m 0644 $REMOTE_STAGE/code/*.py /opt/notlicht-monitor/ && sudo chmod 755 /opt/notlicht-monitor/main.py"

echo
echo ">> [3/3] systemd-Units aktualisieren"
ssh "$SSH_HOST" "sudo install -m 0644 $REMOTE_STAGE/systemd/notlicht-monitor.service /etc/systemd/system/ && sudo install -m 0644 $REMOTE_STAGE/systemd/notlicht-monitor.timer /etc/systemd/system/ && sudo systemctl daemon-reload"

if [[ "$RESTART_TIMER" == "1" ]]; then
  echo
  echo ">> Timer neu starten (RESTART_TIMER=1)"
  ssh "$SSH_HOST" "sudo systemctl restart notlicht-monitor.timer"
fi

echo
echo "== Deploy erfolgreich =="
echo "Timer-Status:    ssh $SSH_HOST 'systemctl list-timers notlicht-monitor.timer'"
echo "Letzter Lauf:    ssh $SSH_HOST 'systemctl status notlicht-monitor.service --no-pager'"
echo "Live-Log:        scripts/tail-log.sh"
echo
echo "Hinweis: /etc/notlicht-monitor/config.yaml bleibt unveraendert."

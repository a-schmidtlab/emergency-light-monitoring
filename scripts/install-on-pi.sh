#!/usr/bin/env bash
#
# install-on-pi.sh - Erstinstallation auf dem Raspberry Pi.
#
# Laeuft lokal auf dem Pi. Idempotent: ein zweiter Aufruf aktualisiert den Code,
# laesst aber bereits vorhandene config.yaml und state.json unveraendert.
#
# Voraussetzung: Die Projektdateien liegen auf dem Pi unter $SRC (Default:
# /tmp/notlicht-monitor-src - genau dorthin kopiert scripts/deploy.sh).
#
# Aufruf typischerweise via deploy.sh + SSH:
#   ssh notlicht-pi 'sudo bash /tmp/notlicht-monitor-src/scripts/install-on-pi.sh'
#
set -euo pipefail

SRC="${SRC:-/tmp/notlicht-monitor-src}"

if [[ $EUID -ne 0 ]]; then
  echo "Dieses Skript muss als root laufen (sudo bash $0)." >&2
  exit 1
fi

if [[ ! -d "$SRC" ]]; then
  echo "Quellverzeichnis $SRC existiert nicht. Erst via scripts/deploy.sh syncen." >&2
  exit 2
fi

echo ">> [1/6] apt-Pakete installieren"
apt-get update
apt-get install -y --no-install-recommends python3 python3-requests python3-yaml

echo
echo ">> [2/6] Systemuser 'notlicht' anlegen (falls nicht vorhanden)"
if id notlicht >/dev/null 2>&1; then
  echo "   User notlicht existiert bereits."
else
  useradd -r -s /usr/sbin/nologin notlicht
  echo "   User notlicht angelegt."
fi

echo
echo ">> [3/6] Verzeichnisse anlegen"
install -d -m 0755 /opt/notlicht-monitor
install -d -m 0755 /etc/notlicht-monitor
install -d -m 0750 -o notlicht -g notlicht /var/lib/notlicht-monitor

echo
echo ">> [4/6] Python-Code nach /opt/notlicht-monitor kopieren"
install -m 0644 "$SRC"/code/*.py /opt/notlicht-monitor/
chmod 755 /opt/notlicht-monitor/main.py

echo
echo ">> [5/6] systemd-Units installieren"
install -m 0644 "$SRC"/systemd/notlicht-monitor.service /etc/systemd/system/
install -m 0644 "$SRC"/systemd/notlicht-monitor.timer   /etc/systemd/system/
systemctl daemon-reload

echo
echo ">> [6/6] config.yaml und secrets.yaml bereitstellen (nur wenn noch nicht vorhanden)"
if [[ -f /etc/notlicht-monitor/config.yaml ]]; then
  echo "   /etc/notlicht-monitor/config.yaml existiert - bleibt unveraendert."
else
  install -m 0600 -o notlicht -g notlicht \
    "$SRC"/config.yaml.example /etc/notlicht-monitor/config.yaml
  echo "   config.yaml aus config.yaml.example erstellt (chmod 600)."
fi

if [[ -f /etc/notlicht-monitor/secrets.yaml ]]; then
  echo "   /etc/notlicht-monitor/secrets.yaml existiert - bleibt unveraendert."
else
  install -m 0600 -o notlicht -g notlicht \
    "$SRC"/secrets.yaml.example /etc/notlicht-monitor/secrets.yaml
  echo "   secrets.yaml aus secrets.yaml.example erstellt (chmod 600)."
fi

cat <<'EOF'

==============================================================
Installation abgeschlossen.

Naechste Schritte:
  1) Config befuellen:
       sudo nano /etc/notlicht-monitor/config.yaml

  2) SMTP-Passwort in secrets.yaml eintragen:
       sudo nano /etc/notlicht-monitor/secrets.yaml

  3) Probelauf ohne Mailversand:
       sudo -u notlicht python3 /opt/notlicht-monitor/main.py \
           --dry-run --force-weekly

  4) Echter Mailtest:
       sudo -u notlicht python3 /opt/notlicht-monitor/main.py --force-weekly

  5) Timer scharfschalten:
       sudo systemctl enable --now notlicht-monitor.timer

  6) Kontrolle:
       systemctl list-timers notlicht-monitor.timer
       journalctl -u notlicht-monitor.service -f
==============================================================
EOF

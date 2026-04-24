# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.
Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Geändert
- Projektstruktur aufgeräumt: flache Duplikate im Root entfernt, Inhalte aus dem
  inneren `notlicht-monitor/`-Ordner auf die Projektebene hochgezogen (entspricht
  der in `README.md` dokumentierten Topologie).
- Screenshot der NETLIGHT-Oberfläche nach `docs/gfs-netlight-webui.png` verschoben.

### Hinzugefügt
- `.gitignore`, `.editorconfig`, `CHANGELOG.md`.
- `scripts/install-on-pi.sh` – automatisiert die Erstinstallation auf dem Pi
  (Pakete, User, Verzeichnisse, systemd-Units).
- `scripts/deploy.sh` – rsync-basierter Push der aktuellen Arbeitskopie auf den Pi.
- `scripts/tail-log.sh` – bequemer Live-Log via SSH.

## [0.1.0] - 2026-04-24

### Hinzugefügt
- Erster funktionaler Stand: Abfrage der drei NETLIGHT-AJAX-Endpoints,
  Alarm-/Entwarnungslogik, Wochenreport, SMTP-Versand (SSL/STARTTLS),
  persistenter State, systemd-Service + Timer, YAML-Config mit Defaults
  und Validierung, Dry-Run-Modus.
- Vollständige Dokumentation in `README.md`, `INSTALL.md`, `ANFORDERUNGEN.md`,
  `TECHNIK.md`.

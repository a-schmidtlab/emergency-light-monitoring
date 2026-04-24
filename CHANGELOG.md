# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.
Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Geändert
- Projektstruktur aufgeräumt: flache Duplikate im Root entfernt, Inhalte aus dem
  inneren `notlicht-monitor/`-Ordner auf die Projektebene hochgezogen (entspricht
  der in `README.md` dokumentierten Topologie).
- Screenshot der NETLIGHT-Oberfläche nach `docs/gfs-netlight-webui.png` verschoben.
- **Secrets getrennt**: `smtp.password` steht jetzt in einer separaten
  `secrets.yaml`, die beim Start automatisch über die Hauptconfig gemerged wird.
  `config.yaml` enthält keine Passwörter mehr und kann weiter­gegeben werden.
- **Fehlermeldungen in Mails**: `netlight_client` gibt statt roher Python-Tracebacks
  sprechende, endanwender­taugliche Kurzmeldungen aus (Timeout, Verbindung
  nicht möglich, HTTP-Fehler, ungültige Antwort). Volle Technik-Details bleiben
  im systemd-Journal.
- **Dokumentation konsolidiert**: `INSTALL.md`, `TECHNIK.md` und `ANFORDERUNGEN.md`
  wurden vollständig in ein erweitertes `README.md` gemerged. Das neue README
  enthält ein Inhaltsverzeichnis, einen einleitenden Abschnitt zu Notlichtanlagen
  und der Notwendigkeit wöchentlicher Kontrollen, sowie alle bisherigen
  Installations-, Anforderungs- und Technikkapitel.

### Hinzugefügt
- `.gitignore`, `.editorconfig`, `CHANGELOG.md`.
- `secrets.yaml.example` als Template für die separate Secrets-Datei.
- `--secrets PATH` CLI-Parameter in `main.py` (Default: `secrets.yaml` neben der Config).
- `scripts/install-on-pi.sh` – automatisiert die Erstinstallation auf dem Pi
  (Pakete, User, Verzeichnisse, systemd-Units, Config- und Secrets-Skelette).
- `scripts/deploy.sh` – rsync-basierter Push der aktuellen Arbeitskopie auf den Pi.
  Schützt `config.yaml`, `secrets.yaml` und `state.json` auf dem Pi vor Überschreibung.
- `scripts/tail-log.sh` – bequemer Live-Log via SSH.
- **`LICENSE`**: Nicht-kommerzielle Nutzungslizenz („Notlicht-Monitor Non-Commercial
  License") mit ausdrücklichem Disclaimer zur Sicherheitsrelevanz und Verweis auf
  die einschlägigen Normen (DIN EN 50172, VDE 0108, DIN EN 50171, VDE 0100-560,
  DGUV V3, ArbStättV).
- **Copyright- und Disclaimer-Header** in allen Python-Modulen unter `code/`.

### Entfernt
- `INSTALL.md`, `TECHNIK.md`, `ANFORDERUNGEN.md` – Inhalte vollständig in das
  neue `README.md` übernommen.

## [0.1.0] - 2026-04-24

### Hinzugefügt
- Erster funktionaler Stand: Abfrage der drei NETLIGHT-AJAX-Endpoints,
  Alarm-/Entwarnungslogik, Wochenreport, SMTP-Versand (SSL/STARTTLS),
  persistenter State, systemd-Service + Timer, YAML-Config mit Defaults
  und Validierung, Dry-Run-Modus.
- Vollständige Dokumentation in `README.md`, `INSTALL.md`, `ANFORDERUNGEN.md`,
  `TECHNIK.md` (die drei letzteren wurden nachträglich in `README.md` gemerged,
  siehe Unreleased).

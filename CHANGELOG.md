# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.
Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased] — v0.3.0

### Hinzugefügt
- **Selbstüberwachung (`health.py`)**: Neues Modul überwacht den Monitor selbst —
  nicht nur die Anlagen. Prüft bei jedem Lauf: systemd-Timer-Zustand via
  `systemctl show` (erkennt `SubState=elapsed` + kein `NextElapseUSecMonotonic`,
  das sog. „Timer-Einschlafen" unter systemd 257), Laufzeit-Lücken seit
  `monitor_last_finished_iso`, Dateisystem-Schreibbarkeit und IMAP-Fehlerserie.
  Befunde werden als strukturierte `FINDING`/`SUMMARY`-Logzeilen ausgegeben
  (Logger `notlicht-health`). Bei CRITICAL optional Digest-Mail mit Cooldown.
- **Neue State-Felder**: `monitor_last_finished_iso`, `monitor_last_exit_code`,
  `health_last_alert_sent_iso`, `imap_error_streak` — rückwärtskompatibel.
- **IMAP-Fehlerserie**: Wiederholte IMAP-Fehler werden in `state.json` gezählt
  und als Health-Finding eskaliert (`imap_error_streak`).
- **`health`-Config-Block**: Neue Sektion in `config.yaml.example` mit allen
  Schwellen, Faktoren und Mail-Schaltern; Defaults in `config.py` (kein
  Pflichtfeld — leerer oder fehlender Block = volle Defaults).
- **`scripts/notlicht-monitor-deploy.sudoers`**: Vorlage für minimale
  passwordless-sudo-Regeln (nur Deploy- und Test-Befehle), die den
  automatisierten Deploy-Workflow von der Workstation ermöglichen.
- **Mail-Subject-Default `mail.health_subject`** und Emojis
  `health_emoji_warn` / `health_emoji_critical`.

### Geändert
- **`systemd/notlicht-monitor.timer`**: `OnUnitActiveSec` → `OnUnitInactiveSec`
  (robuster für `Type=oneshot` unter systemd 257; verhindert das beobachtete
  Einschlafen des Timers nach einigen Tagen Betrieb).
- **`netlight_client.py`**: Statusindex 6 (Testbetrieb) mit Wert `yellow`
  wird jetzt als regulärer automatischer Selbsttest gewertet — kein Alarm,
  keine Abweichungsmeldung. Andere Werte auf Index 6 bleiben Störung.
  Neue Property `in_testbetrieb` für Downstream-Nutzung.
- **`main.py`**: Mailer wird früher initialisiert (vor Netlight-Abfragen),
  damit Selbstüberwachungs-Mails dieselbe Instanz nutzen. IMAP-Streak wird
  nach jedem Lauf im State fortgeschrieben. `state.set_monitor_run_finished()`
  am Ende jedes Laufs.
- **`code/config.py`**: Validierung für `health.*`-Parameter (Faktoren,
  IMAP-Streak-Schwellen).
- **`recipients`** auf Produktivsystem: `beirat@spreefeld.org` ergänzt.

### Geändert (vor diesem Commit)

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
- **TEST-Mail-Funktion**: Neuer optionaler IMAP-Polling-Mode. Eine Mail mit
  Subject `TEST` an das Notlicht-Postfach erzeugt eine Status-Antwort an
  den Absender (Reply mit `In-Reply-To`/`References`-Headern für sauberes
  Threading). Andere Mails werden stillschweigend gelöscht. Pro Lauf
  bekommt jeder Absender max. eine Antwort (Reflection-Schutz). Dry-Run
  liest, löscht aber nicht. Default: deaktiviert (`imap.enabled: false`).
- Neues Modul `code/imap_handler.py`.
- Neue Config-Sektion `imap.*` mit automatischer Übernahme von SMTP-Werten,
  wenn entsprechende Felder leer sind (gleicher Account = minimale Config).
- Neuer Mail-Subject-Default `mail.test_response_subject`.
- Neuer CLI-Parameter `--skip-imap` zum Deaktivieren des Pollings für einen
  einzelnen Lauf.
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

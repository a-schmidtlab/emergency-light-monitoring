# Notlicht-Monitor

Automatisches Monitoring für GFS-NETLIGHT-Sicherheitsbeleuchtungs­anlagen. Läuft auf einem Raspberry Pi, prüft über die Weboberfläche der Anlagen den Zustand, versendet wöchentliche Statusreports und Sofort-Alarme per E-Mail.

## Was es tut

- Fragt drei Sicherheits­beleuchtungs­anlagen via HTTP-AJAX ab (keine Logindaten nötig, keine aktive Bedienung – reiner Lesezugriff).
- Bewertet Betriebsstatus, Sammelstörung, Tiefentladung, Testbetrieb, Netzbetrieb, Batteriebetrieb und liest Messwerte + Meldungsfeld aus.
- Erkennt Statuswechsel und alarmiert sofort bei Problemen.
- Schickt jeden Montag um 07:00 einen Wochenreport mit allen Details.
- Läuft leichtgewichtig genug, um auf einem Pi 1 B+ aus 2014 zu funktionieren.

## Mailtypen

| Ereignis | Beispiel-Betreff |
|---|---|
| Wöchentlicher Report, alles OK | 🟢 Wochenreport Notlicht - 24.04.2026 |
| Wöchentlicher Report, Störung | 🔴 Wochenreport Notlicht - 24.04.2026 |
| Anlage geht in Störung | 🔴 ALARM Notlicht - Anlage 1 - Treppenhaus |
| Anlage wieder OK | 🟢 Entwarnung Notlicht - Anlage 1 - Treppenhaus |

Kein Spam: Bei durchgehender Störung gibt es nur eine Alarmmail, keine Wiederholungen bis zur Rückkehr auf OK.

## Voraussetzungen

- Raspberry Pi (ARMv6 oder neuer) mit Raspberry Pi OS Lite (Bookworm)
- Python 3.11+ (in Bookworm Standard)
- Netzwerkzugang zu den Anlagen (selbes LAN)
- Eigener SMTP-Server mit SSL auf Port 465 (STARTTLS/587 auch unterstützt)

## Schnellstart

**Auf dem Pi (manuelle Installation, Details in [INSTALL.md](INSTALL.md)):**

```bash
# Repo/Archiv auf den Pi bringen (git clone, scp, rsync - egal wie) und cd hinein.

# 1. Abhaengigkeiten
sudo apt install -y python3 python3-requests python3-yaml

# 2. Zielverzeichnisse + Systemuser
sudo useradd -r -s /usr/sbin/nologin notlicht
sudo install -d -m 0755 /opt/notlicht-monitor /etc/notlicht-monitor
sudo install -d -m 0750 -o notlicht -g notlicht /var/lib/notlicht-monitor

# 3. Code + systemd-Units
sudo install -m 0644 code/*.py /opt/notlicht-monitor/
sudo chmod 755 /opt/notlicht-monitor/main.py
sudo install -m 0644 systemd/notlicht-monitor.* /etc/systemd/system/
sudo systemctl daemon-reload

# 4. Config anlegen und anpassen
sudo install -m 0600 -o notlicht -g notlicht config.yaml.example /etc/notlicht-monitor/config.yaml
sudo nano /etc/notlicht-monitor/config.yaml

# 5. Trockenlauf, dann echter Mailversand, dann Timer scharf
sudo -u notlicht python3 /opt/notlicht-monitor/main.py --dry-run --force-weekly
sudo -u notlicht python3 /opt/notlicht-monitor/main.py --force-weekly
sudo systemctl enable --now notlicht-monitor.timer
```

**Von der Workstation aus (bequemer, per Skripten):**

```bash
# einmalig: scripts/deploy.sh syncen lassen, dann install-on-pi.sh auf dem Pi:
scripts/deploy.sh
ssh notlicht-pi 'sudo bash /tmp/notlicht-monitor-src/scripts/install-on-pi.sh'
# config editieren, Testlauf, Timer enablen - s. ausgegebene Anleitung.
```

## Projektstruktur

```
emergencylight-monitoring/
├── README.md                ← Dieses Dokument
├── ANFORDERUNGEN.md         ← Anforderungskatalog
├── TECHNIK.md               ← Technische Beschreibung
├── INSTALL.md               ← Schritt-für-Schritt Installation (manuell)
├── CHANGELOG.md             ← Versionierte Änderungen
├── config.yaml.example      ← Vorlage für die Konfiguration
│
├── code/                    ← Python-Quellen, wird nach /opt/notlicht-monitor installiert
│   ├── main.py              ← Orchestrator, Einstiegspunkt
│   ├── netlight_client.py   ← HTTP-Abfrage der Anlagen
│   ├── mail_builder.py      ← Erzeugt Mail-Bodies
│   ├── mailer.py            ← SMTP-Versand
│   ├── state.py             ← Persistenz zwischen Läufen
│   └── config.py            ← YAML-Config laden und validieren
│
├── systemd/                 ← wird nach /etc/systemd/system installiert
│   ├── notlicht-monitor.service
│   └── notlicht-monitor.timer
│
├── scripts/                 ← Deployment-Helfer (optional, für komfortables Arbeiten)
│   ├── install-on-pi.sh     ← Erstinstallation (läuft auf dem Pi)
│   ├── deploy.sh            ← rsync-Push Workstation → Pi
│   └── tail-log.sh          ← Live-Log via SSH
│
└── docs/                    ← Referenzmaterial
    └── gfs-netlight-webui.png
```

### Deployment auf den Pi

Zwei Wege – der manuelle Weg ist in [INSTALL.md](INSTALL.md) beschrieben, der automatisierte nutzt die Helferskripte:

```bash
# 1. Einmalig: SSH-Alias 'notlicht-pi' in ~/.ssh/config eintragen
#    (Host, User, IdentityFile – passwortloser Login via Key).

# 2. Arbeitskopie auf den Pi syncen
scripts/deploy.sh

# 3. Nur beim ersten Mal: Installation auf dem Pi ausführen
ssh notlicht-pi 'sudo bash /tmp/notlicht-monitor-src/scripts/install-on-pi.sh'
#    -> Pakete, User, Verzeichnisse, systemd-Units. Idempotent.

# 4. Config befüllen (einmalig, auf dem Pi):
ssh notlicht-pi 'sudo nano /etc/notlicht-monitor/config.yaml'

# 5. Testlauf + Timer aktivieren (siehe INSTALL.md Abschnitte 5-7).

# Spätere Code-Updates: nur noch Schritt 2 (scripts/deploy.sh).
```

## Konfiguration in Kürze

Alle Einstellungen in `/etc/notlicht-monitor/config.yaml`:

- **`devices`** – Liste der Anlagen (Name + URL)
- **`smtp`** – Mailserver-Zugang (Host, Port, SSL, Login, Absender)
- **`recipients`** – Verteilerliste
- **`mail`** – Betreffvorlagen, Standardtext, eigener Text, Fußtext
- **`schedule`** – Wochentag und Uhrzeit des Reports
- **`http`** – Timeout und Retry-Parameter

Details: siehe Kommentare in `config.yaml.example`.

### Mailtext anpassen

```yaml
mail:
  intro_text: |
    Wochenstatus der Sicherheitsbeleuchtung vom {date}.
    Anlagen wurden automatisch abgefragt.
  custom_intro_text: ""     # wenn gefüllt: ersetzt intro_text komplett
  custom_footer: ""         # wird ans Ende jeder Mail gehängt
```

Verfügbare Platzhalter in Textfeldern: `{date}`, `{datetime}`, `{device}`.

## Betrieb

```bash
# Status des Timers
systemctl list-timers notlicht-monitor.timer

# Live-Log
journalctl -u notlicht-monitor.service -f

# Manueller Lauf zum Testen
sudo systemctl start notlicht-monitor.service

# Wochenreport sofort senden
sudo -u notlicht python3 /opt/notlicht-monitor/main.py --force-weekly

# State zurücksetzen (alle Anlagen als neue Baseline)
sudo rm /var/lib/notlicht-monitor/state.json
```

## Kommandozeilenparameter

| Parameter | Wirkung |
|---|---|
| `--config PATH` | Abweichende Config-Datei |
| `--state PATH` | Abweichende State-Datei |
| `--force-weekly` | Wochenreport jetzt senden, unabhängig vom Zeitplan |
| `--dry-run` | Mails nicht senden, nur auf stdout ausgeben |

## Sicherheitshinweise

Die NETLIGHT-Anlagen laufen auf einem sehr alten Software-Stack (Apache 2.2 / PHP 5.4 auf Debian 7). Diese Geräte sollten:

- **niemals direkt aus dem Internet erreichbar sein**
- idealerweise in einem separaten Management-VLAN stehen
- nur vom Monitor-Pi angesprochen werden

Der Monitor greift ausschließlich lesend zu. Er kann weder Tests auslösen noch Einstellungen ändern.

## Verhalten in Sonderfällen

| Situation | Verhalten |
|---|---|
| Erster Lauf nach Installation | Status wird als Baseline gespeichert, keine Mail |
| Anlage dauerhaft gestört | genau eine Alarmmail, dann Ruhe |
| Anlage oszilliert zwischen OK/Störung | Mail bei jedem Wechsel |
| Pi war aus zur geplanten Mailzeit | Report wird nach Boot nachgeholt (systemd `Persistent=true`) |
| State-Datei gelöscht oder korrupt | Neustart mit leerem State, keine fälschlichen Alarme |
| Mailserver temporär offline | Fehler wird geloggt, nächster Run versucht es nicht nochmal – Mails werden bei Versandfehler **nicht** nachgeholt |

## Dokumentation

- [ANFORDERUNGEN.md](ANFORDERUNGEN.md) – Was das System tun soll (funktional + nicht-funktional)
- [TECHNIK.md](TECHNIK.md) – Wie es gebaut ist (Architektur, Module, Datenfluss)
- [INSTALL.md](INSTALL.md) – Wie man es installiert

## Hinweis

Intern verwendetes Tool. Keine Gewährleistung. Wichtig bei Sicherheits­beleuchtung: Dieses System **ersetzt nicht** die vorgeschriebenen manuellen Prüfungen nach DIN/VDE. Es ist ein zusätzliches Monitoring, kein Ersatz für die normgerechte Wartung.

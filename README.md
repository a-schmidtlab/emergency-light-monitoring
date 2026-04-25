# Notlicht-Monitor

Ein kleiner Hilfsdienst für drei Notlichtanlagen. Läuft auf einem alten Raspberry Pi, schaut jede Viertelstunde nach, ob die Anlagen noch beieinander sind, und schickt nur dann eine Mail, wenn sich etwas geändert hat. Einmal pro Woche kommt zusätzlich ein Sammelbericht.

> **Bitte erst [Abschnitt 14](#14-lizenz--haftungsausschluss) lesen.**
> Dieses Programm ersetzt **keine** der gesetzlich vorgeschriebenen Prüfungen einer Notlichtanlage durch Fachpersonal (DIN EN 50172, VDE 0108, DIN EN 50171, VDE 0100-560, DGUV V3 u. a.). Es ist eine zusätzliche Hilfe — mehr nicht.

---

## Inhaltsverzeichnis

1. [Worum es geht](#1-worum-es-geht)
2. [Mailtypen](#2-mailtypen)
3. [Projektstruktur](#3-projektstruktur)
4. [Voraussetzungen](#4-voraussetzungen)
5. [Schnellstart](#5-schnellstart)
6. [Installation auf dem Raspberry Pi](#6-installation-auf-dem-raspberry-pi)
   - 6.1 [Variante A: automatisiert von der Workstation](#61-variante-a-automatisiert-von-der-workstation)
   - 6.2 [Variante B: manuell auf dem Pi](#62-variante-b-manuell-auf-dem-pi)
   - 6.3 [Testlauf](#63-testlauf)
   - 6.4 [systemd-Timer aktivieren](#64-systemd-timer-aktivieren)
   - 6.5 [Betrieb prüfen](#65-betrieb-prüfen)
7. [Konfiguration im Detail](#7-konfiguration-im-detail)
   - 7.1 [Warum zwei Dateien: `config.yaml` vs. `secrets.yaml`](#71-warum-zwei-dateien-configyaml-vs-secretsyaml)
   - 7.2 [Abschnitte in `config.yaml`](#72-abschnitte-in-configyaml)
   - 7.3 [Abschnitte in `secrets.yaml`](#73-abschnitte-in-secretsyaml)
   - 7.4 [Mailtext anpassen](#74-mailtext-anpassen)
   - 7.5 [TEST-Mail-Funktion (optional)](#75-test-mail-funktion-optional)
8. [Betrieb & Wartung](#8-betrieb--wartung)
9. [Kommandozeilenparameter](#9-kommandozeilenparameter)
10. [Anforderungen](#10-anforderungen)
    - 10.1 [Zweck und Umfeld](#101-zweck-und-umfeld)
    - 10.2 [Funktionale Anforderungen](#102-funktionale-anforderungen)
    - 10.3 [Nicht-funktionale Anforderungen](#103-nicht-funktionale-anforderungen)
    - 10.4 [Abgrenzung](#104-abgrenzung)
    - 10.5 [Annahmen](#105-annahmen)
11. [Technische Beschreibung](#11-technische-beschreibung)
    - 11.1 [Überblick & Architektur](#111-überblick--architektur)
    - 11.2 [Modulübersicht](#112-modulübersicht)
    - 11.3 [Datenfluss pro Lauf](#113-datenfluss-pro-lauf)
    - 11.4 [NETLIGHT-Endpoints und Datenmodell](#114-netlight-endpoints-und-datenmodell)
    - 11.5 [Entscheidungslogik Mailversand](#115-entscheidungslogik-mailversand)
    - 11.6 [State-Schema](#116-state-schema)
    - 11.7 [Deployment-Layout](#117-deployment-layout)
    - 11.8 [Fehlerklassen und Reaktionen](#118-fehlerklassen-und-reaktionen)
    - 11.9 [Leistung und Laufzeit](#119-leistung-und-laufzeit)
    - 11.10 [Erweiterungspunkte](#1110-erweiterungspunkte)
12. [Sicherheitshinweise](#12-sicherheitshinweise)
13. [Verhaltensmatrix](#13-verhaltensmatrix)
14. [Lizenz & Haftungsausschluss](#14-lizenz--haftungsausschluss)
15. [Autor](#15-autor)

---

## 1. Worum es geht

Sicherheitsbeleuchtung ist die Sorte Lampe, die fast immer dunkel ist. Sie wartet — auf einen Stromausfall, einen Brand, auf einen Moment, in dem die anderen Lampen ausgehen und Menschen im Halbdunkel einen Weg nach draußen brauchen. Dass sie wirklich anspringt, weiß man erst, wenn man nachsieht. Bauteile altern schleichend; eine Sicherung kann auslösen, ohne dass es jemand mitbekommt; ein Bus zwischen Zentrale und Einzelleuchten kann wochenlang stumm sein, bevor es auffällt. Eine rote LED an der Zentrale hilft nur dem, der gerade in dem Raum steht.

Der Gesetzgeber denkt das in Deutschland systematisch durch. Normen wie **DIN EN 50172** / **VDE 0108-100**, **EN 50171**, **VDE 0100-560**, die **DGUV Vorschrift 3** und die **ArbStättV** verlangen abgestufte Prüfungen — Sichtkontrolle täglich, Funktionstest der Umschaltung wöchentlich, Einzelleuchten monatlich, volle Batterieprüfung jährlich durch Fachpersonal. Verantwortlich ist der Betreiber, und im Ernstfall haftet er für ausbleibende Wartung sowohl zivil- wie strafrechtlich.

Drei Anlagen einmal pro Woche zu Fuß abzuklappern und in jedes Prüfbuch einen Strich zu setzen, dauert einen halben Vormittag. Praktischerweise misst sich jede dieser Anlagen ohnehin selbst: ein eingebauter Webserver liefert Spannungen, Ladeströme, Statusflags und etwaige Meldungen — eine geduldige, monotone Selbstvermessung, an die man andocken kann. Genau das tut dieses Programm: es fragt im Viertelstundentakt nach, vergleicht den Zustand mit dem letzten Mal, und meldet sich nur, wenn sich etwas geändert hat. Einmal pro Woche schickt es zusätzlich einen Sammelbericht — denn ein Schweigen, das niemand bemerkt, ist von einem Programmfehler nicht zu unterscheiden.

Was es **nicht** kann: nachsehen, ob die Lampen tatsächlich angehen. Es liest nur das, was die Anlage von sich selbst meldet — und was eine Maschine über sich selbst weiß, deckt sich nicht zwangsläufig mit dem, was über sie zu wissen wäre. Die normgerechten Sicht- und Funktionsprüfungen werden also nicht ersetzt; sie verschieben sich nur dorthin, wo sie wirklich gebraucht werden: ans Ende einer Mail, in der etwas auffällig geworden ist. Mehr soll dieses Programm nicht. Und weniger auch nicht.

---

## 2. Mailtypen

| Ereignis | Beispiel-Betreff |
|---|---|
| Wöchentlicher Report, alles OK | 🟢 Wochenreport Notlicht - 24.04.2026 |
| Wöchentlicher Report, Störung vorhanden | 🔴 Wochenreport Notlicht - 24.04.2026 |
| Anlage wechselt OK → Störung | 🔴 ALARM Notlicht - Anlage 1 |
| Anlage wechselt Störung → OK | 🟢 Entwarnung Notlicht - Anlage 1 |
| Antwort auf eingehende TEST-Mail (optional, s. [7.5](#75-test-mail-funktion-optional)) | 🟢 / 🔴 TEST-Antwort Notlicht - 24.04.2026 |

**Kein Mail-Spam:** Bei durchgehender Störung gibt es genau *eine* Alarmmail, keine Wiederholungen. Erst wenn die Anlage wieder OK war und erneut in Störung geht, kommt die nächste Alarmmail.

---

## 3. Projektstruktur

```
emergencylight-monitoring/
├── README.md                ← Dieses Dokument (komplette Doku)
├── LICENSE                  ← Non-Commercial-Lizenz + Disclaimer
├── CHANGELOG.md             ← Versionierte Änderungen
├── config.yaml.example      ← Vorlage für die Konfiguration
├── secrets.yaml.example     ← Vorlage für Passwörter (getrennt!)
│
├── code/                    ← Python-Quellen, wird nach /opt/notlicht-monitor installiert
│   ├── main.py              ← Orchestrator, Einstiegspunkt
│   ├── netlight_client.py   ← HTTP-Abfrage der Anlagen (nur lesend)
│   ├── mail_builder.py      ← Erzeugt Mail-Bodies (Plaintext)
│   ├── mailer.py            ← SMTP-Versand
│   ├── state.py             ← Persistenz zwischen Läufen
│   └── config.py            ← YAML-Config + Secrets laden & validieren
│
├── systemd/                 ← wird nach /etc/systemd/system/ installiert
│   ├── notlicht-monitor.service
│   └── notlicht-monitor.timer
│
├── scripts/                 ← Deployment-Helfer (optional)
│   ├── install-on-pi.sh     ← Erstinstallation (läuft auf dem Pi)
│   ├── deploy.sh            ← rsync-Push Workstation → Pi
│   └── tail-log.sh          ← Live-Log via SSH
│
└── docs/
    └── gfs-netlight-webui.png
```

---

## 4. Voraussetzungen

| Komponente | Anforderung |
|---|---|
| Monitor-Host | Raspberry Pi (ARMv6 oder neuer). Getestet: Pi 1 B+ (2014), 512 MB RAM. |
| Betriebssystem | Raspberry Pi OS Lite (Bookworm oder neuer, 32-bit reicht). |
| Python | 3.11+ (aus apt). Weder pip noch venv erforderlich. |
| apt-Pakete | `python3`, `python3-requests`, `python3-yaml` |
| Netzwerk | Pi und alle Anlagen im selben LAN, TCP-Port 80 zur Anlage erreichbar. |
| SMTP | Eigener Mailserver mit SSL (Port 465) oder STARTTLS (587). |

---

## 5. Schnellstart

**Aus dem Arbeitsverzeichnis auf der Workstation, wenn ein SSH-Alias `notlicht-pi` in `~/.ssh/config` existiert:**

```bash
scripts/deploy.sh
ssh notlicht-pi 'sudo bash /tmp/notlicht-monitor-src/scripts/install-on-pi.sh'
ssh notlicht-pi 'sudo nano /etc/notlicht-monitor/config.yaml'
ssh notlicht-pi 'sudo nano /etc/notlicht-monitor/secrets.yaml'
ssh notlicht-pi 'sudo -u notlicht python3 /opt/notlicht-monitor/main.py --force-weekly'
ssh notlicht-pi 'sudo systemctl enable --now notlicht-monitor.timer'
```

Alles weitere ist Feintuning. Details in Abschnitt 6.

---

## 6. Installation auf dem Raspberry Pi

Getestetes Ziel: **Pi 1 B+ mit Raspberry Pi OS Lite (Bookworm bzw. Trixie, 32-bit, armv6l)**.

### 6.1 Variante A: automatisiert von der Workstation

Voraussetzung: passwortloser SSH-Zugang zum Pi (SSH-Key deponiert) und ein SSH-Alias `notlicht-pi` in `~/.ssh/config`.

```bash
# 1. Arbeitskopie auf den Pi syncen (rsync, lässt /etc/notlicht-monitor unangetastet)
scripts/deploy.sh

# 2. Nur beim ersten Mal: Installation auf dem Pi ausführen (idempotent)
ssh notlicht-pi 'sudo bash /tmp/notlicht-monitor-src/scripts/install-on-pi.sh'
#    → legt User 'notlicht' an, installiert Pakete, kopiert Code und systemd-Units,
#      legt /etc/notlicht-monitor/config.yaml + secrets.yaml aus den Vorlagen an.

# 3. Config befüllen (einmalig, auf dem Pi)
ssh notlicht-pi 'sudo nano /etc/notlicht-monitor/config.yaml'
ssh notlicht-pi 'sudo nano /etc/notlicht-monitor/secrets.yaml'

# 4. Testlauf + Timer aktivieren – siehe 6.3 / 6.4.

# Spätere Code-Updates: nur noch Schritt 1 (scripts/deploy.sh).
```

### 6.2 Variante B: manuell auf dem Pi

```bash
# 1. Pakete
sudo apt update
sudo apt install -y python3 python3-requests python3-yaml

# 2. Zielverzeichnisse + Systemuser
sudo useradd -r -s /usr/sbin/nologin notlicht || true
sudo install -d -m 0755 /opt/notlicht-monitor /etc/notlicht-monitor
sudo install -d -m 0750 -o notlicht -g notlicht /var/lib/notlicht-monitor

# 3. Code + systemd-Units
sudo install -m 0644 code/*.py /opt/notlicht-monitor/
sudo chmod 755 /opt/notlicht-monitor/main.py
sudo install -m 0644 systemd/notlicht-monitor.* /etc/systemd/system/
sudo systemctl daemon-reload

# 4. Haupt-Config (ohne Passwort)
sudo install -m 0600 -o notlicht -g notlicht config.yaml.example /etc/notlicht-monitor/config.yaml
sudo nano /etc/notlicht-monitor/config.yaml

# 5. Secrets (SMTP-Passwort getrennt)
sudo install -m 0600 -o notlicht -g notlicht secrets.yaml.example /etc/notlicht-monitor/secrets.yaml
sudo nano /etc/notlicht-monitor/secrets.yaml
```

Die apt-Pakete reichen vollständig — kein pip, kein venv. Der B+ hat zu wenig Dampf, um sich damit ohne Not zu quälen.

### 6.3 Testlauf

**Ohne Mailversand (Trockenlauf):**

```bash
sudo -u notlicht /usr/bin/python3 /opt/notlicht-monitor/main.py --dry-run --force-weekly
```

Erwartet: pro Anlage eine Logzeile (`OK` oder `STÖRUNG`), dazu ein kompletter Mail-Entwurf auf stdout.

**Mit Mailversand (echter Test an die konfigurierten Empfänger):**

```bash
sudo -u notlicht /usr/bin/python3 /opt/notlicht-monitor/main.py --force-weekly
```

### 6.4 systemd-Timer aktivieren

```bash
sudo systemctl enable --now notlicht-monitor.timer
```

Der Timer-Unit läuft **alle 15 Minuten** und holt nach einem Neustart verpasste Läufe automatisch nach (`Persistent=true`).

### 6.5 Betrieb prüfen

```bash
# Ist der Timer aktiv?
systemctl list-timers notlicht-monitor.timer

# Letzter Lauf:
systemctl status notlicht-monitor.service

# Live-Log:
journalctl -u notlicht-monitor.service -f

# Historie der letzten 200 Logzeilen:
journalctl -u notlicht-monitor.service -n 200 --no-pager
```

---

## 7. Konfiguration im Detail

### 7.1 Warum zwei Dateien: `config.yaml` vs. `secrets.yaml`

Die Konfiguration wird bewusst auf zwei Dateien aufgeteilt — beide im Verzeichnis `/etc/notlicht-monitor/`:

| Datei | Inhalt | Rechte |
|---|---|---|
| `config.yaml` | Alles **außer** Passwörtern — Anlagen, SMTP-Host, Empfänger, Texte, Zeitplan | `0600`, owner `notlicht` |
| `secrets.yaml` | Nur Passwörter / sensible Tokens | `0600`, owner `notlicht` |

Der Grund: `config.yaml` darf ohne Bedenken weitergegeben werden (Support, Backup, Versionskontrolle, Dokumentation). Nur `secrets.yaml` enthält wirklich schützenswerte Daten. Entsprechend ist `secrets.yaml` in der `.gitignore` ausgeschlossen, während `secrets.yaml.example` — eine leere Vorlage — getrackt wird.

Beim Start sucht das Programm automatisch nach `secrets.yaml` **neben** der Haupt-Config und merged sie drüber (`--secrets PATH` erlaubt abweichende Pfade). Fehlt die Datei, wird ohne Secrets gestartet — das ist erlaubt, aber für Produktion nicht empfohlen (Passwort stünde dann im Klartext in `config.yaml`).

### 7.2 Abschnitte in `config.yaml`

- **`devices`** — Liste der Anlagen (Name + URL).
  ```yaml
  devices:
    - name: "Anlage 1"
      url: "http://192.0.2.60"
    - name: "Anlage 2"
      url: "http://192.0.2.61"
  ```
- **`smtp`** — Mailserver-Zugang (Host, Port, SSL/STARTTLS, User, Absender). **Passwort bewusst nicht hier**, sondern in `secrets.yaml`.
- **`recipients`** — Verteilerliste (ein oder mehrere Empfänger).
- **`mail`** — Betreffvorlagen, Standardtext, eigener Einleitungstext, Fußtext.
- **`schedule`** — Wochentag (0=Montag) und Stunde des Reports.
- **`http`** — Timeout, Anzahl Versuche, Pausen zwischen Versuchen.

Die Vorlage `config.yaml.example` ist vollständig kommentiert.

### 7.3 Abschnitte in `secrets.yaml`

Aktuell nur:

```yaml
smtp:
  password: "DEIN_SMTP_PASSWORT_HIER"
```

Die Datei wird beim Start über `config.yaml` gemerged (Deep-Merge). Gleichnamige Felder in `secrets.yaml` gewinnen.

### 7.4 Mailtext anpassen

```yaml
mail:
  intro_text: |
    Wochenstatus der Sicherheitsbeleuchtung vom {date}.
    Anlagen wurden automatisch abgefragt.
  custom_intro_text: ""     # wenn gefüllt: ersetzt intro_text komplett
  custom_footer: ""         # wird ans Ende jeder Mail gehängt
```

Verfügbare Platzhalter in Textfeldern: `{date}`, `{datetime}`, `{device}`.

Änderungen greifen beim nächsten Lauf; kein Dienst-Neustart nötig.

### 7.5 TEST-Mail-Funktion (optional)

Wenn aktiviert, pollt das Tool bei jedem 15-Minuten-Lauf das Notlicht-Postfach via IMAP. Wer eine Mail mit Subject `TEST` (case-insensitive, ohne führende/nachlaufende Leerzeichen) an dieses Postfach schickt, bekommt **als Reply den aktuellen Status der Anlagen** zurück — inhaltlich identisch mit dem Wochenreport.

**Verhalten im Detail:**

- **Subject `TEST` von einem beliebigen Absender** → Eine Antwort an genau diesen Absender (mit gesetztem `In-Reply-To`-Header für sauberes Threading). Wenn die eingehende Mail einen `Reply-To`-Header hat, wird dieser bevorzugt — Standard-Mailverhalten.
- **Mehrere TEST-Mails desselben Absenders im selben Lauf** → Genau eine Antwort, alle weiteren Mails werden gelöscht (Reflection-/Flood-Schutz).
- **Anderes Subject** → Mail wird stillschweigend gelöscht. Es gibt **keine** „abgewiesen"-Bounce, weil das nur Spam-Backscatter erzeugen würde.
- **Verarbeitete Mails** werden aus dem Postfach gelöscht (`delete_processed: true`, Default), damit sie nicht beim nächsten Lauf erneut verarbeitet werden.
- Im **`--dry-run`** wird das Postfach gelesen und die geplante Antwort auf stdout gezeigt, aber **keine Mail gelöscht** — so kann eine TEST-Anfrage trockentestet werden, ohne sie zu konsumieren.

**Konfiguration** (in `config.yaml`):

```yaml
imap:
  enabled: true              # Default: false
  host: ""                   # leer = wie smtp.host
  port: 993
  use_ssl: true
  username: ""               # leer = wie smtp.username
  folder: "INBOX"
  test_subject: "TEST"
  delete_processed: true
```

Das **IMAP-Passwort** gehört nach `secrets.yaml`:

```yaml
imap:
  password: "DEIN_IMAP_PASSWORT_HIER"
```

Bei gleichem Account wie SMTP kann der ganze `imap`-Block in `secrets.yaml` weggelassen werden — `code/config.py` übernimmt dann automatisch `smtp.password`.

**Sicherheits-Hinweis (wichtig!):** Diese Funktion gibt Anlagenstati an *jeden* Absender zurück, der das richtige Subject trifft. Die Adresse des Postfachs ist damit eine kleine Disclosure-Quelle — IPs, Messwerte und Meldungstexte deiner Anlagen werden an Anfragende geschickt. Daher:

- Adresse nicht öffentlich verteilen (kein `mailto:`-Link auf Webseiten, keine Visitenkarten).
- Die Adresse möglichst nur Personen geben, die die Information ohnehin sehen dürften (z. B. Hausverwaltung, Wartungsdienst, Hausmeister).
- Wer das nicht will, lässt `imap.enabled: false` und nimmt stattdessen `--force-weekly` zum Testen.

**Dienst-Mailbox aufräumen, wenn TEST-Mode aktiviert wird:** beim ersten Lauf werden *alle* Mails im Postfach durchgegangen — sortiere also vorher manuell, falls dort noch alte Mails liegen, die nicht gelöscht werden sollen.

---

## 8. Betrieb & Wartung

```bash
# Status des Timers
systemctl list-timers notlicht-monitor.timer

# Live-Log
journalctl -u notlicht-monitor.service -f

# Manueller Lauf zum Testen
sudo systemctl start notlicht-monitor.service

# Wochenreport sofort senden (z. B. zum Testen)
sudo -u notlicht python3 /opt/notlicht-monitor/main.py --force-weekly

# State zurücksetzen: Anlagen als neue Baseline, keine fälschlichen Alarme
sudo rm /var/lib/notlicht-monitor/state.json
```

**Code-Update einspielen:**

```bash
# Von der Workstation aus
scripts/deploy.sh
```

`deploy.sh` überschreibt `/etc/notlicht-monitor/config.yaml` und `secrets.yaml` **nicht** — eure Produktiv-Config bleibt bei Updates unangetastet.

**Mailtext ändern:**

```bash
sudo nano /etc/notlicht-monitor/config.yaml
```

Greift beim nächsten 15-Minuten-Tick automatisch.

---

## 9. Kommandozeilenparameter

| Parameter | Wirkung |
|---|---|
| `--config PATH` | Abweichende Config-Datei (Default `/etc/notlicht-monitor/config.yaml`) |
| `--secrets PATH` | Abweichende Secrets-Datei (Default: `secrets.yaml` neben der Config) |
| `--state PATH` | Abweichende State-Datei (Default `/var/lib/notlicht-monitor/state.json`) |
| `--force-weekly` | Wochenreport jetzt senden, unabhängig vom Zeitplan |
| `--dry-run` | Mails nicht senden, nur auf stdout ausgeben. IMAP wird gelesen, aber das Postfach nicht geleert. |
| `--skip-imap` | IMAP-Inbox in diesem Lauf gar nicht abfragen (unabhängig von `imap.enabled`) |

---

## 10. Anforderungen

### 10.1 Zweck und Umfeld

Automatische, wiederkehrende Zustandsprüfung von drei Sicherheitsbeleuchtungsanlagen (Hersteller **GFS**, Modell **NETLIGHT quattro**, Firmware V6.0). Ergebnisse werden per E-Mail an einen konfigurierbaren Verteiler gemeldet.

| Punkt | Wert |
|---|---|
| Anzahl zu überwachender Anlagen | 3 |
| Anlagen-Webserver | Apache 2.2.22 / PHP 5.4.45 (Debian 7) |
| Anlagen-Auth | keine (offene Weboberfläche) |
| Datenformat der Anlagen | JSON-Arrays über drei POST-Endpoints |
| Monitor-Host | Raspberry Pi 1 B+ (2014), ARMv6l, 512 MB RAM |
| Betriebssystem | Raspberry Pi OS Lite Bookworm/Trixie (32-bit) |
| Netz | Alle Anlagen im selben LAN wie der Pi |

### 10.2 Funktionale Anforderungen

**Datenerfassung**

- **FA-1**: Das System fragt pro Anlage drei AJAX-Endpoints ab:
  - `POST /ajax_anlagenstatus.php` → Statusarray (10 Elemente, relevant 0, 1, 2, 3, 4, 6)
  - `POST /ajax_messwerte.php` → Messwertarray (6 Elemente, relevant 0, 3, 4, 5)
  - `POST /ajax_meldungen.php` mit Body `para1=start` → Meldungen als HTML-Schnipsel
- **FA-2**: Kein HTML-Parsing der Visualisierungsseite; die Rohdaten kommen direkt aus den AJAX-Endpoints.
- **FA-3**: Bei Netz- oder HTTP-Fehler wird der Abruf pro Endpoint wiederholt. Standard: 3 Versuche mit Pausen 10 s / 30 s / 60 s. Timeout pro Versuch: 10 s.
- **FA-4**: Scheitert ein Endpoint nach allen Versuchen, gilt die Anlage als „nicht erreichbar" — das ist ein Störungszustand.

**Statusbewertung**

- **FA-5**: Eine Anlage gilt als **OK**, wenn alle folgenden Bedingungen zutreffen:
  - Statusindex 0 (Betrieb) = `green`
  - Statusindex 1 (Netzbetrieb) = `green`
  - Statusindex 2 (Batteriebetrieb) = leer
  - Statusindex 3 (Sammelstörung) = leer
  - Statusindex 4 (Tiefentladung) = leer
  - Statusindex 6 (Testbetrieb) = leer
- **FA-6**: Jede Abweichung erzeugt eine Einzelmeldung im Mailtext (Bezeichnung + tatsächlicher Wert).
- **FA-7**: Messwerte werden roh übernommen, mit Einheiten formatiert (V, Ah, A). Bei Index 5 (Ladestrom): negative Werte werden als „Entladestrom" bezeichnet (Originalverhalten der Visualisierung).
- **FA-8**: Inhalt des Meldungsfeldes wird ausgelesen. HTML wird zu Plaintext konvertiert. Leeres Array → „(keine Meldungen)".

**Zeitsteuerung und Mailtypen**

- **FA-9**: **Wöchentlicher Statusreport** — einmal pro Woche am konfigurierten Wochentag (Default: Montag) ab der konfigurierten Stunde (Default: 07:00) an alle Empfänger.
- **FA-10**: **Sofort-Alarm** — Wechsel einer Anlage von OK nach Störung erzeugt umgehend eine Alarmmail für diese Anlage.
- **FA-11**: **Entwarnung** — Wechsel einer Anlage von Störung nach OK erzeugt eine Entwarnungsmail.
- **FA-12**: Während eine Störung durchgehend besteht, wird **keine weitere Alarmmail** verschickt (kein Spam). Erst bei Rückkehr zu OK und erneuter Störung gibt es wieder eine Alarmmail.
- **FA-13**: Beim allerersten Lauf nach Installation oder nach Zurücksetzen des State wird keine Mail erzeugt; der aktuelle Zustand gilt als Baseline.
- **FA-14**: In derselben Kalenderwoche wird der Wochenreport maximal einmal regulär versendet, auch wenn das Tool öfter läuft.

**E-Mail**

- **FA-15**: Versand via SMTP mit SSL/TLS auf Port 465 (konfigurierbar auf STARTTLS/587).
- **FA-16**: Empfänger: frei konfigurierbare Liste.
- **FA-17**: Betreff enthält ein Statusemoji: 🟢 bei gesamt-OK, 🔴 bei mindestens einer Störung.
- **FA-18**: Betreffvorlagen für die drei Mailtypen sind in der Config definierbar (mit Platzhaltern `{status_emoji}`, `{date}`, `{device}`).
- **FA-19**: Mailinhalt ist Plaintext und enthält pro Anlage:
  - Name und URL
  - Gesamtstatus (OK / STÖRUNG / NICHT ERREICHBAR)
  - Alle sechs Statuspositionen
  - Messwerte (Netzspannung, Batteriespannung, Batteriekapazität, Lade-/Entladestrom)
  - Inhalt des Meldungsfeldes
  - Liste der Abweichungen (nur bei Störung)
- **FA-20**: Mailsprache: Deutsch.
- **FA-21**: Der **Standard-Einleitungstext** ist in der Config hinterlegt und editierbar.
- **FA-22**: **Eigener Einleitungstext** — wenn der Benutzer einen eigenen Text hinterlegt, ersetzt dieser den Standardtext komplett.
- **FA-23**: Optionaler freier Fußtext kann an jede Mail angehängt werden.

**Konfiguration**

- **FA-24**: Alle veränderlichen Parameter liegen in externen YAML-Dateien.
- **FA-25**: Die Konfiguration enthält: Anlagen, SMTP-Daten, Empfängerverteiler, Betreffvorlagen/Texte, Zeitplan, HTTP-Timeout- und Retry-Parameter.
- **FA-26**: Passwörter liegen separat in `secrets.yaml`. Beide Dateien sind mit `0600` / Owner `notlicht` abzusichern.

**Protokollierung**

- **FA-27**: Jeder Lauf schreibt eine Logzeile pro Anlage in das systemd-Journal (Status OK/Störung, Details zu Abweichungen, HTTP-Fehler mit Versuchszähler).
- **FA-28**: Logs sind per `journalctl -u notlicht-monitor.service` einsehbar, mit Rotation über die systemd-Defaults.

### 10.3 Nicht-funktionale Anforderungen

- **NF-1**: Lauffähig auf Raspberry Pi 1 B+ (ARMv6, 512 MB RAM) mit Standard-apt-Python-Stack; keine pip-/venv-Installation nötig.
- **NF-2**: Abhängigkeiten ausschließlich aus Python-Standardbibliothek plus `python3-requests` und `python3-yaml` (beide als apt-Pakete verfügbar).
- **NF-3**: Robust gegen temporäre Netzfehler (siehe FA-3).
- **NF-4**: Robust gegen Neustarts/Stromausfall — verpasste Läufe werden durch systemd-Timer mit `Persistent=true` nachgeholt.
- **NF-5**: Der laufende Prozess verwendet einen dedizierten Systembenutzer ohne Login-Shell (`notlicht`).
- **NF-6**: Der Monitor darf die Anlagen nicht beeinträchtigen — er ruft nur lesende AJAX-Endpoints auf, löst keine Testläufe aus und sendet keine Fernsteuerungsbefehle.

### 10.4 Abgrenzung

Ausdrücklich nicht im Projektumfang:

- Keine Bedienung (Leuchtentest, Funktionstest, Fernsteuerung) — nur Lesen.
- Kein Dashboard, keine Weboberfläche auf dem Pi.
- Kein Export in externe Monitoring-Systeme (MQTT, Prometheus, etc.).
- Kein Alarmversand per SMS oder Push — ausschließlich E-Mail.
- Die Absicherung der Anlagen selbst (Netzsegmentierung, Firewall) liegt außerhalb des Projekts, wird aber dringend empfohlen (veralteter Apache/PHP-Stack).

### 10.5 Annahmen

- **A-1**: Das Format der AJAX-Antworten ist über alle Anlagen identisch. Verifiziert für das getestete Exemplar am 24.04.2026.
- **A-2**: Die AJAX-Endpoints sind ohne Session-Cookie nutzbar. Verifiziert per curl-Test.
- **A-3**: Die Anlagen liefern konsistente Status-Codes (`green`, `yellow`, `red`, leer). Aus Seitencode abgeleitet.
- **A-4**: Der eigene Mailserver akzeptiert SMTP-SSL-Einlieferung auf Port 465.

---

## 11. Technische Beschreibung

### 11.1 Überblick & Architektur

Stateful Python-Batchjob, alle 15 Minuten von einem systemd-Timer gestartet. Der Job fragt drei NETLIGHT-Anlagen via HTTP-POST-AJAX ab, bewertet den Zustand, vergleicht mit dem persistierten Vorzustand und entscheidet selbständig, ob und welche E-Mail versendet wird. Rückgabe- und Log-Informationen gehen ins systemd-Journal.

```
┌────────────────────────────────────────────────────────────┐
│ systemd-Timer (alle 15 min, Persistent=true)               │
└──────────────────────────┬─────────────────────────────────┘
                           │ startet
                           ▼
┌────────────────────────────────────────────────────────────┐
│ notlicht-monitor.service (oneshot, user: notlicht)         │
│   python3 /opt/notlicht-monitor/main.py                    │
└──────────────────────────┬─────────────────────────────────┘
                           │
        ┌──────────────────┼───────────────────┐
        ▼                  ▼                   ▼
  ┌─────────┐        ┌──────────┐       ┌──────────┐
  │ config  │        │ netlight │       │ state    │
  │ + secr. │        │ _client  │       │ .json    │
  └─────────┘        └──────────┘       └──────────┘
                           │                   │
                           ▼                   ▼
                     ┌──────────┐       ┌──────────┐
                     │ evaluator│       │ diff     │
                     │ (in Snap)│       │ (Alarm / │
                     └──────────┘       │ Entwarn.)│
                           │            └──────────┘
                           │                   │
                           └────────┬──────────┘
                                    ▼
                              ┌──────────┐
                              │ mail_    │───► SMTP-Server (465/SSL)
                              │ builder  │     (eigener Mailserver)
                              │ + mailer │
                              └──────────┘
```

### 11.2 Modulübersicht

| Modul | Zeilen | Aufgabe |
|---|---|---|
| `main.py` | ~160 | Orchestrator. Lädt Config + State, iteriert Geräte, entscheidet über Mailversand, schreibt State zurück. Einziges Binary. |
| `netlight_client.py` | ~140 | HTTP-Kommunikation mit einer Anlage. Retry-Logik. Produziert `DeviceSnapshot` inkl. OK-Bewertung und Abweichungsliste. Sprechende Fehlermeldungen für die Mail. |
| `state.py` | ~60 | Persistenz des letzten bekannten Status pro Gerät sowie des letzten Wochenreport-Zeitstempels. Atomares Schreiben via `tmp`-Datei + `replace`. |
| `mailer.py` | ~70 | Dünner SMTP-Wrapper um `smtplib`. Unterstützt SMTPS (465) und STARTTLS, optionale Reply-Header. |
| `mail_builder.py` | ~150 | Plaintext-Mailbodies für die vier Mailtypen (inkl. TEST-Antwort). HTML-Decoding der Meldungen via `html.parser`. |
| `imap_handler.py` | ~140 | Optionale IMAP-Inbox-Verarbeitung für die `TEST`-Mail-Funktion. Subject-Decode, Pro-Lauf-Dedup, sichere Mail-Löschung. |
| `config.py` | ~110 | YAML laden, Defaults mergen, `secrets.yaml` überlagern, Pflichtfelder prüfen, IMAP-Defaults von SMTP übernehmen. |

**Gesamtumfang:** ca. 760 Zeilen Python ohne Kommentare. Keine eigenen Frameworks, keine Web-/DB-Abhängigkeiten.

### 11.3 Datenfluss pro Lauf

1. **Config laden** (`/etc/notlicht-monitor/config.yaml`) → validiertes `dict`. Daneben ggf. `secrets.yaml` drübermergen.
2. **State laden** (`/var/lib/notlicht-monitor/state.json`) → `State`-Objekt, enthält `last_weekly_report` und `devices[name].was_ok`.
3. **Iteration über Geräte**:
    1. Drei POST-Requests pro Gerät.
    2. Bei Fehler: Retry gemäß Config, dann `reachable=False`.
    3. Ergebnis landet in `DeviceSnapshot` mit abgeleiteten Properties `is_ok` und `abweichungen`.
4. **Diff-Entscheidung pro Gerät**:
    - `prev=None` → Baseline setzen, keine Mail.
    - `prev=True, now=False` → Alarmmail.
    - `prev=False, now=True` → Entwarnungsmail.
    - sonst → keine Mail.
    - State pro Gerät wird unabhängig vom Mailversand aktualisiert.
5. **Wochenreport-Prüfung**: `should_send_weekly()` liefert True, wenn heute der konfigurierte Wochentag ist, die aktuelle Stunde ≥ konfigurierter Stunde, und der letzte Wochenreport nicht in derselben ISO-Kalenderwoche liegt. Oder wenn `--force-weekly` gesetzt ist.
6. **Mailversand** jeweils über eine lokale `send()`-Funktion, die im Dry-Run-Modus nur auf stdout druckt.
7. **State persistieren** (atomar).
8. **Exit-Code**: `0` falls alle Geräte OK, sonst `1`. systemd ist so konfiguriert, dass Exit `1` kein Dienstfehler ist (`SuccessExitStatus=0 1`).

### 11.4 NETLIGHT-Endpoints und Datenmodell

#### `POST /ajax_anlagenstatus.php`

**Response** (Beispiel):
```json
["green","green","","","","","","","",""]
```

Das UI (`index.php`) rendert die Indizes auf HTML-Elemente `s1..s7`, wobei Index 5 nicht im HTML existiert und Index 6 auf „Testbetrieb" (`s7`) geht. Relevante Indizes:

| Idx | Bedeutung | Erwartet | Klassen-Werte |
|---|---|---|---|
| 0 | Betrieb | `green` | `green` / leer |
| 1 | Netzbetrieb | `green` | `green` / `yellow` / leer |
| 2 | Batteriebetrieb | leer | `yellow` / leer |
| 3 | Sammelstörung | leer | `red` / `yellow` / leer |
| 4 | Tiefentladung | leer | `red` / leer |
| 6 | Testbetrieb | leer | `yellow` / leer |

Quelle: JavaScript in `index.php` setzt `class` auf `green|yellow|red`, CSS färbt entsprechend.

#### `POST /ajax_messwerte.php`

**Response:**
```json
["231","0","0","27.1","36","0.8"]
```

| Idx | Bedeutung | Einheit |
|---|---|---|
| 0 | Netzspannung | V |
| 1 | (nicht verwendet) | — |
| 2 | (nicht verwendet) | — |
| 3 | Batteriespannung | V |
| 4 | Batteriekapazität | Ah |
| 5 | Lade- / Entladestrom | A (negativ = Entladung) |

#### `POST /ajax_meldungen.php` mit Body `para1=start`

**Response:**
```json
[]
```
oder
```json
["<p>Sammelstoerung: Unterspannung Batterie</p>"]
```

HTML-Schnipsel werden client-seitig konkateniert. Der Monitor flacht das Array über `"".join(...)` und extrahiert Text via `html.parser.HTMLParser`, Whitespace wird normalisiert.

### 11.5 Entscheidungslogik Mailversand

```
FÜR JEDES Gerät:
    snap ← fetch_data()
    prev ← state.was_ok(name)
    state.update_device(name, snap.is_ok)

    WENN prev ist None:
        ▸ kein Mailversand (Baseline)
    SONST WENN prev=True  UND snap.is_ok=False:
        ▸ Alarmmail "🔴 ALARM"
    SONST WENN prev=False UND snap.is_ok=True:
        ▸ Entwarnungsmail "🟢 Entwarnung"

NACH ALLEN GERÄTEN:
    WENN should_send_weekly():
        ▸ Wochenreport mit allen Geräten
        ▸ state.set_weekly_report_sent(now)
```

### 11.6 State-Schema

Datei `/var/lib/notlicht-monitor/state.json`:

```json
{
  "last_weekly_report": "2026-04-24T16:07:15.123456+02:00",
  "devices": {
    "Anlage 1": {
      "was_ok": true,
      "last_check": "2026-04-24T16:22:00.000000+02:00"
    }
  }
}
```

Geschrieben atomar: `state.tmp` → `replace()` → `state.json`. Damit kann das Tool während des Schreibens nicht zu inkonsistentem State führen.

### 11.7 Deployment-Layout

```
/opt/notlicht-monitor/          # Code, read-only für Dienst
├── main.py
├── netlight_client.py
├── mail_builder.py
├── mailer.py
├── state.py
└── config.py

/etc/notlicht-monitor/
├── config.yaml                  # 0600, owner: notlicht
└── secrets.yaml                 # 0600, owner: notlicht

/var/lib/notlicht-monitor/
└── state.json                   # 0600, owner: notlicht

/etc/systemd/system/
├── notlicht-monitor.service
└── notlicht-monitor.timer
```

### 11.8 Fehlerklassen und Reaktionen

| Fehler | Erkannt in | Reaktion |
|---|---|---|
| `ConnectionError`, `Timeout` | `netlight_client._post` | Retry nach Backoff (10/30/60 s), danach `reachable=False` → Gerät zählt als Störung. Fehlerbeschreibung in die Mail geht sprechend (z. B. „Gerät antwortet nicht (Timeout 10 s)"), Technik-Details nur ins Log. |
| HTTP 4xx/5xx | `raise_for_status` | identisch, Mail-Meldung: „Gerät antwortet mit Fehler-Status HTTP 500" |
| Ungültiges JSON | `Response.json()` | identisch, Mail-Meldung: „Antwort konnte nicht ausgewertet werden" |
| Unerwartete Array-Länge | `DeviceSnapshot.is_ok` | Gerät zählt als Störung, Abweichung wird geloggt |
| Mailversand-Fehler | `mailer.send` | Exception wird geloggt, State wird dennoch persistiert; nächster Lauf versucht nicht nachzusenden (bewusst, siehe FA-13). |
| State-Datei korrupt | `State._load` | Warnung im Log, Start mit leerem State = alle Geräte als „erstmalig gesehen" (keine Mail) |

### 11.9 Leistung und Laufzeit

Typischer Lauf auf Pi 1 B+ mit drei Anlagen im lokalen LAN:

- HTTP-Requests: 3 Anlagen × 3 Endpoints = 9 Requests, sequentiell.
- LAN-Latenz pro Request: < 100 ms, JSON winzig → Gesamt < 2 s im Normalfall.
- Bei einer nicht erreichbaren Anlage: 3 × Timeout (10 s) + 2 Backoffs (10 s + 30 s) = bis zu ~70 s.
- Bei drei nicht erreichbaren Anlagen (worst case): ~210 s ≈ 3,5 min.
- Der 15-Minuten-Timer hat genug Puffer.

### 11.10 Erweiterungspunkte

Falls später gewünscht — aktuell bewusst nicht im Scope:

- Anderer Transport (MQTT, Webhook) → zusätzlicher Sender analog zu `mailer.py`.
- Tägliche statt wöchentlicher Reports → neuer Schedule-Block in Config, `should_send_*` leicht erweitern.
- HTML-Mails statt Plaintext → `EmailMessage.add_alternative()` im `mailer.py`.
- Mehr als drei Anlagen → einfach in `devices:` eintragen, kein Code-Change.

---

## 12. Sicherheitshinweise

Die NETLIGHT-Anlagen laufen auf einem sehr alten Software-Stack (Apache 2.2 / PHP 5.4 auf Debian 7). Diese Geräte sollten:

- **niemals direkt aus dem Internet erreichbar sein**,
- idealerweise in einem separaten Management-VLAN stehen,
- nur vom Monitor-Pi angesprochen werden.

Der Monitor greift ausschließlich **lesend** zu. Er kann weder Tests auslösen noch Einstellungen ändern. Das Passwort des Mailaccounts liegt im Klartext in `secrets.yaml`, geschützt durch Dateirechte (`0600`) und den dedizierten Systemuser `notlicht`. Für diesen Einsatzfall ist das angemessen; höhere Sicherheitsstufen (Secret-Store, Vault) sind nicht vorgesehen, wären aber erweiterbar.

Logs enthalten kein Passwort. Bei Fehlern werden die vollständigen URLs der Anlagen geloggt.

---

## 13. Verhaltensmatrix

| Situation | Reaktion |
|---|---|
| Erster Lauf nach Installation | Status als Baseline speichern, **keine Mail** |
| Gerät OK → bleibt OK | keine Mail (außer Wochenreport) |
| Gerät OK → Störung | sofortige **Alarm-Mail** |
| Gerät Störung → Störung | keine weitere Mail (**kein Spam**) |
| Gerät Störung → OK | **Entwarnungs-Mail** |
| Gerät nicht erreichbar (nach 3 Retries) | zählt als Störung |
| Montag 07:00+ (per Default) | **Wochenreport** mit allen Details |
| Pi war aus zur geplanten Mailzeit | Report wird nach Boot nachgeholt (`Persistent=true`) |
| State-Datei gelöscht oder korrupt | Neustart mit leerem State, keine fälschlichen Alarme |
| Mailserver temporär offline | Fehler wird geloggt, Mails werden **nicht** nachgeholt |
| IMAP aktiv, eingehende `TEST`-Mail | Eine Antwort an den Absender, Original wird gelöscht |
| IMAP aktiv, mehrere `TEST`-Mails desselben Absenders im selben Lauf | Genau eine Antwort, alle weiteren werden stillschweigend gelöscht |
| IMAP aktiv, Mail mit anderem Subject | Stillschweigende Löschung, keine Bounce |
| IMAP aktiv, IMAP-Server offline | Fehler wird geloggt, normaler Lauf läuft trotzdem durch |

---

## 14. Lizenz & Haftungsausschluss

**Copyright (C) 2026 Axel Schmidt**

Dieses Projekt steht unter einer **nicht-kommerziellen Nutzungslizenz** („Notlicht-Monitor Non-Commercial License"). Der vollständige Lizenztext liegt in der Datei [`LICENSE`](LICENSE) bei.

**Kurzfassung:**

- **Nicht-kommerzielle Nutzung ist frei gestattet** — inklusive Nutzung, Kopie, Änderung und Weitergabe. Dazu zählt insbesondere die Nutzung durch den Betreiber einer Immobilie zur Überwachung eigener Notlichtanlagen sowie die private, ausbildungsbezogene, wissenschaftliche oder gemeinnützige Nutzung.
- **Kommerzielle Nutzung** (z. B. durch einen Wartungsdienstleister, der das Monitoring seinen Kunden in Rechnung stellt) bedarf der **vorherigen schriftlichen Zustimmung** des Autors. Anfragen bitte als Issue im GitHub-Repository.
- Bei jeder Weitergabe muss dieser Hinweis einschließlich Copyright erhalten bleiben.

### Haftungsausschluss

Diese Software wird „wie sie ist" bereitgestellt, **ohne jegliche Gewährleistung** — weder ausdrücklich noch stillschweigend.

### ⚠️ Besonderer Hinweis zur Sicherheitsrelevanz

Eine **Notlichtanlage ist eine sicherheitsrelevante Einrichtung des vorbeugenden Brandschutzes**. Diese Software ist **ausschließlich ein zusätzliches informationelles Monitoring**. Sie

> **ERSETZT AUSDRÜCKLICH NICHT**

die gesetzlich vorgeschriebenen Prüfungen durch Fachpersonal nach

- **DIN EN 50172 / DIN VDE 0108-100**
- **DIN EN 50171**
- **DIN VDE 0100-560**
- **DGUV Vorschrift 3**
- **ArbStättV § 4 Abs. 3 und Anhang 2.3**
- weiteren einschlägigen Normen und örtlichen Bestimmungen.

Die **Verantwortung für die ordnungsgemäße Funktion, Wartung, Prüfung und Dokumentation** der Anlage verbleibt vollumfänglich beim **Betreiber**. Der Autor übernimmt **keinerlei Haftung** für Schäden, die aus der Nutzung dieser Software, aus fehlerhaften oder ausbleibenden Meldungen, aus falsch konfigurierten Empfängern oder aus anderen Ursachen im Zusammenhang mit der Software entstehen.

Wer dieses Tool einsetzt, tut dies in eigener Verantwortung und **zusätzlich**, nicht **anstelle** der normgerechten Wartung.

---

## 15. Autor

**Axel Schmidt**

Rückfragen, Fehlerberichte und Anfragen für kommerzielle Nutzung bitte als Issue im Repository:
[`github.com/a-schmidtlab/emergency-light-monitoring/issues`](https://github.com/a-schmidtlab/emergency-light-monitoring/issues)

---

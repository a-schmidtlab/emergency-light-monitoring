# Anforderungskatalog – Notlicht-Monitor

Version 1.0 · 24.04.2026 · Ableitung aus der Projekt-Konversation.

## 1. Zweck

Automatische, wiederkehrende Zustandsprüfung von drei Sicherheits­beleuchtungs­anlagen (Hersteller GFS, Modell NETLIGHT quattro, Firmware V 6.0). Ergebnisse werden per E-Mail an einen konfigurierbaren Verteiler gemeldet.

## 2. Umfeld

| Punkt | Wert |
|---|---|
| Anzahl zu überwachender Anlagen | 3 |
| Anlagen-Webserver | Apache 2.2.22 / PHP 5.4.45 (Debian 7) |
| Anlagen-Auth | keine (offene Weboberfläche) |
| Datenformat der Anlagen | JSON-Arrays über drei POST-Endpoints |
| Monitor-Host | Raspberry Pi 1 B+ (2014), ARMv6l, 512 MB RAM |
| Betriebssystem | Raspberry Pi OS Lite Bookworm (32-bit) |
| Netz | Alle drei Anlagen im selben LAN wie der Pi |

## 3. Funktionale Anforderungen

### 3.1 Datenerfassung

- **FA-1**: Das System fragt pro Anlage drei AJAX-Endpoints ab:
  - `POST /ajax_anlagenstatus.php` → Statusarray (10 Elemente, relevant 0,1,2,3,4,6)
  - `POST /ajax_messwerte.php` → Messwertarray (6 Elemente, relevant 0,3,4,5)
  - `POST /ajax_meldungen.php` mit `para1=start` → Meldungen als HTML-Schnipsel
- **FA-2**: Kein HTML-Parsing der Visualisierungsseite; die Rohdaten kommen direkt aus den AJAX-Endpoints.
- **FA-3**: Bei Netz- oder HTTP-Fehler wird der Abruf pro Endpoint wiederholt. Standard: 3 Versuche mit Pausen 10 s / 30 s / 60 s. Timeout pro Versuch: 10 s.
- **FA-4**: Scheitert ein Endpoint nach allen Versuchen, gilt die Anlage als „nicht erreichbar" – das ist ein Störungszustand.

### 3.2 Statusbewertung

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

### 3.3 Zeitsteuerung und Mailtypen

- **FA-9**: **Wöchentlicher Statusreport** – Einmal pro Woche am konfigurierten Wochentag (Default: Montag) ab der konfigurierten Stunde (Default: 07:00) wird ein Gesamtreport an alle Empfänger verschickt.
- **FA-10**: **Sofort-Alarm** – Wechselt eine Anlage von „OK" nach „Störung", wird umgehend eine Alarmmail für diese Anlage verschickt.
- **FA-11**: **Entwarnung** – Wechselt eine Anlage von „Störung" nach „OK", wird eine Entwarnungsmail verschickt.
- **FA-12**: Während eine Störung durchgehend besteht, wird **keine weitere Alarmmail** verschickt (kein Spam). Erst bei Rückkehr zu OK und erneuter Störung gibt es wieder eine Alarmmail.
- **FA-13**: Beim allerersten Lauf nach Installation oder nach Zurücksetzen des State wird keine Mail erzeugt; der aktuelle Zustand gilt als Baseline.
- **FA-14**: In derselben Kalenderwoche wird der Wochenreport maximal einmal regulär versendet, auch wenn das Tool öfter läuft.

### 3.4 E-Mail

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
- **FA-22**: **Eigener Einleitungstext** – Wenn der Benutzer einen eigenen Text hinterlegt, **ersetzt** dieser den Standardtext komplett (ausdrückliche Anforderung).
- **FA-23**: Optionaler freier Fußtext kann an jede Mail angehängt werden.

### 3.5 Konfiguration

- **FA-24**: Alle veränderlichen Parameter liegen in einer externen Config-Datei (YAML).
- **FA-25**: Die Config enthält:
  - Liste der zu prüfenden Anlagen (Name + URL)
  - SMTP-Daten (Host, Port, SSL-Modus, User, Passwort, Absender)
  - Empfängerverteiler
  - Betreffvorlagen, Standardtext, eigener Einleitungstext, Fußtext
  - Zeitplan (Wochentag, Stunde)
  - HTTP-Timeout und Retry-Parameter
- **FA-26**: Die Config-Datei ist wegen des SMTP-Passworts mit Dateirechten 600 zu schützen.

### 3.6 Protokollierung

- **FA-27**: Jeder Lauf schreibt eine Logzeile pro Anlage in das systemd-Journal (Status OK/Störung, Details zu Abweichungen, HTTP-Fehler mit Versuchszähler).
- **FA-28**: Logs sind per `journalctl -u notlicht-monitor.service` einsehbar, mit Rotation über die systemd-Defaults.

## 4. Nicht-funktionale Anforderungen

- **NF-1**: Lauffähig auf Raspberry Pi 1 B+ (ARMv6, 512 MB RAM) mit Standard-apt-Python-Stack; keine pip-/venv-Installation nötig.
- **NF-2**: Abhängigkeiten ausschließlich aus Python-Standardbibliothek plus `python3-requests` und `python3-yaml` (beide als apt-Pakete verfügbar).
- **NF-3**: Robust gegen temporäre Netzfehler (siehe FA-3).
- **NF-4**: Robust gegen Neustarts/Stromausfall – verpasste Läufe werden durch systemd-Timer mit `Persistent=true` nachgeholt.
- **NF-5**: Der laufende Prozess verwendet einen dedizierten Systembenutzer ohne Login-Shell (`notlicht`).
- **NF-6**: Der Monitor darf die Anlagen nicht beeinträchtigen – er ruft nur lesende AJAX-Endpoints auf, löst keine Testläufe aus und sendet keine Fernsteuerungsbefehle.

## 5. Abgrenzung (ausdrücklich nicht im Projektumfang)

- Keine Bedienung (Leuchtentest, Funktionstest, Fernsteuerung) – nur Lesen.
- Kein Dashboard, keine Weboberfläche auf dem Pi.
- Kein Export in externe Monitoring-Systeme (MQTT, Prometheus, etc.).
- Kein Alarmversand per SMS oder Push – ausschließlich E-Mail.
- Die Absicherung der Anlagen selbst (Netzsegmentierung, Firewall) liegt außerhalb des Projekts, wird aber dringend empfohlen (veralteter Apache/PHP-Stack).

## 6. Annahmen

- **A-1**: Das Format der AJAX-Antworten ist über alle drei Anlagen identisch. Verifiziert für 192.168.178.60 am 24.04.2026.
- **A-2**: Die AJAX-Endpoints sind ohne Session-Cookie nutzbar. Verifiziert per curl-Test.
- **A-3**: Die Anlagen liefern konsistente Status-Codes (`green`, `yellow`, `red`, leer). Aus Seitencode abgeleitet.
- **A-4**: Der eigene Mailserver akzeptiert SMTP-SSL-Einlieferung auf Port 465.

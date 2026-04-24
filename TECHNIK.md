# Technische Beschreibung – Notlicht-Monitor

Version 1.0 · 24.04.2026

## 1. Überblick

Stateful Python-Batchjob, alle 15 Minuten von einem systemd-Timer gestartet. Der Job fragt drei NETLIGHT-Anlagen via HTTP-POST-AJAX ab, bewertet den Zustand, vergleicht mit dem persistierten Vorzustand und entscheidet selbständig, ob und welche E-Mail versendet wird. Rückgabe- und Log-Informationen gehen ins systemd-Journal.

```
┌────────────────────────────────────────────────────────────┐
│ systemd-Timer (alle 15 min, Persistent=true)              │
└──────────────────────────┬─────────────────────────────────┘
                           │ startet
                           ▼
┌────────────────────────────────────────────────────────────┐
│ notlicht-monitor.service (oneshot, user: notlicht)        │
│   python3 /opt/notlicht-monitor/main.py                   │
└──────────────────────────┬─────────────────────────────────┘
                           │
        ┌──────────────────┼───────────────────┐
        ▼                  ▼                   ▼
  ┌─────────┐        ┌──────────┐       ┌──────────┐
  │ config  │        │ netlight │       │ state    │
  │ .yaml   │        │ _client  │       │ .json    │
  └─────────┘        └──────────┘       └──────────┘
                           │                   │
                           ▼                   ▼
                     ┌──────────┐       ┌──────────┐
                     │ evaluator│       │ diff     │
                     │ (in Snap)│       │ (Alarm/  │
                     └──────────┘       │ Entwarn.)│
                           │           └──────────┘
                           │                   │
                           └────────┬──────────┘
                                    ▼
                              ┌──────────┐
                              │ mail_    │───► SMTP-Server (465/SSL)
                              │ builder  │     (eigener Mailserver)
                              │ + mailer │
                              └──────────┘
```

## 2. Modulübersicht

| Modul | Zeilen | Aufgabe |
|---|---|---|
| `main.py` | ~160 | Orchestrator. Lädt Config + State, iteriert Geräte, entscheidet über Mailversand, schreibt State zurück. Einziges Binary. |
| `netlight_client.py` | ~130 | HTTP-Kommunikation mit einer Anlage. Retry-Logik. Produziert `DeviceSnapshot` inkl. OK-Bewertung und Abweichungsliste. |
| `state.py` | ~60 | Persistenz des letzten bekannten Status pro Gerät sowie des letzten Wochenreport-Zeitstempels. Atomares Schreiben via `tmp`-Datei + `replace`. |
| `mailer.py` | ~50 | Dünner SMTP-Wrapper um `smtplib`. Unterstützt SMTPS (Port 465) und STARTTLS. |
| `mail_builder.py` | ~130 | Plaintext-Mailbodies für die drei Mailtypen. HTML-Decoding der Meldungen via `html.parser`. |
| `config.py` | ~70 | YAML laden, Defaults mergen, Pflichtfelder prüfen. |

**Gesamtumfang:** ca. 600 Zeilen Python ohne Kommentare. Keine eigenen Frameworks, keine Web-/DB-Abhängigkeiten.

## 3. Datenfluss pro Lauf

1. **Config laden** (`/etc/notlicht-monitor/config.yaml`) → validiertes dict.
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

## 4. NETLIGHT-Endpoints – Datenmodell

### 4.1 `POST /ajax_anlagenstatus.php`

**Response** (Beispiel aus 192.168.178.60):
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

### 4.2 `POST /ajax_messwerte.php`

**Response:**
```json
["231","0","0","27.1","36","0.8"]
```

| Idx | Bedeutung | Einheit |
|---|---|---|
| 0 | Netzspannung | V |
| 1 | (nicht verwendet) | – |
| 2 | (nicht verwendet) | – |
| 3 | Batteriespannung | V |
| 4 | Batteriekapazität | Ah |
| 5 | Lade- / Entladestrom | A (negativ = Entladung) |

### 4.3 `POST /ajax_meldungen.php` mit Body `para1=start`

**Response:**
```json
[]                                                // keine Meldungen
["<p>Sammelstoerung: Unterspannung Batterie</p>"] // eine Meldung
```

HTML-Schnipsel werden client-seitig konkateniert. Der Monitor flacht das Array über `"".join(...)` und extrahiert Text via `html.parser.HTMLParser`, Whitespace wird normalisiert.

## 5. Entscheidungslogik Mailversand

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

## 6. State-Schema

Datei `/var/lib/notlicht-monitor/state.json`:

```json
{
  "last_weekly_report": "2026-04-24T16:07:15.123456+02:00",
  "devices": {
    "Anlage 1 - Treppenhaus": {
      "was_ok": true,
      "last_check": "2026-04-24T16:22:00.000000+02:00"
    }
  }
}
```

Geschrieben atomar: `state.tmp` → `replace()` → `state.json`. Damit kann das Tool während des Schreibens nicht zu inkonsistentem State führen.

## 7. Deployment-Layout

```
/opt/notlicht-monitor/          # Code, read-only für Dienst
├── main.py
├── netlight_client.py
├── mail_builder.py
├── mailer.py
├── state.py
└── config.py

/etc/notlicht-monitor/
└── config.yaml                  # chmod 600, owner: notlicht

/var/lib/notlicht-monitor/
└── state.json                   # chmod 600, owner: notlicht

/etc/systemd/system/
├── notlicht-monitor.service
└── notlicht-monitor.timer
```

## 8. Fehlerklassen und Reaktionen

| Fehler | Erkannt in | Reaktion |
|---|---|---|
| `ConnectionError`, `Timeout` | `netlight_client._post` | Retry nach Backoff (10/30/60 s), danach `reachable=False` → Gerät zählt als Störung |
| HTTP 4xx/5xx | `raise_for_status` | identisch zu oben |
| Ungültiges JSON | `requests.Response.json()` | identisch zu oben |
| Unerwartete Array-Länge | `DeviceSnapshot.is_ok` | Gerät zählt als Störung, Abweichung wird geloggt |
| Mailversand-Fehler | `mailer.send` | Exception wird geloggt, State wird dennoch persistiert; nächster Lauf versucht nicht nachzusenden (bewusst, siehe FA-13) |
| State-Datei korrupt | `State._load` | Warnung im Log, Start mit leerem State = alle Geräte als „erstmalig gesehen" (keine Mail) |

## 9. Leistung / Laufzeit

Typischer Lauf auf Pi 1 B+ mit drei Anlagen im lokalen LAN:

- HTTP-Requests: 3 Anlagen × 3 Endpoints = 9 Requests, sequentiell.
- LAN-Latenz pro Request: < 100 ms, JSON winzig → Gesamt < 2 s im Normalfall.
- Bei einer nicht erreichbaren Anlage: 3 × Timeout (10 s) + 2 Backoffs (10 s + 30 s) = bis zu ~70 s.
- Bei drei nicht erreichbaren Anlagen (worst case): ~210 s ≈ 3,5 min.
- Der 15-Minuten-Timer hat genug Puffer.

## 10. Sicherheits-Überlegungen

- Der Monitor macht nur Read-Requests. Er kann an den Anlagen nichts verstellen.
- Die NETLIGHT-Anlagen selbst haben kein Login vor den gelesenen Endpoints. Zugangs­schutz erfolgt rein über Netzsegmentierung – Verantwortung des Betreibers.
- SMTP-Passwort liegt im Klartext in `config.yaml`, geschützt durch Dateirechte (600) und dedizierten Systemuser. Höhere Sicherheits­stufen (z. B. Secret-Store) sind für diesen Einsatzfall nicht vorgesehen.
- Logs enthalten kein Passwort, aber bei Fehlern vollständige URLs der Anlagen.

## 11. Erweiterungspunkte

Falls später gewünscht – was im aktuellen Scope nicht ist:

- Anderer Transport (MQTT, Webhook) → zusätzlicher Sender analog zu `mailer.py`.
- Tägliche statt wöchentlicher Reports → neuer Schedule-Block in Config, minimal in `should_send_*` erweitern.
- HTML-Mails statt Plaintext → `EmailMessage.add_alternative()` im `mailer.py`.
- Mehr als drei Anlagen → einfach in `devices:` eintragen, kein Code-Change.

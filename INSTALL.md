# Notlicht-Monitor – Installation auf dem Raspberry Pi

Getestetes Ziel: Pi 1 B+ mit Raspberry Pi OS Lite (Bookworm, 32-bit, armv6l).

## 1. Pakete

```bash
sudo apt update
sudo apt install -y python3 python3-requests python3-yaml
```

Die apt-Pakete reichen – kein pip, kein venv. Der B+ hat zu wenig Dampf,
um sich damit unnoetig zu qualen.

## 2. Code ablegen

```bash
sudo mkdir -p /opt/notlicht-monitor
sudo cp code/*.py /opt/notlicht-monitor/
sudo chmod 755 /opt/notlicht-monitor/main.py
```

## 3. User fuer den Dienst

```bash
sudo useradd -r -s /usr/sbin/nologin notlicht || true
sudo mkdir -p /var/lib/notlicht-monitor
sudo chown notlicht:notlicht /var/lib/notlicht-monitor
```

## 4. Config + Secrets

```bash
sudo mkdir -p /etc/notlicht-monitor

# Haupt-Config (ohne Passwort)
sudo cp config.yaml.example /etc/notlicht-monitor/config.yaml
sudo chown notlicht:notlicht /etc/notlicht-monitor/config.yaml
sudo chmod 600 /etc/notlicht-monitor/config.yaml
sudo nano /etc/notlicht-monitor/config.yaml

# Secrets (SMTP-Passwort)
sudo cp secrets.yaml.example /etc/notlicht-monitor/secrets.yaml
sudo chown notlicht:notlicht /etc/notlicht-monitor/secrets.yaml
sudo chmod 600 /etc/notlicht-monitor/secrets.yaml
sudo nano /etc/notlicht-monitor/secrets.yaml
```

In `config.yaml` anpassen: `devices`, `smtp.*` (ohne Passwort), `recipients`, ggf. `mail.*`.
In `secrets.yaml` nur: `smtp.password`. Die secrets werden beim Start automatisch ueber die Hauptconfig gemerged.

## 5. Testlauf (ohne Mailversand)

```bash
sudo -u notlicht /usr/bin/python3 /opt/notlicht-monitor/main.py \
    --dry-run --force-weekly
```

Erwartet: Pro Geraet eine Zeile "OK" oder "STOERUNG" im Log,
plus ein kompletter Mail-Entwurf auf stdout.

Wenn das passt, echter Mailtest:

```bash
sudo -u notlicht /usr/bin/python3 /opt/notlicht-monitor/main.py --force-weekly
```

Die Empfaenger aus der Config sollten eine Mail bekommen.

## 6. systemd aktivieren

```bash
sudo cp systemd/notlicht-monitor.service /etc/systemd/system/
sudo cp systemd/notlicht-monitor.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now notlicht-monitor.timer
```

## 7. Pruefen

```bash
# Ist der Timer aktiv?
systemctl list-timers notlicht-monitor.timer

# Letzter Lauf:
systemctl status notlicht-monitor.service

# Live-Log:
journalctl -u notlicht-monitor.service -f

# Historie der letzten 50 Laeufe:
journalctl -u notlicht-monitor.service -n 200 --no-pager
```

## Bedienung / Wartung

**Mail-Text aendern:** `sudo nano /etc/notlicht-monitor/config.yaml`,
Aenderung greift beim naechsten Lauf.

**Sofort-Test eines manuellen Laufs:**
```bash
sudo systemctl start notlicht-monitor.service
```

**State zuruecksetzen** (z.B. wenn faelschlich Alarm gesendet wurde):
```bash
sudo rm /var/lib/notlicht-monitor/state.json
```
Beim naechsten Lauf wird der aktuelle Status als neue Baseline genommen,
es gibt keinen Alarm.

**Wochenreport erneut senden (z.B. fuer Test):**
```bash
sudo -u notlicht /usr/bin/python3 /opt/notlicht-monitor/main.py --force-weekly
```

## Verhaltensmatrix

| Situation                          | Reaktion                         |
|------------------------------------|----------------------------------|
| Erster Lauf nach Installation      | nur State setzen, keine Mail     |
| Geraet OK, bleibt OK               | keine Mail (ausser Wochenreport) |
| Geraet OK -> Stoerung              | sofortige Alarm-Mail             |
| Geraet Stoerung -> Stoerung        | keine weitere Mail (kein Spam)   |
| Geraet Stoerung -> OK              | Entwarnungs-Mail                 |
| Geraet nicht erreichbar (3 Retries)| gilt als Stoerung                |
| Montag 07:00+                      | Wochenreport mit allen Details   |

## Sicherheits-Hinweis

Die NETLIGHT-Anlagen laufen auf uraltem Apache/PHP (Debian 7).
Diese Geraete unter keinen Umstaenden ins Internet routen, und moeglichst
in ein separates VLAN/Management-Netz stellen. Der Monitor-Pi sollte der
einzige Client sein, der sie anspricht.

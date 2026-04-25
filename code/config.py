# Notlicht-Monitor - Emergency Light Monitoring Tool
# Copyright (C) 2026 Axel Schmidt
# SPDX-License-Identifier: LicenseRef-Notlicht-Monitor-NC
#
# Nicht-kommerzielle Nutzung ist frei gestattet. Kommerzielle Nutzung bedarf
# der schriftlichen Zustimmung des Autors. Volle Bedingungen: siehe LICENSE.
#
# HAFTUNGSAUSSCHLUSS: Keine Gewaehrleistung. Diese Software stellt nur ein
# zusaetzliches informationelles Monitoring dar und ERSETZT NICHT die
# gesetzlich vorgeschriebenen Pruefungen der Notlichtanlage durch
# Fachpersonal (DIN EN 50172, VDE 0108, DIN EN 50171, VDE 0100-560,
# DGUV Vorschrift 3 u. a.). Die Verantwortung fuer die ordnungsgemaesse
# Funktion verbleibt beim Betreiber.
"""
Config laden (YAML), Defaults mergen, minimal validieren.

Secrets liegen bewusst in einer separaten Datei (secrets.yaml), die niemals
ins Repo gehoert. Ist sie vorhanden, wird sie zuletzt ueber die Config
gemerged - dort stehen also z.B. smtp.password. Default-Pfad: gleiche
Verzeichnis wie config.yaml.
"""
import logging
from pathlib import Path
from typing import Optional
import yaml

log = logging.getLogger(__name__)


DEFAULTS = {
    "http": {
        "timeout_seconds": 10,
        "retry_attempts": 3,
        "retry_delays": [10, 30, 60],
    },
    "mail": {
        "weekly_subject":        "{status_emoji} Wochenreport Notlicht - {date}",
        "alarm_subject":         "{status_emoji} ALARM Notlicht - {device}",
        "recovery_subject":      "{status_emoji} Entwarnung Notlicht - {device}",
        "test_response_subject": "{status_emoji} TEST-Antwort Notlicht - {date}",
        "status_emoji_ok":    "\U0001F7E2",  # gruener Kreis
        "status_emoji_fault": "\U0001F534",  # roter Kreis
        "intro_text": (
            "Wochenstatus der Sicherheitsbeleuchtung vom {date}.\n"
            "Alle Anlagen wurden automatisch abgefragt. Details unten.\n"
        ),
        "custom_intro_text": "",
        "custom_footer": "",
    },
    "schedule": {
        "weekly_report_weekday": 1,   # 1=Montag (ISO: 1-7)
        "weekly_report_hour": 7,
    },
    "imap": {
        # Default: aus. Erst aktivieren, wenn TEST-Mail-Funktion gewuenscht ist.
        "enabled": False,
        # Leer = identisch zu smtp.host (haeufiger Fall: gleicher Provider).
        "host": "",
        "port": 993,
        "use_ssl": True,
        # Leer = identisch zu smtp.username.
        "username": "",
        # Passwort kommt aus secrets.yaml unter imap.password; leer = smtp.password.
        "folder": "INBOX",
        "test_subject": "TEST",         # case-insensitive, getrimmt
        "delete_processed": True,       # verarbeitete Mails aus Postfach loeschen
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: Path, secrets_path: Optional[Path] = None) -> dict:
    path = Path(path)
    with path.open() as f:
        user = yaml.safe_load(f) or {}

    cfg: dict = {}
    _deep_merge(cfg, DEFAULTS)
    _deep_merge(cfg, user)

    # Secrets-Datei daneben suchen (oder expliziten Pfad nehmen) und drueber mergen.
    # Fehlt die Datei, ist das OK - dann muessen die Werte vollstaendig in config.yaml
    # stehen (nicht empfohlen fuer Passwoerter).
    if secrets_path is None:
        secrets_path = path.parent / "secrets.yaml"
    secrets_path = Path(secrets_path)
    if secrets_path.exists():
        try:
            with secrets_path.open() as f:
                secrets = yaml.safe_load(f) or {}
            if not isinstance(secrets, dict):
                raise ValueError("secrets.yaml muss ein Mapping sein.")
            _deep_merge(cfg, secrets)
            log.info("Secrets geladen aus %s", secrets_path)
        except (OSError, yaml.YAMLError) as e:
            raise ValueError(f"secrets-Datei {secrets_path} unlesbar: {e}") from e

    if not cfg.get("devices"):
        raise ValueError("config: 'devices' ist leer oder fehlt.")
    for i, dev in enumerate(cfg["devices"]):
        if "name" not in dev or "url" not in dev:
            raise ValueError(f"config: devices[{i}] braucht 'name' und 'url'.")

    if not cfg.get("smtp"):
        raise ValueError("config: 'smtp' fehlt.")
    for key in ("host", "port", "from_address"):
        if key not in cfg["smtp"]:
            raise ValueError(f"config: smtp.{key} fehlt.")

    if not cfg.get("recipients"):
        raise ValueError("config: 'recipients' ist leer oder fehlt.")

    sched = cfg["schedule"]
    if not (1 <= int(sched["weekly_report_weekday"]) <= 7):
        raise ValueError("config: schedule.weekly_report_weekday muss 1..7 sein.")
    if not (0 <= int(sched["weekly_report_hour"]) <= 23):
        raise ValueError("config: schedule.weekly_report_hour muss 0..23 sein.")

    # IMAP-Block: leere Felder von SMTP uebernehmen, damit der Default-Fall
    # "gleicher Account wie SMTP" minimal konfigurierbar bleibt.
    imap = cfg.setdefault("imap", {})
    if imap.get("enabled"):
        if not imap.get("host"):
            imap["host"] = cfg["smtp"]["host"]
        if not imap.get("username"):
            imap["username"] = cfg["smtp"].get("username", "")
        if not imap.get("password"):
            imap["password"] = cfg["smtp"].get("password", "")
        if not imap.get("host"):
            raise ValueError("config: imap.host fehlt (und smtp.host ebenfalls).")
        if not imap.get("username"):
            raise ValueError("config: imap.username fehlt.")
        if not imap.get("password"):
            raise ValueError("config: imap.password fehlt (gehoert in secrets.yaml).")
        if not imap.get("test_subject"):
            raise ValueError("config: imap.test_subject darf nicht leer sein.")

    return cfg

"""
Config laden (YAML), Defaults mergen, minimal validieren.
"""
from pathlib import Path
import yaml


DEFAULTS = {
    "http": {
        "timeout_seconds": 10,
        "retry_attempts": 3,
        "retry_delays": [10, 30, 60],
    },
    "mail": {
        "weekly_subject":   "{status_emoji} Wochenreport Notlicht - {date}",
        "alarm_subject":    "{status_emoji} ALARM Notlicht - {device}",
        "recovery_subject": "{status_emoji} Entwarnung Notlicht - {device}",
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
}


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: Path) -> dict:
    with Path(path).open() as f:
        user = yaml.safe_load(f) or {}

    cfg: dict = {}
    _deep_merge(cfg, DEFAULTS)
    _deep_merge(cfg, user)

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

    return cfg

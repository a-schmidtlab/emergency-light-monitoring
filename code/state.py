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
Persistenter State in JSON:
- letzter bekannter OK/Stoerung-Status pro Geraet (fuer Alarm-Diff)
- Zeitpunkt des letzten Wochenreports (damit keiner doppelt rausgeht)
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class State:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = {
            "last_weekly_report": None,  # ISO timestamp mit tzinfo
            "devices": {},               # name -> {"was_ok": bool, "last_check": iso}
        }
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            with self.path.open() as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("State-Datei %s unlesbar, starte mit leerem State: %s",
                        self.path, e)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(self.data, f, indent=2)
        tmp.replace(self.path)

    def last_weekly_report(self) -> Optional[datetime]:
        ts = self.data.get("last_weekly_report")
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None

    def set_weekly_report_sent(self, when: datetime):
        self.data["last_weekly_report"] = when.isoformat()

    def was_ok(self, device_name: str) -> Optional[bool]:
        """True/False wenn letzter Status bekannt, None wenn erster Lauf."""
        d = self.data["devices"].get(device_name)
        if d is None:
            return None
        return bool(d.get("was_ok"))

    def update_device(self, device_name: str, is_ok: bool, when: datetime):
        self.data["devices"][device_name] = {
            "was_ok": bool(is_ok),
            "last_check": when.isoformat(),
        }

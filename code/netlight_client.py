# Notlicht-Monitor - Emergency Light Monitoring Tool
# Copyright (C) 2026 Axel Schmidt <axel@schmidtlab.net>
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
Client fuer NETLIGHT Sicherheitsbeleuchtungssysteme.
Fragt die drei AJAX-Endpoints ab und liefert ein DeviceSnapshot-Objekt.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List

import requests

log = logging.getLogger(__name__)


def _describe_error(exc: Exception, attempts: int, timeout: int) -> str:
    """Kurze, fuer Endanwender verstaendliche Fehlerbeschreibung.

    Die rohe Exception wird separat ins systemd-Journal geloggt; die Mail
    bekommt nur diesen einzeiligen, sprechenden Text.
    """
    if isinstance(exc, (requests.exceptions.ConnectTimeout,
                        requests.exceptions.ReadTimeout)):
        return (f"Geraet antwortet nicht (Timeout {timeout} s, "
                f"{attempts} Versuch{'e' if attempts != 1 else ''}).")
    if isinstance(exc, requests.exceptions.ConnectionError):
        return (f"Verbindung zum Geraet nicht moeglich "
                f"({attempts} Versuch{'e' if attempts != 1 else ''} fehlgeschlagen).")
    if isinstance(exc, requests.exceptions.HTTPError):
        code = getattr(getattr(exc, "response", None), "status_code", "?")
        return f"Geraet antwortet mit Fehler-Status HTTP {code}."
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "Antwort des Geraets konnte nicht ausgewertet werden (kein gueltiges JSON)."
    return f"Unerwarteter Fehler beim Abruf ({type(exc).__name__})."

# Mapping Array-Index -> Bedeutung, abgeleitet aus index.php + JS-Code.
# Das Array hat 10 Elemente, aber die Seite nutzt nur diese Positionen:
STATUS_LABELS = {
    0: "Betrieb",
    1: "Netzbetrieb",
    2: "Batteriebetrieb",
    3: "Sammelstoerung",
    4: "Tiefentladung",
    6: "Testbetrieb",
}

# Erwarteter Sollwert pro Index. Abweichung = Stoerung.
STATUS_EXPECTED = {
    0: "green",   # Betrieb soll an
    1: "green",   # Netzbetrieb soll an
    2: "",        # Batteriebetrieb soll aus
    3: "",        # Sammelstoerung soll aus
    4: "",        # Tiefentladung soll aus
    6: "",        # Testbetrieb soll aus
}

# Messwerte: Index -> (Label, Einheit). Indizes 1 und 2 sind im UI unsichtbar.
MESSWERT_LABELS = {
    0: ("Netzspannung",     "V"),
    3: ("Batteriespannung", "V"),
    4: ("Batteriekapazitaet", "Ah"),
    5: ("Ladestrom",        "A"),   # negativ = Entladestrom
}


@dataclass
class DeviceSnapshot:
    name: str
    url: str
    reachable: bool = False
    error: Optional[str] = None
    status: List = field(default_factory=list)
    messwerte: List = field(default_factory=list)
    meldungen: List = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        if not self.reachable:
            return False
        if len(self.status) < 7:
            return False
        for idx, expected in STATUS_EXPECTED.items():
            actual = self.status[idx] if idx < len(self.status) else ""
            if actual != expected:
                return False
        return True

    @property
    def abweichungen(self) -> List[str]:
        if not self.reachable:
            return [f"nicht erreichbar: {self.error or 'unbekannter Fehler'}"]
        if len(self.status) < 7:
            return [f"unerwartetes Statusformat: {self.status}"]
        out = []
        for idx, expected in STATUS_EXPECTED.items():
            actual = self.status[idx] if idx < len(self.status) else ""
            label = STATUS_LABELS[idx]
            if expected == "green" and actual != "green":
                out.append(f"{label}: nicht gruen (Wert: '{actual or 'leer'}')")
            elif expected == "" and actual != "":
                out.append(f"{label}: aktiv (Wert: '{actual}')")
        return out


class NetlightClient:
    def __init__(self, timeout: int = 10, attempts: int = 3,
                 delays: Optional[List[int]] = None):
        self.timeout = timeout
        self.attempts = max(1, attempts)
        self.delays = delays or [10, 30, 60]

    def _post(self, url: str, data: Optional[dict] = None):
        last_err = None
        for attempt in range(self.attempts):
            try:
                r = requests.post(url, data=data or {}, timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                log.warning("POST %s Versuch %d/%d fehlgeschlagen: %s",
                            url, attempt + 1, self.attempts, e)
                if attempt < self.attempts - 1:
                    delay = self.delays[min(attempt, len(self.delays) - 1)]
                    time.sleep(delay)
        raise last_err  # type: ignore[misc]

    def fetch(self, name: str, base_url: str) -> DeviceSnapshot:
        snap = DeviceSnapshot(name=name, url=base_url)
        base = base_url.rstrip("/")
        try:
            snap.status    = self._post(f"{base}/ajax_anlagenstatus.php")
            snap.messwerte = self._post(f"{base}/ajax_messwerte.php")
            snap.meldungen = self._post(f"{base}/ajax_meldungen.php",
                                        data={"para1": "start"})
            snap.reachable = True
        except Exception as e:
            snap.error = _describe_error(e, self.attempts, self.timeout)
            # Menschenlesbar in die Mail, rohe Details NUR ins Log:
            log.error("Geraet %s (%s) nicht erreichbar: %s (Original: %s: %s)",
                      name, base_url, snap.error, type(e).__name__, e)
        return snap

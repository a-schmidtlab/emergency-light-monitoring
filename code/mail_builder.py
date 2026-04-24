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
Erzeugt Mail-Bodies (Plaintext) aus DeviceSnapshots.
"""
from datetime import datetime
from html.parser import HTMLParser
from typing import List

from netlight_client import (
    STATUS_LABELS, MESSWERT_LABELS, DeviceSnapshot,
)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html_parts) -> str:
    """Meldungen kommen als Array von HTML-Schnipseln, flach machen."""
    if not html_parts:
        return "(keine Meldungen)"
    joined = "".join(str(p) for p in html_parts)
    ex = _TextExtractor()
    ex.feed(joined)
    text = " ".join("".join(ex.parts).split()).strip()
    return text or "(keine Meldungen)"


def _format_messwert(idx: int, raw_value: str) -> str:
    label, unit = MESSWERT_LABELS[idx]
    # Ladestrom negativ => Entladestrom (entspricht JS-Logik im Original)
    if idx == 5:
        try:
            v = float(raw_value)
            if v < 0:
                label = "Entladestrom"
        except (TypeError, ValueError):
            pass
    return f"  {label:<20} {raw_value} {unit}"


def format_device_block(snap: DeviceSnapshot) -> str:
    lines = [f"=== {snap.name} ({snap.url}) ==="]

    if not snap.reachable:
        lines.append("STATUS: NICHT ERREICHBAR")
        lines.append(f"Fehler: {snap.error}")
        return "\n".join(lines)

    overall = "OK" if snap.is_ok else "STOERUNG"
    lines.append(f"Gesamtstatus: {overall}")
    lines.append("")
    lines.append("Anlagenstatus:")
    for idx, label in STATUS_LABELS.items():
        val = snap.status[idx] if idx < len(snap.status) else ""
        display = val if val else "-"
        lines.append(f"  {label:<20} {display}")

    lines.append("")
    lines.append("Messwerte:")
    for idx in MESSWERT_LABELS:
        val = snap.messwerte[idx] if idx < len(snap.messwerte) else "-"
        lines.append(_format_messwert(idx, val))

    lines.append("")
    lines.append("Meldungen:")
    lines.append(f"  {html_to_text(snap.meldungen)}")

    if not snap.is_ok:
        lines.append("")
        lines.append("Abweichungen:")
        for a in snap.abweichungen:
            lines.append(f"  - {a}")

    return "\n".join(lines)


def _intro(mail_cfg: dict, now: datetime, device: str = "") -> str:
    custom = mail_cfg.get("custom_intro_text", "").strip()
    text = custom if custom else mail_cfg.get("intro_text", "")
    return text.format(date=now.strftime("%d.%m.%Y"),
                       datetime=now.strftime("%d.%m.%Y %H:%M"),
                       device=device)


def _footer(mail_cfg: dict) -> str:
    return mail_cfg.get("custom_footer", "").strip()


def build_weekly_body(snapshots: List[DeviceSnapshot], mail_cfg: dict,
                      now: datetime) -> str:
    parts = [_intro(mail_cfg, now), ""]
    all_ok = all(s.is_ok for s in snapshots)
    parts.append(f"GESAMTSTATUS: {'ALLE OK' if all_ok else 'STOERUNG'}")
    parts.append("")
    for snap in snapshots:
        parts.append(format_device_block(snap))
        parts.append("")
    f = _footer(mail_cfg)
    if f:
        parts.append(f)
    parts.append("")
    parts.append(f"-- Notlicht-Monitor, Lauf {now.strftime('%d.%m.%Y %H:%M:%S')}")
    return "\n".join(parts)


def build_alarm_body(snap: DeviceSnapshot, mail_cfg: dict,
                     now: datetime) -> str:
    parts = [_intro(mail_cfg, now, device=snap.name), ""]
    parts.append("STOERUNG erkannt an folgender Anlage:")
    parts.append("")
    parts.append(format_device_block(snap))
    f = _footer(mail_cfg)
    if f:
        parts.append("")
        parts.append(f)
    parts.append("")
    parts.append(f"-- Notlicht-Monitor, {now.strftime('%d.%m.%Y %H:%M:%S')}")
    return "\n".join(parts)


def build_recovery_body(snap: DeviceSnapshot, mail_cfg: dict,
                        now: datetime) -> str:
    parts = [
        f"Entwarnung fuer Anlage '{snap.name}' am {now.strftime('%d.%m.%Y %H:%M')}.",
        "",
        "Die Anlage meldet wieder normalen Betrieb.",
        "",
        format_device_block(snap),
    ]
    f = _footer(mail_cfg)
    if f:
        parts.append("")
        parts.append(f)
    parts.append("")
    parts.append(f"-- Notlicht-Monitor, {now.strftime('%d.%m.%Y %H:%M:%S')}")
    return "\n".join(parts)

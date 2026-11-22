"""The VPN section on Denise's dashboard (`dashboard-denise`), in German.

The rest of that dashboard is edited in the HA UI and isn't kept here. This
owns one section only: the one whose heading is `HEADING`. `apply()` replaces
it, or adds it at the end of the first view, and leaves every other section,
view and dashboard-level setting (kiosk mode) as it was.

Entities, the free allowance and the colour steps come from the VPN dashboard
(`dashboards/vpn/build.py`), so the two can't drift apart.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

_spec = importlib.util.spec_from_file_location(
    "vpn_build", Path(__file__).resolve().parent.parent / "vpn" / "build.py")
vpn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vpn)

DASHBOARD = "dashboard-denise"
HEADING = "VPN"
MINE = dict((name, e) for e, name in vpn.PEERS)["Denise"]
FREE = vpn.FREE_GB
# The banner changes where the gauge changes colour (and the pills turn on).
INFO, WARN, OVER = (s["from"] for s in vpn.ALLOWANCE_SEGMENTS[1:])

LEFT = "Noch {{ (" + str(FREE) + " - gb)|round(1) }} GB gratis diesen Monat."
STATUS = ("{% set u = states('" + vpn.USED + "')|float(0) %}{% set gb = states('" + vpn.EGRESS + "')|float(0) %}"
          "{% if u >= " + str(OVER) + " %}<ha-alert alert-type=\"error\" title=\"Gratis-Kontingent aufgebraucht\">"
          "{{ (gb - " + str(FREE) + ")|round(1) }} GB darüber. Jedes weitere GB kostet etwas.</ha-alert>"
          "{% elif u >= " + str(WARN) + " %}<ha-alert alert-type=\"warning\" title=\"Fast aufgebraucht\">" + LEFT + "</ha-alert>"
          "{% elif u >= " + str(INFO) + " %}<ha-alert alert-type=\"info\" title=\"Mehr als die Hälfte gebraucht\">" + LEFT + "</ha-alert>"
          "{% else %}<ha-alert alert-type=\"success\" title=\"Alles im grünen Bereich\">" + LEFT + "</ha-alert>{% endif %}")
# The same pace as the VPN dashboard: egress so far, over the days gone, times the days in the month.
PACE = ("{% set d = now().day %}"
        "{% set n = ((now().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day %}"
        "{% set end = states('" + vpn.EGRESS + "')|float(0) / d * n %}"
        "So weiter: **{{ end|round(0)|int }} GB** bis Ende Monat, "
        "{{ (end / " + str(FREE) + " * 100)|round(0)|int }} % vom Gratis-Kontingent.")


def _tile(entity_id: str, name: str) -> dict[str, Any]:
    return {"type": "tile", "entity": entity_id, "vertical": True, "name": name, "grid_options": {"columns": 6}}


def section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": HEADING, "heading_style": "title", "icon": vpn.ICON},
        {"type": "markdown", "content": STATUS},
        {"type": "gauge", "entity": vpn.USED, "name": "Gratis-Kontingent", "min": 0, "max": 100, "needle": True,
         "segments": vpn.ALLOWANCE_SEGMENTS, "grid_options": {"columns": 12}},
        _tile(MINE, "Du, diesen Monat"),
        _tile(vpn.EGRESS, "Alle zusammen"),
        {"type": "markdown", "content": PACE},
        {"type": "history-graph", "title": "Letzte 30 Tage (GB)", "hours_to_show": 720,
         "entities": [{"entity": MINE, "name": "Du"}, {"entity": vpn.EGRESS, "name": "Alle"}]},
        {"type": "markdown", "text_only": True,
         "content": f"<small>Pro Monat sind {FREE} GB gratis, die der VPN-Server ins Internet schickt. "
                    "Die Zahlen kommen von AWS und sind ein paar Stunden alt.</small>"},
    ]}


def is_ours(sec: dict[str, Any]) -> bool:
    cards = sec.get("cards") or []
    return bool(cards) and cards[0].get("type") == "heading" and cards[0].get("heading") == HEADING


def apply(dashboard: dict[str, Any]) -> dict[str, Any]:
    """The dashboard with the VPN section replaced in place, or added at the end of the first view."""
    out = copy.deepcopy(dashboard)
    sections = out["views"][0].setdefault("sections", [])
    at = next((i for i, s in enumerate(sections) if is_ours(s)), None)
    sections[:] = [s for s in sections if not is_ours(s)]
    sections.insert(len(sections) if at is None else at, section())
    return out

"""The Health dashboard (`dashboard-health`): the Global Health Score's Pro card.

HAGHS (HACS: HA-Pulse/home-assistant-global-health-score) rates HA itself,
0-100 %. Its "Pro" card shows where the points go: failed integrations,
repairs, pending updates, recorder and database, stale and zombie entities,
dead devices. `pro.yaml` is that card, copied unchanged from the integration's
`docs/cards/pro.yaml` at the installed release (`PRO_CARD_RELEASE`); when HACS
updates HAGHS, copy the new one over it and bump the release.

Not in the sidebar: the "HA health low" pill on the Mobile dashboard links here
(`LINK`, used by `mobile-alerts/pills.py`). `build()` returns the whole config,
owned by the script like the VPN one: a card added in the UI is gone after the
next sync.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DASHBOARD = "dashboard-health"
VIEW = "score"
LINK = f"/{DASHBOARD}/{VIEW}"
TITLE = "Health"
ICON = "mdi:shield-check"

SCORE = "sensor.system_ha_global_health_score"
PRO_CARD = Path(__file__).resolve().parent / "pro.yaml"
PRO_CARD_RELEASE = "v2.4.2"  # HAGHS release pro.yaml comes from (card "Pro v1.4")


def pro_card() -> dict[str, Any]:
    return yaml.safe_load(PRO_CARD.read_text(encoding="utf-8"))


def history_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Last 30 days", "heading_style": "title", "icon": "mdi:chart-line"},
        {"type": "history-graph", "hours_to_show": 720, "entities": [{"entity": SCORE, "name": "Score"}]},
        {"type": "entities", "entities": [
            {"type": "attribute", "entity": SCORE, "attribute": "hardware_score", "name": "Hardware", "suffix": "%"},
            {"type": "attribute", "entity": SCORE, "attribute": "application_score", "name": "Application", "suffix": "%"},
            {"type": "attribute", "entity": SCORE, "attribute": "db_size_mb", "name": "Database", "suffix": "MB"},
        ]},
    ]}


def build() -> dict[str, Any]:
    back = {"type": "grid", "column_span": 2,
            "cards": [{"type": "custom:mushroom-chips-card", "chips": [{"type": "back"}]}]}
    pro = {"type": "grid", "cards": [pro_card()]}
    return {"views": [{"title": TITLE, "path": VIEW, "icon": ICON, "type": "sections", "max_columns": 2,
                       "sections": [back, pro, history_section()]}]}

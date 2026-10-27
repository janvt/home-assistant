"""The VPN dashboard (`dashboard-vpn`): how much of the month's free AWS
egress the WireGuard VPN has used, and what the AWS account costs so far.

Not in the sidebar: the VPN alert pills on the Mobile dashboard link here
(`LINK`, used by `mobile-alerts/pills.py`). `build()` returns the whole config,
owned by the script like the Trains one: a card added in the UI is gone after
the next sync.

Everything on it comes from the wg-vpn Terraform stack's EventBridge webhook
(automation "WG VPN: receive AWS EventBridge"), which writes the month-to-date
snapshot into input_number helpers.
"""
from __future__ import annotations

from typing import Any

DASHBOARD = "dashboard-vpn"
VIEW = "usage"
LINK = f"/{DASHBOARD}/{VIEW}"
TITLE = "VPN"
ICON = "mdi:vpn"

VPN = "input_number.wg_vpn_"
USED = VPN + "free_allowance_used"
EGRESS = VPN + "egress_month_to_date"
BILL = VPN + "aws_bill_month_to_date"
COST = VPN + "cost_month_to_date"
INSTANCE = "input_select.wg_vpn_instance_state"
WEBHOOK = "automation.wg_vpn_receive_aws_eventbridge"
PEERS = [(VPN + "mac_egress_month_to_date", "Mac"), (VPN + "denise_egress_month_to_date", "Denise"),
         (VPN + "phone_egress_month_to_date", "Phone")]
FREE_GB = 100
BILL_ALARM = 10  # the "AWS bill over $10" pill

# The same steps as the pills: 50 % yellow, 80 % orange, 100 % red.
ALLOWANCE_SEGMENTS = [{"from": 0, "color": "var(--green-color)"}, {"from": 50, "color": "var(--yellow-color)"},
                      {"from": 80, "color": "var(--orange-color)"}, {"from": 100, "color": "var(--red-color)"}]
BILL_SEGMENTS = [{"from": 0, "color": "var(--green-color)"}, {"from": BILL_ALARM * 0.8, "color": "var(--orange-color)"},
                 {"from": BILL_ALARM, "color": "var(--red-color)"}]

# Egress so far, spread over the days gone, times the days in the month.
PACE = ("{% set d = now().day %}"
        "{% set n = ((now().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day %}"
        "{% set gb = states('" + EGRESS + "')|float(0) %}{% set end = gb / d * n %}"
        "At this pace: **{{ end|round(0)|int }} GB** by the end of the month, "
        "{{ (end / " + str(FREE_GB) + " * 100)|round(0)|int }} % of the free " + str(FREE_GB) + " GB."
        "{% set t = state_attr('" + WEBHOOK + "','last_triggered') %}"
        "{{ '<br><small>Last snapshot from AWS ' ~ relative_time(t) ~ ' ago.</small>' if t }}")


def _tile(entity_id: str, name: str) -> dict[str, Any]:
    return {"type": "tile", "entity": entity_id, "name": name, "vertical": True}


def _gauge(entity_id: str, name: str, top: float, segments: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "gauge", "entity": entity_id, "name": name, "min": 0, "max": top, "needle": True,
            "segments": segments, "grid_options": {"columns": 6}}


def allowance_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Free allowance", "heading_style": "title", "icon": "mdi:gauge"},
        _gauge(USED, "Used", 100, ALLOWANCE_SEGMENTS),
        {**_tile(EGRESS, "Out this month"), "grid_options": {"columns": 6}},
        {"type": "markdown", "content": PACE},
        *(_tile(e, n) for e, n in PEERS),
    ]}


def cost_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Cost", "heading_style": "title", "icon": "mdi:currency-usd"},
        _gauge(BILL, "AWS bill", BILL_ALARM * 1.5, BILL_SEGMENTS),
        {**_tile(COST, "VPN egress cost"), "grid_options": {"columns": 6}},
        {"type": "markdown", "content": f"<small>The bill is the whole AWS account, month to date; the pill "
                                        f"turns on at ${BILL_ALARM}. Egress cost is what the VPN sent beyond "
                                        f"the free {FREE_GB} GB.</small>"},
        _tile(INSTANCE, "Instance"),
    ]}


def history_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 2, "cards": [
        {"type": "heading", "heading": "Last 30 days", "heading_style": "title", "icon": "mdi:chart-line"},
        {"type": "history-graph", "title": "Egress (GB)", "hours_to_show": 720,
         "entities": [{"entity": EGRESS, "name": "Total"}] + [{"entity": e, "name": n} for e, n in PEERS]},
        {"type": "history-graph", "title": "Cost (USD)", "hours_to_show": 720,
         "entities": [{"entity": BILL, "name": "AWS bill"}, {"entity": COST, "name": "VPN egress"}]},
    ]}


def build() -> dict[str, Any]:
    back = {"type": "grid", "column_span": 2,
            "cards": [{"type": "custom:mushroom-chips-card", "chips": [{"type": "back"}]}]}
    return {"views": [{"title": TITLE, "path": VIEW, "icon": ICON, "type": "sections", "max_columns": 2,
                       "sections": [back, allowance_section(), cost_section(), history_section()]}]}

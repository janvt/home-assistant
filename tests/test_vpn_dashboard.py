"""The VPN dashboard (`dashboards/vpn/`) and the alert pills that link to it.

It isn't in the sidebar, so the pills' links are the only way in: a link that
doesn't match the dashboard's path opens an empty page without a sound.
"""
from __future__ import annotations

import importlib.util
import json
import re
import runpy

from conftest import ROOT

HERE = ROOT / "dashboards" / "vpn"
spec = importlib.util.spec_from_file_location("vpn_build", HERE / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
CONFIG = build.build()
PILLS = runpy.run_path(str(ROOT / "dashboards" / "mobile-alerts" / "pills.py"))["ALERTS"]


def test_build_is_plain_json() -> None:
    assert json.loads(json.dumps(CONFIG)) == CONFIG


def test_link_is_a_view_of_the_dashboard() -> None:
    assert build.LINK in {f"/{build.DASHBOARD}/{v['path']}" for v in CONFIG["views"]}


def test_every_vpn_pill_links_to_the_dashboard() -> None:
    vpn = [p for p in PILLS if p["group"] == "VPN"]
    assert vpn and all(p.get("link") == build.LINK for p in vpn), [p["key"] for p in vpn]


def test_every_pill_link_goes_to_a_known_dashboard() -> None:
    """A typo in `link` sends the card to a page that doesn't exist."""
    links = {p["link"] for p in PILLS if p.get("link")}
    assert links <= {build.LINK}, links


def test_only_the_webhooks_entities() -> None:
    """The page shows what the wg-vpn webhook writes, and that automation."""
    used = set(re.findall(r"\b(?:sensor|input_number|input_select|automation)\.[a-z0-9_]+", json.dumps(CONFIG)))
    assert all("wg_vpn_" in e for e in used), sorted(used)


def test_gauge_steps_match_the_pills() -> None:
    """The allowance gauge changes colour where the pills turn on."""
    steps = [s["from"] for s in build.ALLOWANCE_SEGMENTS[1:]]
    assert steps == [50, 80, 100]
    assert build.BILL_SEGMENTS[-1]["from"] == build.BILL_ALARM
    bill = next(p for p in PILLS if p["key"] == "vpn_bill_over_10")
    assert f">= {build.BILL_ALARM} " in bill["tmpl"]

"""The VPN section on Denise's dashboard (`dashboards/denise/`).

The rest of that dashboard is hers, edited in the HA UI: a sync that touched
anything outside the section would quietly undo her changes, or the kiosk
mode that lets her swipe the menu open on the phone.
"""
from __future__ import annotations

import importlib.util
import json
import re

from conftest import ROOT

spec = importlib.util.spec_from_file_location("denise_build", ROOT / "dashboards" / "denise" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def _dashboard() -> dict:
    return {"kiosk_mode": {"hide_header": True, "hide_sidebar": True,
                           "mobile_settings": {"hide_header": True, "hide_sidebar": False}},
            "views": [{"title": "Denise", "path": "home", "type": "sections", "sections": [
                          {"type": "grid", "cards": [{"type": "heading", "heading": "Föhn"}]},
                          {"type": "grid", "cards": [{"type": "heading", "heading": "Axenstrasse"}]}]},
                      {"title": "Hinweise", "path": "hinweise", "subview": True, "sections": []}]}


def test_apply_touches_only_the_vpn_section() -> None:
    before = _dashboard()
    after = build.apply(before)
    assert {k: v for k, v in after.items() if k != "views"} == {k: v for k, v in before.items() if k != "views"}
    assert after["views"][1:] == before["views"][1:]
    assert after["views"][0]["sections"][:-1] == before["views"][0]["sections"]
    assert build.is_ours(after["views"][0]["sections"][-1])


def test_apply_keeps_the_section_where_she_moved_it() -> None:
    """Moved up in the UI, it's replaced in place, not sent back to the end."""
    moved = build.apply(_dashboard())
    secs = moved["views"][0]["sections"]
    secs.insert(0, secs.pop())
    again = build.apply(moved)
    assert build.is_ours(again["views"][0]["sections"][0])
    assert sum(build.is_ours(s) for s in again["views"][0]["sections"]) == 1


def test_apply_is_idempotent() -> None:
    once = build.apply(_dashboard())
    assert build.apply(once) == once


def test_her_own_counter_is_her_peer() -> None:
    """"Du" must be Denise's WireGuard peer, not the Mac's or the phone's."""
    assert build.MINE in [e for e, _ in build.vpn.PEERS]
    assert "denise" in build.MINE


def test_only_the_webhooks_entities() -> None:
    used = set(re.findall(r"\b(?:sensor|input_number|input_select|automation)\.[a-z0-9_]+", json.dumps(build.section())))
    assert used and all("wg_vpn_" in e for e in used), sorted(used)


def test_banner_steps_match_the_gauge() -> None:
    """The banner changes where the gauge changes colour."""
    steps = [s["from"] for s in build.vpn.ALLOWANCE_SEGMENTS[1:]]
    assert [build.INFO, build.WARN, build.OVER] == steps
    for step in steps:
        assert f"u >= {step} " in build.STATUS

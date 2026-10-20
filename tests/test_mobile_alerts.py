"""The Mobile dashboard's alert pills (`dashboards/mobile-alerts/`).

Nothing here talks to Home Assistant. What goes wrong with this setup is
quiet: the alert row wraps onto a second line, a rebuild clobbers a card on
the dashboard that has nothing to do with alerts, a helper template has a typo
and simply stays off, or a created helper gets an entity id the row never
looks at. Each test below guards one of those.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from conftest import ROOT

HERE = ROOT / "dashboards" / "mobile-alerts"


def _load(name: str):
    sys.path.insert(0, str(HERE))
    try:
        spec = importlib.util.spec_from_file_location(f"mobile_alerts_{name}", HERE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(HERE))


build = _load("build")

# Mushroom's named colours (icon_color accepts these or a hex value).
MUSHROOM_COLORS = {
    "red", "pink", "purple", "deep-purple", "indigo", "blue", "light-blue", "cyan", "teal", "green",
    "light-green", "lime", "yellow", "amber", "orange", "deep-orange", "brown", "grey", "blue-grey",
    "black", "white", "disabled",
}


def _weather_dashboard() -> dict:
    """The shape of the real Mobile dashboard: weather chips first, more cards, more views."""
    return {"views": [
        {"title": "Default", "type": "sections", "sections": [{"type": "grid", "cards": [
            {"type": "custom:mushroom-chips-card", "alignment": "center", "chips": [
                {"type": "weather", "entity": "weather.altdorf_ur", "show_temperature": True},
                {"type": "weather", "entity": "weather.andermatt", "show_temperature": True}]},
            {"type": "horizontal-stack", "cards": [{"type": "custom:mushroom-template-card", "primary": "Lights"}]},
        ]}]},
        {"title": "Lights", "path": "lights", "type": "sections", "sections": []},
    ]}


def _visible(conditions: list[dict], count: int) -> bool:
    return all(str(count) in c["state"] for c in conditions)


# ── pills.py ────────────────────────────────────────────────────────────────
def test_pill_keys_are_unique_and_slug_shaped() -> None:
    """The key is the entity id: `binary_sensor.pill_<key>`. HA slugifies the
    helper title it is created with, so the key must survive that unchanged,
    or the row looks for an entity that never exists.
    """
    keys = [p["key"] for p in build.ALERTS]
    assert len(keys) == len(set(keys)), "duplicate pill keys"
    for key in keys:
        assert re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", key), key
        title = "Pill " + key.replace("_", " ")
        assert re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") == f"pill_{key}"


def test_every_pill_is_complete() -> None:
    """A pill without a template stays off for ever; one in an unknown group
    never shows on the Alerts page; an unknown colour renders grey."""
    for p in build.ALERTS:
        assert p.get("tmpl"), f"{p['key']} has no template"
        assert p["group"] in build.GROUPS, f"{p['key']}: group {p['group']!r}"
        assert p["color"] in MUSHROOM_COLORS, f"{p['key']}: colour {p['color']!r}"
        assert p["icon"].startswith("mdi:"), p["key"]
        assert p["name"] and p["rule"].endswith("."), p["key"]
    assert set(build.GROUP_ICONS) == set(build.GROUPS)


def test_templates_compile() -> None:
    """Jinja syntax errors only show up as a helper that is quietly unavailable.

    HA's own filters are stubbed: this checks the syntax, not the logic.
    """
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(extensions=["jinja2.ext.loopcontrols"])
    for name in ("as_local", "relative_time", "is_number", "float", "int"):
        env.filters.setdefault(name, lambda value, *args: value)
    templates = {"count chip": build.chips()[-1]["chip"]["content"]}
    for p in build.ALERTS:
        templates[f"{p['key']} state"] = p["tmpl"]
        templates[f"{p['key']} detail"] = p["secondary"]
        if p.get("summary"):
            templates[f"{p['key']} summary"] = p["summary"]
        if p.get("color_from"):
            templates[f"{p['key']} colour"] = build.color(p)
    for i, place in enumerate(build.chips()[:-1]):
        templates[f"row place {i} icon"] = place["chip"]["icon"]
        templates[f"row place {i} colour"] = place["chip"]["icon_color"]
    for label, template in templates.items():
        try:
            env.parse(template)
        except jinja2.TemplateSyntaxError as err:
            pytest.fail(f"{label}: {err}")


DOMAINS = {"sensor", "binary_sensor", "lock", "cover", "calendar", "input_boolean", "person", "climate",
           "media_player", "camera", "light", "update", "sun", "weather", "todo", "image"}


def test_state_objects_name_a_domain() -> None:
    """`states.sensor.x.last_changed` works; `states.x.last_changed` (domain
    left out) is None, and the template quietly renders the pill off for ever.
    This happened to the lightning pill."""
    pattern = re.compile(r"states\.([a-z_]+)\.([a-z0-9_]+)")
    for p in build.ALERTS:
        for field in ("tmpl", "secondary", "summary"):
            for domain, _ in pattern.findall(p.get(field) or ""):
                assert domain in DOMAINS, f"{p['key']} {field}: states.{domain}.… has no domain"


# ── the row ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("active", range(0, len(build.ALERTS) + 3))
def test_row_never_grows_past_one_line(active: int) -> None:
    """Card-mod isn't installed, so a Mushroom chips row wraps. The row is
    held to PLACES chips instead: with N pills on, min(N, PLACES) chips show,
    the last as "+N" once there are more pills than places."""
    row = build.row_card()
    shown = [c for c in row["chips"] if _visible(c["conditions"], active)]
    assert _visible(row["visibility"], active) == (active > 0), "row should hide when nothing is on"
    assert len(shown) == min(active, build.PLACES)
    overflow = [c for c in shown if c["chip"].get("content")]
    assert len(overflow) == (1 if active > build.PLACES else 0)


# ── the dashboard ───────────────────────────────────────────────────────────
def test_apply_touches_only_the_row_and_the_sub_page() -> None:
    """The weather chips row is Jan's and stays as it is; so does every other
    card and view."""
    before = _weather_dashboard()
    after = build.apply(before)
    cards = after["views"][0]["sections"][0]["cards"]
    assert cards[0] == before["views"][0]["sections"][0]["cards"][0], "weather row changed"
    assert build.is_row_card(cards[1])
    assert cards[2:] == before["views"][0]["sections"][0]["cards"][1:]
    assert after["views"][1] == before["views"][1]
    assert [v.get("path") for v in after["views"]][-1] == build.SUBVIEW


def test_apply_is_idempotent() -> None:
    """Running the sync twice must not stack a second row or sub-page."""
    once = build.apply(_weather_dashboard())
    assert build.apply(once) == once


def test_apply_refuses_a_rearranged_dashboard() -> None:
    """If the first card isn't the weather row any more, inserting "after it"
    would land the row somewhere random: stop instead."""
    dashboard = _weather_dashboard()
    dashboard["views"][0]["sections"][0]["cards"].pop(0)
    with pytest.raises(ValueError):
        build.apply(dashboard)


def test_every_pill_has_a_card_on_the_alerts_page() -> None:
    """A pill that is on but has no card leaves the row's icon pointing at
    nothing."""
    page = build.subview()
    active_cards = {c.get("entity") for c in page["sections"][0]["cards"]}
    for p in build.ALERTS:
        assert build.entity(p) in active_cards, p["key"]


# ── dismissing ──────────────────────────────────────────────────────────────
def test_critical_pills_exist() -> None:
    """A typo in CRITICAL would quietly make a safety alert dismissable."""
    assert build.CRITICAL <= {p["key"] for p in build.ALERTS}
    assert {"smoke_or_co", "front_door_open"} <= build.CRITICAL


def test_dismiss_helper_ids_match_their_titles() -> None:
    """sync.py creates each helper from a title; HA slugifies it into the id
    the row and the count look up. A mismatch means the pill can never be
    dismissed."""
    for p in build.ALERTS:
        if build.dismissable(p):
            title = f"Pill {p['key'].replace('_', ' ')} dismissed"
            slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
            assert f"input_datetime.{slug}" == build.dismissed_entity(p)


def test_critical_cards_have_no_dismiss_action() -> None:
    cards = {c["entity"]: c for c in build.subview()["sections"][0]["cards"] if c.get("entity")}
    for p in build.ALERTS:
        card = cards[build.entity(p)]
        assert ("hold_action" in card) == build.dismissable(p), p["key"]


def test_dismiss_templates_parse() -> None:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment()
    templates = [build.COUNT_TEMPLATE, build.SCRIPT["sequence"][1]["value_template"],
                 build.SCRIPT["sequence"][2]["data"]["timestamp"],
                 *build.SCRIPT["sequence"][0]["variables"].values()]
    for card in build.subview()["sections"][0]["cards"]:
        if card.get("hold_action"):
            templates += [card["secondary"], card["icon_color"]]
    for template in templates:
        env.parse(template)


def test_alerts_page_has_back_buttons_top_and_bottom() -> None:
    """The header arrow is small on a phone and scrolls out of view on a long
    page, so the first and the last section each carry a Back button to the
    same place the arrow goes."""
    page = build.subview()
    def backs(section):
        return [c for c in section["cards"] if c.get("type") == "button"
                and c.get("tap_action", {}).get("navigation_path") == page["back_path"]]
    assert page["sections"][0]["cards"][0] in backs(page["sections"][0]), "no Back button at the top"
    assert backs(page["sections"][-1]), "no Back button at the bottom"

"""The Mobile dashboard's alert pills (`dashboards/mobile-alerts/`).

Nothing here talks to Home Assistant (the integration has its own suite in
`tests_alert_pills/`). What goes wrong with this setup is quiet: the alert row
wraps onto a second line, a rebuild clobbers a card on the dashboard that has
nothing to do with alerts, a template has a typo and simply stays off, or the
dashboard looks for an entity or attribute the integration doesn't provide.
Each test below guards one of those.
"""
from __future__ import annotations

import importlib.util
import json
import re
import runpy
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
INTEGRATION = ROOT / "custom_components" / "alert_pills"
const = runpy.run_path(str(INTEGRATION / "const.py"))
logic = runpy.run_path(str(INTEGRATION / "logic.py"))

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


def _visible(conditions: list[dict], slots: int) -> bool:
    return all(str(slots) in c["state"] for c in conditions)


# ── pills.py ────────────────────────────────────────────────────────────────
def test_pill_keys_are_unique_and_slug_shaped() -> None:
    """The key is the entity id, `binary_sensor.pill_<key>`; `alert_pills.load`
    refuses the whole lot over one key that isn't slug-shaped or is repeated."""
    keys = [p["key"] for p in build.ALERTS]
    assert len(keys) == len(set(keys)), "duplicate pill keys"
    for key in keys:
        assert re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", key), key


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
    templates = {}
    for p in build.ALERTS:
        templates[f"{p['key']} state"] = p["tmpl"]
        templates[f"{p['key']} detail"] = p["secondary"]
        if p.get("summary"):
            templates[f"{p['key']} summary"] = p["summary"]
        if p.get("color_from"):
            templates[f"{p['key']} colour"] = build.color(p)
    for i, place in enumerate(build.chips()):
        templates[f"row place {i} icon"] = place["chip"]["icon"]
        templates[f"row place {i} colour"] = place["chip"]["icon_color"]
        templates[f"row place {i} content"] = place["chip"]["content"]
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
@pytest.mark.parametrize("slots", range(0, build.MAX_PLACES + 1))
def test_row_draws_exactly_the_slots_in_use(slots: int) -> None:
    """The integration says how many places are in use (`sensor.alert_pills_row`);
    the row draws that many chips and hides when there are none."""
    row = build.row_card()
    assert len(row["chips"]) == build.MAX_PLACES
    assert _visible(row["visibility"], slots) == (slots > 0), "row should hide when nothing is on"
    assert sum(_visible(c["conditions"], slots) for c in row["chips"]) == slots


@pytest.mark.parametrize("places", range(1, build.MAX_PLACES + 1))
def test_row_never_grows_past_one_line(places: int) -> None:
    """Card-mod isn't installed, so a Mushroom chips row wraps. With N pills on,
    min(N, places) places are used, the last as "+N" once there are more."""
    keys = [p["key"] for p in build.ALERTS]
    for active in range(0, len(keys) + 1):
        row, overflow = logic["row"](keys[:active], [], places)
        assert len(row) + (1 if overflow else 0) == min(active, places)
        assert len(row) + overflow == active
        assert (overflow > 0) == (active > places)


def test_card_only_pills_take_no_place() -> None:
    row, overflow = logic["row"](["a", "b", "c"], ["b"], 6)
    assert row == ["a", "c"] and overflow == 0


def test_switching_off_a_group_switches_off_its_pills() -> None:
    pill = {"key": "rain", "group": "Weather now"}
    assert logic["enabled"](pill, [], [])
    assert not logic["enabled"](pill, ["rain"], [])
    assert not logic["enabled"](pill, [], ["Weather now"])


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


def test_apply_replaces_the_row_from_before_the_integration() -> None:
    """The first sync after the switch must swap the old template-driven row
    for the new one, not stack a second row under it."""
    dashboard = _weather_dashboard()
    old_row = {"type": "custom:mushroom-chips-card", "chips": [],
               "visibility": [{"condition": "state", "entity": build.COUNT, "state": ["1", "2"]}]}
    dashboard["views"][0]["sections"][0]["cards"].insert(1, old_row)
    cards = build.apply(dashboard)["views"][0]["sections"][0]["cards"]
    assert old_row not in cards
    assert sum(build.is_row_card(c) for c in cards) == 1


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


def test_critical_cards_have_no_dismiss_action() -> None:
    cards = {c["entity"]: c for c in build.subview()["sections"][0]["cards"] if c.get("entity")}
    for p in build.ALERTS:
        card = cards[build.entity(p)]
        assert ("hold_action" in card) == build.dismissable(p), p["key"]


def test_card_templates_parse() -> None:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment()
    for card in build.subview()["sections"][0]["cards"]:
        if card.get("entity"):
            env.parse(card["secondary"])
            env.parse(card["icon_color"])


def test_hold_calls_the_integration() -> None:
    """A card whose hold action names a service that doesn't exist fails
    silently on the phone."""
    for card in build.subview()["sections"][0]["cards"]:
        if card.get("hold_action"):
            assert card["hold_action"]["perform_action"] == f"{const['DOMAIN']}.{const['SERVICE_TOGGLE_DISMISS']}"


def test_alerts_page_has_back_chips_top_and_bottom() -> None:
    """Every page of the Mobile dashboard starts with Mushroom's back chip; the
    Alerts page is long, so it has one at the bottom too."""
    page = build.subview()
    def has_back(card):
        return card.get("type") == "custom:mushroom-chips-card" and {"type": "back"} in card["chips"]
    assert has_back(page["sections"][0]["cards"][0]), "no back chip at the top"
    assert has_back(page["sections"][-1]["cards"][-1]), "no back chip at the bottom"


# ── the integration's side ──────────────────────────────────────────────────
def test_definitions_match_what_load_accepts() -> None:
    """`alert_pills.load` refuses unknown fields; a missing one leaves a pill
    without a template or icon."""
    defs = build.definitions()
    assert defs["groups"] == build.GROUPS
    for p in defs["pills"]:
        assert set(p) <= const["PILL_FIELDS"], p["key"]
        assert {"key", "name", "group", "icon", "color", "state"} <= set(p), p["key"]
        assert p["critical"] == (p["key"] in build.CRITICAL)
    json.dumps(defs)  # it goes over the websocket


def test_row_and_count_entities_are_the_integrations() -> None:
    assert build.COUNT == const["COUNT_ENTITY"] and build.ROW == const["ROW_ENTITY"]
    assert build.entity({"key": "x"}) == "binary_sensor.pill_x"


def test_integration_is_installable_through_hacs() -> None:
    """HACS wants `hacs.json` at the root and one integration under
    `custom_components/`; hassfest wants domain and name first, then the rest
    sorted, and a version for a custom integration."""
    assert json.loads((ROOT / "hacs.json").read_text())["name"]
    assert [d.name for d in (ROOT / "custom_components").iterdir() if d.is_dir()] == ["alert_pills"]
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["domain"] == const["DOMAIN"] == INTEGRATION.name
    keys = list(manifest)
    assert keys[:2] == ["domain", "name"] and keys[2:] == sorted(keys[2:])
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])


def test_every_service_is_described() -> None:
    yaml = pytest.importorskip("yaml")
    services = set(yaml.safe_load((INTEGRATION / "services.yaml").read_text()))
    strings = json.loads((INTEGRATION / "strings.json").read_text())
    assert services == set(strings["services"])
    assert services == {v for k, v in const.items() if k.startswith("SERVICE_")}
    assert (INTEGRATION / "translations" / "en.json").read_text() == (INTEGRATION / "strings.json").read_text()

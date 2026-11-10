"""The Health dashboard (`dashboards/health/`) and the pill that links to it.

It isn't in the sidebar, so the "HA health low" pill is the only way in. The
Pro card is HAGHS's own YAML, copied in; what breaks quietly is a copy that no
longer parses, one wired to another sensor than the pill reads, or a card type
that needs a frontend plugin this HA doesn't have.
"""
from __future__ import annotations

import importlib.util
import json
import re
import runpy

from conftest import ROOT

HERE = ROOT / "dashboards" / "health"
spec = importlib.util.spec_from_file_location("health_build", HERE / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
CONFIG = build.build()
PILLS = runpy.run_path(str(ROOT / "dashboards" / "mobile-alerts" / "pills.py"))
PILL = next(p for p in PILLS["ALERTS"] if p["key"] == "ha_health_low")


def _cards(card: dict) -> list[dict]:
    return [card] + [c for sub in card.get("cards", []) for c in _cards(sub)]


def test_build_is_plain_json() -> None:
    assert json.loads(json.dumps(CONFIG)) == CONFIG


def test_link_is_a_view_of_the_dashboard() -> None:
    assert build.LINK in {f"/{build.DASHBOARD}/{v['path']}" for v in CONFIG["views"]}


def test_the_health_pill_links_to_the_dashboard() -> None:
    assert PILL.get("link") == build.LINK


def test_pro_card_reads_the_sensor_the_pill_reads() -> None:
    """A renamed sensor would leave the card saying "offline" while the pill
    still works, or the other way round: both must name the same one."""
    used = set(re.findall(r"\bsensor\.[a-z0-9_]+", json.dumps(CONFIG)))
    assert used == {build.SCORE} and PILLS["HEALTH"] == build.SCORE, sorted(used)


def test_pro_card_is_the_upstream_stack() -> None:
    """The copy parses into HAGHS's gauge plus markdown cards, nothing lost in the copy."""
    card = build.pro_card()
    assert card["type"] == "vertical-stack"
    assert card["cards"][0] == {**card["cards"][0], "type": "gauge", "entity": build.SCORE}
    titles = [c.get("title", "") for c in card["cards"][1:]]
    assert all(c["type"] == "markdown" for c in card["cards"][1:])
    assert any("Repairs" in t for t in titles) and any("Zombie" in t for t in titles), titles


def test_only_core_cards_besides_the_back_chip() -> None:
    """The page needs no frontend plugin beyond Mushroom (the back chip, as on
    the VPN page): HAGHS's card is all core cards."""
    custom = {c["type"] for s in CONFIG["views"][0]["sections"] for c in _cards({"cards": s["cards"]})[1:]
              if c["type"].startswith("custom:")}
    assert custom == {"custom:mushroom-chips-card"}

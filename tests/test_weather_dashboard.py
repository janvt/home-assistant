"""The Weather dashboard (`dashboards/weather/`).

`build.py` writes the whole dashboard, so the failures to guard against are
the ones a dashboard shows as an empty or dead card rather than an error: a
"details" button or back arrow pointing at a view that isn't there, a place
left out of the comparison graphs, an IMIS station with no description, a
template that doesn't parse.
"""
from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from conftest import ROOT

HERE = ROOT / "dashboards" / "weather"


def _load(name: str):
    sys.path.insert(0, str(HERE))
    try:
        spec = importlib.util.spec_from_file_location(f"weather_{name}", HERE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(HERE))


build = _load("build")
CONFIG = build.build()
VIEWS = CONFIG["views"]


def _walk(node, key):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from _walk(v, key)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, key)


def test_view_paths_are_unique_and_overview_comes_first() -> None:
    """The first view is what the dashboard opens on."""
    paths = [v["path"] for v in VIEWS]
    assert len(paths) == len(set(paths))
    assert paths[0] == "overview" and not VIEWS[0].get("subview")
    assert all(v.get("subview") for v in VIEWS[1:]), "only the Overview belongs in the top bar"


def test_every_link_lands_on_a_view() -> None:
    """A details button, a tapped tile or a back arrow to a missing path just
    shows an empty page."""
    paths = {f"{build.BASE}/{v['path']}" for v in VIEWS}
    targets = set(_walk(CONFIG, "navigation_path")) | set(_walk(CONFIG, "back_path"))
    assert targets, "no links found: the walk is broken"
    assert targets <= paths, f"links to nowhere: {sorted(targets - paths)}"


def test_every_place_has_a_page_and_an_overview_section() -> None:
    linked = set(_walk(VIEWS[0], "navigation_path"))
    for place in [*build.LOCATIONS, *[build._mountain(m) for m in build.MOUNTAINS]]:
        assert f"{build.BASE}/{place['path']}" in linked, place["title"]


def test_comparison_graphs_cover_every_location() -> None:
    compare = build.compare_section()
    for graph in compare["cards"][1:]:
        assert len(graph["entities"]) == len(build.LOCATIONS), graph["title"]


def test_imis_stations_are_described() -> None:
    """An IMIS suffix without an entry in IMIS would crash the build; one
    with an unknown sensor name would show a tile without a label."""
    used = [s for l in build.LOCATIONS for s in l.get("imis", [])] + \
           [m["imis"] for m in build.MOUNTAINS if m.get("imis")]
    assert used
    for sfx in used:
        station = build.IMIS[sfx]
        assert set(station["sensors"]) <= set(build.IMIS_NAMES), sfx
        assert station["name"] and station["elevation"] > 1000, sfx


def test_templates_parse() -> None:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment()
    for name in ("as_datetime", "as_local"):
        env.filters.setdefault(name, lambda value, *args: value)
    for content in _walk(CONFIG, "content"):
        try:
            env.parse(content)
        except jinja2.TemplateSyntaxError as err:
            pytest.fail(f"{err}: {content[:80]}")


def test_build_is_plain_json() -> None:
    """HA stores the config as JSON: a stray tuple or set would not survive."""
    assert json.loads(json.dumps(CONFIG)) == CONFIG


def test_rivers_are_well_formed() -> None:
    """The weather sync renames river sensors by unique id <station>_<condition>,
    so a condition HA doesn't know never gets a sensor, and a slug used twice
    would rename two stations onto one entity id. Danger thresholds must rise
    or the computed flood level is wrong."""
    slugs = [r["slug"] for r in build.RIVERS]
    assert len(slugs) == len(set(slugs))
    for r in build.RIVERS:
        assert r["conditions"] and set(r["conditions"]) <= {"discharge", "level", "temperature"}, r["title"]
        if r.get("danger"):
            assert r["danger"] == sorted(r["danger"]) and "discharge" in r["conditions"], r["title"]


def test_every_page_has_its_radar_loop() -> None:
    """Each place's page shows its own entry's radar loop, not another's."""
    pages = {v["path"]: v for v in VIEWS[1:]}
    places = [*build.LOCATIONS, *[build._mountain(m) for m in build.MOUNTAINS]]
    for place in places:
        entities = set(_walk(pages[place["path"]], "entity"))
        assert f"image.{place['weather'].split('.')[1]}_radar_loop" in entities, place["title"]


def test_earthquake_page_is_reachable_and_reads_the_entry() -> None:
    """The page sits behind the Overview's details button; its map finds the
    quakes by the entry's source, so a wrong source is an empty map, not an error."""
    linked = set(_walk(VIEWS[0], "navigation_path"))
    assert f"{build.BASE}/{build.QUAKES_PATH}" in linked
    page = next(v for v in VIEWS if v["path"] == build.QUAKES_PATH)
    maps = [c for c in _walk(page, "geo_location_sources")]
    assert maps == [[build.EARTHQUAKES["source"]]]


def test_earthquake_pill_matches_the_page() -> None:
    """The pill and the page are two files naming the same SED entry: re-adding
    the entry renames its sensors, and the pill's Details button opens the page.
    Changing one without the other leaves an unavailable row or a dead button."""
    import runpy
    pills = runpy.run_path(str(ROOT / "dashboards" / "mobile-alerts" / "pills.py"))
    assert pills["QUAKE"] == "sensor." + build.EARTHQUAKES["sensors"]
    assert pills["QUAKES_LINK"] == f"{build.BASE}/{build.QUAKES_PATH}"
    assert f"'{build.EARTHQUAKES['source']}'" in pills["FELT"]
    pill = next(p for p in pills["ALERTS"] if p["key"] == "earthquake_felt")
    assert pill["link"] == pills["QUAKES_LINK"]

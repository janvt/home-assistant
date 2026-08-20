"""Each deck's `configuration.yaml`, validated the way the app validates it.

The app loads these through pydantic models with `extra="forbid"`, so a
misspelled field is caught at startup — but only at startup, on the machine
with the deck attached, which for the Pi means "after a deploy". Everything
here runs the real loader against both configs offline.

The checks that aren't just "does it parse" cover failures pydantic can't see:
a service in the reserved `mac.` domain that no handler implements (logged and
dropped), a `go-to-page` naming a page that doesn't exist, a synthetic entity
`ext/` doesn't provide (KeyError while drawing the first frame), and a template
that fails to render (the app logs and falls back to the RAW TEXT, so the deck
tries to load an icon file literally named `{{ ... }}`).
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from conftest import (
    DECKS,
    DEVICE,
    TEMPLATE_PROBES,
    config_path,
    entity_ids,
    synthetic_state,
)


@pytest.fixture(scope="session")
def configs(app: Any) -> dict[str, Any]:
    return {deck: app.Config.load(config_path(deck)) for deck in DECKS}


@pytest.mark.parametrize("deck", DECKS)
def test_config_loads_through_the_real_models(configs: dict, deck: str) -> None:
    cfg = configs[deck]
    assert cfg.pages, "no pages"
    assert len({page.name for page in cfg.pages}) == len(cfg.pages), "duplicate page names"


@pytest.mark.parametrize("deck", DECKS)
def test_every_key_slot_is_declared(configs: dict, deck: str) -> None:
    """Buttons fill left→right, top→bottom, so a gap has to be an explicit
    `special_type: empty` placeholder — otherwise every later key shifts into
    the wrong column. And pressing a key with no entry at all trips an
    `assert button is not None` inside the app's key handler.
    """
    expected = DEVICE[deck]["keys"]
    for page in configs[deck].pages:
        assert len(page.buttons) == expected, (
            f"{deck} page {page.name!r} declares {len(page.buttons)} of "
            f"{expected} keys — later keys will sit in the wrong columns"
        )


@pytest.mark.parametrize("deck", DECKS)
def test_dial_entries_fit_the_hardware(configs: dict, deck: str) -> None:
    """A dial entry past the device's dial count is unreachable — it renders
    nowhere and turning anything never triggers it.
    """
    limit = DEVICE[deck]["dials"]
    for page in configs[deck].pages:
        physical = page.sort_dials()[:limit]
        reachable = {id(d) for pair in physical for d in pair if d is not None}
        orphans = [d.entity_id for d in page.dials if id(d) not in reachable]
        assert orphans == [], (
            f"{deck} page {page.name!r}: dial entries {orphans} fall past dial "
            f"{limit} and can never fire"
        )


def test_plus_dial_pairing_is_turn_then_push(configs: dict) -> None:
    """The Pi deck pairs each dial's TURN with a PUSH by ADJACENCY: the app
    merges two consecutive entries only when their `dial_event_type` differs.
    Reordering them silently splits the pairs across different physical dials,
    which is why the config says "do not reorder".
    """
    page = configs["plus"].pages[0]
    pairs = page.sort_dials()[: DEVICE["plus"]["dials"]]
    assert [(turn.dial_event_type, push.dial_event_type if push else None)
            for turn, push in pairs] == [("TURN", "PUSH")] * 4


@pytest.mark.parametrize("deck", DECKS)
def test_xl_dials_are_turn_only(configs: dict, deck: str) -> None:
    """The XL keeps every dial TURN-only on purpose.

    The app's eager local re-render looks a dial up by its RAW list index while
    being handed the SORTED index. Those only agree while no dial has a paired
    PUSH, so mixing paired and unpaired dials redraws the wrong strip segment.
    """
    if deck != "plus-xl":
        pytest.skip("the Plus deliberately pairs TURN with PUSH; see the test above")
    for page in configs[deck].pages:
        assert {dial.dial_event_type for dial in page.dials} <= {"TURN"}
        assert page.sort_dials()[: len(page.dials)] == [
            (dial, None) for dial in page.dials
        ], "a paired dial would desynchronise the eager redraw index"


# ── services and entities ───────────────────────────────────────────────────
def _all_services(cfg: Any) -> set[str]:
    services = set()
    for page in cfg.pages:
        for item in [*page.buttons, *page.dials]:
            if item.service:
                services.add(item.service)
            # `long_press` is a bare dict on the model, not a nested Button.
            long_press = getattr(item, "long_press", None) or {}
            if long_press.get("service"):
                services.add(long_press["service"])
    return services


@pytest.mark.parametrize("deck", DECKS)
def test_service_names_are_domain_qualified(configs: dict, deck: str) -> None:
    for service in _all_services(configs[deck]):
        assert re.fullmatch(r"[a-z_]+\.[a-z_]+", service), f"odd service {service!r}"


@pytest.mark.parametrize("deck", DECKS)
def test_every_local_service_has_a_handler(ext: Any, configs: dict, deck: str) -> None:
    """`mac.*` is a reserved local domain intercepted before the websocket. An
    unregistered name there is not an error the user sees — `dispatch()` logs
    "Unknown local action" and returns, so the key just does nothing.
    """
    local = {s for s in _all_services(configs[deck]) if s.startswith(f"{ext.actions.DOMAIN}.")}
    assert sorted(local - set(ext.actions.ACTIONS)) == [], (
        f"known actions: {sorted(ext.actions.ACTIONS)}"
    )
    if deck == "plus":
        assert local == set(), "the Pi deck is a pure HA client — it has no mac.* bridge"


@pytest.mark.parametrize("deck", DECKS)
def test_every_synthetic_entity_is_provided_by_ext(ext: Any, deck: str) -> None:
    """`get_states` seeds `mac.*` entities into `complete_state` at connect
    time. One the providers don't supply is a KeyError while the app indexes
    `complete_state[dial.entity_id]` drawing the first dial frame — i.e. the
    deck fails to start, not just that one key.
    """
    provided = {provider.entity_id for provider in ext.state.PROVIDERS}
    used = {eid for eid in entity_ids(deck) if eid.startswith(f"{ext.actions.DOMAIN}.")}
    assert sorted(used - provided) == [], f"ext/ provides only {sorted(provided)}"


@pytest.mark.parametrize("deck", DECKS)
def test_entity_ids_are_domain_qualified(deck: str) -> None:
    assert entity_ids(deck), "no entity ids found — has the config moved?"
    for eid in entity_ids(deck):
        assert re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", eid), f"malformed entity id {eid!r}"


@pytest.mark.parametrize("deck", DECKS)
def test_page_navigation_targets_exist(configs: dict, deck: str) -> None:
    """`go-to-page` takes a page NAME. A typo leaves a key that looks like
    navigation and does nothing.
    """
    cfg = configs[deck]
    names = {page.name for page in cfg.pages}
    nav = [
        button
        for page in cfg.pages
        for button in page.buttons
        if button.special_type in ("go-to-page", "next-page", "previous-page")
    ]
    if len(cfg.pages) > 1:
        assert nav, f"{deck} has {len(cfg.pages)} pages and no way to move between them"
    targets = {b.special_type_data for b in nav if b.special_type == "go-to-page"}
    assert sorted(t for t in targets if t not in names) == [], f"pages are {sorted(names)}"


def test_both_pages_can_be_reached_from_each_other(configs: dict) -> None:
    """Two pages, a nav key each way — losing one strands you on that page
    (there is no next/previous-page key on either deck's XL layout)."""
    cfg = configs["plus-xl"]
    for page in cfg.pages:
        targets = {
            button.special_type_data
            for button in page.buttons
            if button.special_type == "go-to-page"
        }
        others = {other.name for other in cfg.pages} - {page.name}
        assert targets >= others, f"page {page.name!r} cannot reach {others - targets}"


@pytest.mark.parametrize("deck", DECKS)
def test_door_opening_keys_have_an_accidental_press_guard(configs: dict, deck: str) -> None:
    """`lock.open` unlatches a physical door. Those keys carry a `delay`, which
    makes the press a countdown a second press cancels.
    """
    unguarded = [
        button.entity_id
        for page in configs[deck].pages
        for button in page.buttons
        if button.service == "lock.open" and not button.delay
    ]
    assert unguarded == [], f"{deck}: door keys with no press guard: {unguarded}"


# ── templates ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("deck", DECKS)
@pytest.mark.parametrize("probe", TEMPLATE_PROBES)
def test_every_template_renders(app: Any, configs: dict, deck: str, probe: int) -> None:
    """A broken template is NOT loud: `_render_jinja` catches the error, logs,
    and returns the template source unchanged. The app then treats `{{ ... }}`
    as a literal icon path or label. So "renders" means "no Jinja syntax
    survives".

    Run once per probe value so both arms of every conditional are exercised.
    """
    state = synthetic_state(deck, probe)
    leftovers: list[str] = []
    for page in configs[deck].pages:
        for button in page.buttons:
            rendered = button.rendered_template_button(state)
            for field in button.templatable():
                value = getattr(rendered, field, None)
                if isinstance(value, str) and ("{{" in value or "{%" in value):
                    leftovers.append(f"{page.name}/button {field}: {value[:70]}")
        for dial in page.dials:
            assert dial.entity_id in state, (
                f"{dial.entity_id} was not collected by conftest.entity_ids()"
            )
            dial.update_attributes(state[dial.entity_id])
            rendered = dial.rendered_template_dial(state)
            for field in dial.templatable():
                value = getattr(rendered, field, None)
                if isinstance(value, str) and ("{{" in value or "{%" in value):
                    leftovers.append(f"{page.name}/{dial.entity_id} {field}: {value[:70]}")
    assert leftovers == []


@pytest.mark.parametrize("deck", DECKS)
def test_icon_templates_resolve_to_a_single_path(app: Any, configs: dict, deck: str) -> None:
    """An icon template must produce ONE path, not a fragment or a joined pair.
    `~` concatenation with a missing `else` arm renders empty, and the app then
    tries to open the deck's icons directory itself.
    """
    for probe in TEMPLATE_PROBES:
        state = synthetic_state(deck, probe)
        for page in configs[deck].pages:
            for button in page.buttons:
                icon = button.rendered_template_button(state).icon
                if icon is None:
                    continue
                assert icon.endswith(".png"), f"{page.name}: icon {icon!r}"
                assert icon.count(".png") == 1, f"{page.name}: two paths in {icon!r}"

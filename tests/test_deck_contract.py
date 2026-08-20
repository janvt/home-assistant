"""The contract between a deck's `spec.py`, its `configuration.yaml`, and the
images the renderer produces.

These three have to agree by hand, and nothing at runtime checks them. When
they disagree the deck does not crash — it degrades quietly:

  * an `icon:` naming a file the renderer never produces raises inside the
    app's per-key render, so that ONE key silently does nothing while the rest
    of the deck looks fine. (This is exactly how a new key can appear to be
    "not implemented" when the code is fine and only the image is missing.)
  * an image the config never references is dead weight that reads as live.
  * a dial whose icon template computes a filename outside the rendered set
    goes blank at those positions only — typically at the extremes, where it
    is least likely to be noticed while testing.

So: every icon named is produced, every icon produced is named, and every
position a dial can physically reach resolves to a frame that exists.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from conftest import (
    DECKS,
    DEVICE,
    STREAMDECK,
    config_path,
    config_text,
    expected_icon_names,
    referenced_icon_dirs,
    referenced_icons,
    spec,
    synthetic_state,
)


@pytest.mark.parametrize("deck", DECKS)
def test_every_icon_the_config_names_is_rendered(gen: ModuleType, deck: str) -> None:
    """The failure this catches: one dead key on an otherwise healthy deck."""
    keys, dials = expected_icon_names(gen, deck)
    missing = sorted(referenced_icons(deck) - keys - dials)
    assert missing == [], (
        f"decks/{deck}/configuration.yaml references images that "
        f"generate_icons.py does not produce from decks/{deck}/spec.py: {missing}"
    )


@pytest.mark.parametrize("deck", DECKS)
def test_every_rendered_key_image_is_used_by_the_config(
    gen: ModuleType, deck: str,
) -> None:
    """The reverse direction — a leftover from a layout change.

    Dial frames are exempt: they are addressed by a computed suffix, so the
    config names only a prefix (see the reachability test below).
    """
    keys, _dials = expected_icon_names(gen, deck)
    orphans = sorted(keys - referenced_icons(deck))
    assert orphans == [], (
        f"decks/{deck}/spec.py renders key images nothing references: {orphans}"
    )


@pytest.mark.parametrize("deck", DECKS)
def test_icon_paths_are_absolute_and_point_at_this_deck(deck: str) -> None:
    """The app resolves a RELATIVE icon path against its own installed package
    directory, not the cwd, so every path has to be absolute — and it has to be
    absolute in the right frame of reference for that deployment (a container
    path on the Pi, a checkout path on the Mac).
    """
    dirs = referenced_icon_dirs(deck)
    assert dirs, "no icon paths found at all — has the config moved?"
    assert all(d.startswith("/") for d in dirs), f"relative icon paths: {sorted(dirs)}"

    roots = {d.split("/icons/")[0] + "/icons" for d in dirs}
    assert len(roots) == 1, (
        f"decks/{deck} mixes icon roots {sorted(roots)} — a half-finished path "
        f"rename leaves some keys pointing at a directory that isn't there"
    )
    root = roots.pop()
    assert root.endswith(DEVICE[deck]["icon_root"]), (
        f"icon root {root!r} does not end with the expected "
        f"{DEVICE[deck]['icon_root']!r} for this deployment"
    )
    assert dirs <= {f"{root}/", f"{root}/dials/"}, f"unexpected icon subdirs: {dirs}"


@pytest.mark.parametrize("deck", DECKS)
def test_the_xl_icon_root_resolves_inside_this_checkout(deck: str) -> None:
    """The Mac deck runs natively out of the checkout, so its absolute icon
    root should be THIS repo's path. Skipped when the repo has been moved or
    cloned elsewhere — the path is a property of that machine, not of the code.
    """
    if DEVICE[deck]["icon_root"].startswith("/"):
        pytest.skip(f"{deck} addresses icons by container path, not checkout path")
    root = Path(next(iter(referenced_icon_dirs(deck))).split("/icons/")[0] + "/icons")
    expected = STREAMDECK / "decks" / deck / "icons"
    if root.parent != expected.parent:
        pytest.skip(f"checkout is at {expected.parent}, config points at {root.parent}")
    assert root == expected


@pytest.mark.parametrize("deck", DECKS)
def test_dial_frame_prefixes_match_the_spec(gen: ModuleType, deck: str) -> None:
    """Dial frames are named `<slug>_<pct>.png` by the renderer and addressed by
    a templated suffix in the config, so the two only meet at the slug.
    """
    text = config_text(deck)
    used = set(re.findall(r"/icons/dials/([a-z_]+?)_(?:\{\{|muted|\"|\d)", text))
    declared = {slug for slug, _style, _label in spec(gen, deck).DIALS}
    assert used == declared, (
        f"dial slugs disagree — config uses {sorted(used)}, "
        f"spec.py declares {sorted(declared)}"
    )


# ── dial reachability ───────────────────────────────────────────────────────
def _turn_dials(app: Any, deck: str) -> list[tuple[str, Any]]:
    """Every TURN dial with a templated frame icon, as (page name, dial)."""
    cfg = app.Config.load(config_path(deck))
    return [
        (page.name, dial)
        for page in cfg.pages
        for dial in page.dials
        if dial.dial_event_type == "TURN" and dial.icon and "dials/" in dial.icon
    ]


def _reachable_values(attrs: dict[str, Any]) -> list[float]:
    """Values a dial can actually be at.

    The starting point comes from Home Assistant (any value in range), and each
    detent adds `step` and clamps, so in practice the whole interval is
    reachable — not just a grid. Sampled densely, plus the exact ends and the
    detent grids walked in from each end, which is where rounding in the icon
    template goes wrong.
    """
    lo, hi = float(attrs["min"]), float(attrs["max"])
    step = abs(float(attrs["step"]))
    dense = [lo + (hi - lo) * i / 400 for i in range(401)]
    grid_up = [min(hi, lo + k * step) for k in range(int((hi - lo) / step) + 2)]
    grid_down = [max(lo, hi - k * step) for k in range(int((hi - lo) / step) + 2)]
    nudges = [lo, hi, lo + (hi - lo) * 1e-9, hi - (hi - lo) * 1e-9]
    return dense + grid_up + grid_down + nudges


@pytest.mark.parametrize("deck", DECKS)
def test_every_reachable_dial_position_has_a_frame(
    app: Any, gen: ModuleType, deck: str,
) -> None:
    """A dial must render at every value it can hold, including both ends.

    Off-by-one rounding in these templates (they convert native units to a
    percentage, then round to the frame step) produces a filename like
    `..._102.png` or `..._-0.png` only at the extremes, so it survives casual
    testing and then shows up as a dial that goes blank when you turn it all
    the way down.
    """
    _keys, frames = expected_icon_names(gen, deck)
    # Both arms of every `if state_attr(...)` in a dial icon: built once, since
    # the state does not depend on the dial's position.
    states = [synthetic_state(deck, probe) for probe in (0, 1)]
    problems: list[str] = []
    for page_name, dial in _turn_dials(app, deck):
        attrs = dict(dial.attributes or {})
        rendered: set[str] = set()
        for value in _reachable_values(attrs):
            dial._attributes = attrs | {"state": value}
            for state in states:
                name = Path(app._render_jinja(dial.icon, state, dial)).name
                rendered.add(name)
                if name not in frames:
                    problems.append(
                        f"{page_name}/{dial.entity_id} at {value:g} -> {name}",
                    )
        assert len(rendered) > 1, (
            f"{page_name}/{dial.entity_id} renders one frame ({rendered}) for "
            f"every position — the icon template ignores dial_value()"
        )
    assert sorted(set(problems))[:10] == []


@pytest.mark.parametrize("deck", DECKS)
def test_one_detent_never_skips_a_frame(app: Any, gen: ModuleType, deck: str) -> None:
    """One click should move the gauge at most one frame, so the display keeps
    up with the finger instead of jumping.

    Only the upper bound is enforced. Finer-than-frame steps are legitimate:
    the Settings page's deck-brightness dial deliberately moves 2% per detent
    against 5% frames, so its gauge redraws every second or third click.
    """
    styles = {slug: style for slug, style, _label in spec(gen, deck).DIALS}
    for page_name, dial in _turn_dials(app, deck):
        attrs = dial.attributes or {}
        span = float(attrs["max"]) - float(attrs["min"])
        detent_pct = abs(float(attrs["step"])) / span * 100
        slug = re.search(r"/icons/dials/([a-z_]+?)_(?:\{\{|muted|\"|\d)",
                         dial.icon).group(1)
        frame_step = gen.DIAL_STYLES[styles[slug]][2]
        assert detent_pct <= frame_step * 1.5, (
            f"{deck} {page_name}/{slug}: one detent moves {detent_pct:.1f}% but "
            f"frames exist every {frame_step}% — the gauge skips positions"
        )

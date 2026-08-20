"""Shared fixtures and helpers for the repo test suite.

Three things make this repo awkward to test, and most of what's here exists to
deal with them:

  * The deck code is loose scripts under `streamdeck/`, not an installed
    package, so `generate_icons.py` and each deck's `spec.py` are imported by
    path (`gen`, `spec()`).
  * `ext/` wraps an upstream app that is pip-installed from git. Tests needing
    it SKIP rather than fail when it's missing, so the suite still runs in a
    bare checkout — CI installs it, so nothing skips there.
  * Icon rendering needs the Material Design Icons webfont, a build artifact
    fetched on first render into `streamdeck/.iconbuild/`. Tests needing real
    glyph codepoints skip when that cache is cold, unless the network is
    explicitly allowed (see `mdi_codepoints`).

The deck facts below (key counts, dial counts, icon path roots) are the
expectations the configs are written against — they are asserted, not derived,
so a config drifting away from its hardware is a failure rather than a new
"truth" the tests quietly adopt.
"""
from __future__ import annotations

import functools
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
STREAMDECK = ROOT / "streamdeck"
DECKS_DIR = STREAMDECK / "decks"
M5STACK = ROOT / "m5stack"

DECKS = ("plus", "plus-xl")

# What each deck's hardware actually is. `icon_root` is how that deployment
# addresses this repo's icons dir: the Pi runs in a container where the
# checkout is bind-mounted at /app, the Mac runs natively out of the checkout.
# The app resolves a RELATIVE icon path against its own installed package
# assets dir rather than the cwd, so both must be absolute.
DEVICE = {
    "plus":    {"keys": 8,  "dials": 4, "key_px": 120, "icon_root": "/app/icons"},
    "plus-xl": {"keys": 36, "dials": 6, "key_px": 112,
                "icon_root": "streamdeck/decks/plus-xl/icons"},
}

# Attribute values used when rendering config templates offline. Rendering
# happens twice, once per value, so both branches of every `if state_attr(...)`
# get exercised; 1/0 stand in for true/false and survive `| float(0)` too.
TEMPLATE_PROBES = (0, 1)


def _import_by_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot import {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def gen() -> ModuleType:
    """The shared icon renderer, `streamdeck/generate_icons.py`."""
    return _import_by_path("generate_icons", STREAMDECK / "generate_icons.py")


@pytest.fixture(scope="session")
def app() -> Any:
    """The upstream Stream Deck app, or skip.

    Installed by `task xl:install` (and by CI) from git, not PyPI — Plus XL
    support is not in any release.
    """
    return pytest.importorskip(
        "home_assistant_streamdeck_yaml",
        reason="upstream app not installed — `task xl:install`, or "
               "pip install 'home-assistant-streamdeck-yaml @ git+https://"
               "github.com/basnijholt/home-assistant-streamdeck-yaml@main'",
    )


@pytest.fixture(scope="session")
def ext() -> Any:
    """The `ext` package (local `mac.*` actions), or skip."""
    sys.path.insert(0, str(STREAMDECK))
    pytest.importorskip("home_assistant_streamdeck_yaml", reason="ext needs the app")
    # The package deliberately does not import its own submodules (`ext/run.py`
    # installs the wrappers), so name them explicitly.
    import ext as ext_pkg
    from ext import actions, mac, state, wrap

    ext_pkg.actions, ext_pkg.mac, ext_pkg.state, ext_pkg.wrap = actions, mac, state, wrap
    return ext_pkg


@pytest.fixture(scope="session")
def mdi_codepoints(gen: ModuleType) -> dict[str, str]:
    """Real MDI icon-name -> codepoint map from the build cache.

    Skips instead of downloading, so an offline run is quiet rather than slow
    or flaky. Set HASD_TEST_NETWORK=1 (CI does) to populate the cache.
    """
    css = gen.BUILD / "mdi.css"
    if not css.exists() and os.environ.get("HASD_TEST_NETWORK") == "1":
        gen._fetch(
            f"https://cdn.jsdelivr.net/npm/@mdi/font@{gen.MDI_VERSION}/css/"
            f"materialdesignicons.css",
            css,
        )
    if not css.exists():
        pytest.skip(
            f"no MDI css cache at {css} — run `task xl:icons` once, or set "
            f"HASD_TEST_NETWORK=1 to let the tests fetch it",
        )
    return gen._codepoints(css)


@pytest.fixture(scope="session")
def mdi_font(gen: ModuleType) -> str:
    """Path to the real MDI webfont, or skip (same policy as `mdi_codepoints`)."""
    ttf = gen.BUILD / "mdi.ttf"
    if not ttf.exists() and os.environ.get("HASD_TEST_NETWORK") == "1":
        gen._fetch(
            f"https://cdn.jsdelivr.net/npm/@mdi/font@{gen.MDI_VERSION}/fonts/"
            f"materialdesignicons-webfont.ttf",
            ttf,
        )
    if not ttf.exists():
        pytest.skip(f"no MDI font cache at {ttf} (see mdi_codepoints)")
    return str(ttf)


# ── deck data ───────────────────────────────────────────────────────────────
def spec(gen: ModuleType, deck: str) -> ModuleType:
    """Import `decks/<deck>/spec.py` the same way the renderer does."""
    return gen.load_spec(deck)


def config_path(deck: str) -> Path:
    return DECKS_DIR / deck / "configuration.yaml"


@functools.lru_cache(maxsize=None)
def config_text(deck: str) -> str:
    """Every string scalar in a deck config, joined — keys, values, templates.

    Deliberately built from the PARSED YAML rather than the raw file: the
    configs are heavily commented, and comments mention icon paths and entity
    ids while documenting them ("the Pi's config gets away with /app/icons/..."
    lives in the XL config). Scanning raw text picks those up as if they were
    live references. Parsing first also keeps both arms of an
    `{{ a if cond else b }}` template visible, which no single render would be.
    """
    import yaml

    strings: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            strings.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(yaml.safe_load(config_path(deck).read_text()))
    return "\n".join(strings)


@functools.lru_cache(maxsize=None)
def expected_icon_names(gen: ModuleType, deck: str) -> tuple[set[str], set[str]]:
    """(key images, dial frames) that `build(deck)` should produce.

    A deliberate mirror of `generate_icons.build()`, so the cheap contract
    tests need neither fonts nor network. `test_icon_render.py` pins it to
    reality by running the real renderer and diffing against this — if build()
    ever changes shape, that guard fails rather than this drifting unnoticed.
    """
    keys: set[str] = set()
    dials: set[str] = set()
    module = spec(gen, deck)
    for name, _mdi, _label, _style in getattr(module, "STATEFUL", []):
        keys |= {f"{name}_on.png", f"{name}_off.png"}
    for name, _mdi, _label, _style in getattr(module, "ACTION", []):
        keys.add(f"{name}.png")
    for name, _mdi, _label in getattr(module, "INFO", []):
        keys |= {f"{name}_{style}.png" for style in gen.INFO_THRESHOLD_STYLES}
    for slug, style, _label in getattr(module, "DIALS", []):
        step = gen.DIAL_STYLES[style][2]
        dials |= {f"{slug}_{pct}.png" for pct in range(0, 101, step)}
        if style == "volume":
            dials.add(f"{slug}_muted.png")
    return keys, dials


# Every icon filename the YAML mentions, anywhere — including both arms of an
# `{{ a if cond else b }}` template, which no single render would reveal.
_PNG_RE = re.compile(r"([\w-]+\.png)")
# The directory part, e.g. "/app/icons/" or "/app/icons/dials/".
_ICON_DIR_RE = re.compile(r"([\w./-]*?/icons/(?:dials/)?)")


@functools.lru_cache(maxsize=None)
def referenced_icons(deck: str) -> set[str]:
    return set(_PNG_RE.findall(config_text(deck)))



@functools.lru_cache(maxsize=None)
def referenced_icon_dirs(deck: str) -> set[str]:
    return set(_ICON_DIR_RE.findall(config_text(deck)))


@functools.lru_cache(maxsize=None)
def entity_ids(deck: str) -> set[str]:
    """Every entity id a deck config names.

    Two sources, because the app reads them from two places: the `entity_id` /
    `linked_entity` fields (a scalar, or a list when a service targets several
    at once), and the ids quoted inside `is_state()` / `state_attr()` template
    calls, which the fields never mention.
    """
    import yaml

    ids: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("entity_id", "linked_entity"):
                    ids.update([value] if isinstance(value, str) else value or [])
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(yaml.safe_load(config_path(deck).read_text()))
    ids |= set(re.findall(
        r"(?:is_state_attr|state_attr|is_state|states)\(\s*[\"']([\w.]+)[\"']",
        config_text(deck)))
    # Templated values are not entity ids, e.g. `entity_id: '{{ ... }}'`.
    return {eid for eid in ids if "{" not in eid}


@functools.lru_cache(maxsize=None)
def attribute_names(deck: str) -> set[str]:
    """Attribute names read via `state_attr()` / `is_state_attr()`."""
    return set(re.findall(
        r"(?:is_state_attr|state_attr)\(\s*[\"'][\w.]+[\"']\s*,\s*[\"'](\w+)[\"']",
        config_text(deck)))


def synthetic_state(deck: str, probe: int) -> dict[str, dict[str, Any]]:
    """A `complete_state` covering every entity the config mentions.

    Real HA state is not available offline, and the point here is template
    mechanics rather than values: every attribute the config reads is present
    and set to `probe`, so templates render instead of erroring, and running
    twice with 0/1 walks both arms of every conditional.
    """
    attrs = {name: probe for name in attribute_names(deck)}
    # Attributes dials read via `state_attribute:` rather than a template.
    attrs |= {"volume_level": probe, "brightness": probe, "current_position": probe,
              "level": probe, "muted": probe, "is_volume_muted": probe}
    return {
        eid: {"state": str(probe), "attributes": dict(attrs)}
        for eid in entity_ids(deck)
    }


# ── repo helpers ────────────────────────────────────────────────────────────
def git_tracked_files() -> list[str]:
    out = subprocess.run(  # noqa: S603
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.split()

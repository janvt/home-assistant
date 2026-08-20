"""The Home Assistant YAML at the repo root: `automations/` and
`ha-scene-tracker.yaml`.

These are snippets to paste into a Home Assistant configuration, so nothing in
this repo ever loads them — Home Assistant does, at reload time, and a mistake
there means an automation that quietly never fires.

The interesting test is the last one. `input_select.active_scene` is the seam
between the scene tracker and BOTH Stream Deck configs: the decks highlight a
scene key by comparing that helper's state against a hard-coded string. Add a
scene to a deck and forget the tracker, and the key simply never lights up —
nothing errors, on either side. So the two are checked against each other.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import DECKS, ROOT, config_path, config_text

AUTOMATION_DIR = ROOT / "automations"
SCENE_TRACKER = ROOT / "ha-scene-tracker.yaml"
AUTOMATION_FILES = sorted(AUTOMATION_DIR.glob("*.yaml"))

# Home Assistant accepts both the modern plural keys and the older singular
# ones. Either is fine; having neither is not.
TRIGGER_KEYS = ("triggers", "trigger")
ACTION_KEYS = ("actions", "action")


class _Loader(yaml.SafeLoader):
    """SafeLoader tolerant of Home Assistant's `!secret` / `!include` tags."""


_Loader.add_multi_constructor(
    "!", lambda loader, suffix, node: f"!{suffix} {getattr(node, 'value', '')}".strip(),
)


def _chunks(text: str) -> list[str]:
    """Split a paste-snippet file into separately-parseable YAML blocks.

    `ha-scene-tracker.yaml` is not one document: it holds an `input_select:`
    mapping to paste into `configuration.yaml` followed by a LIST of automation
    blocks to paste into `automations.yaml`. A mapping and a sequence at the
    same level is not valid YAML, so the file is split where the top-level
    construct changes and each part parsed on its own.
    """
    blocks: list[list[str]] = []
    kind: str | None = None
    for line in text.splitlines():
        if line.startswith("- "):
            line_kind = "list"
        elif line[:1] not in ("", " ", "#"):
            line_kind = "map"
        else:
            line_kind = kind  # blank, comment or continuation of the current block
        if kind is not None and line_kind is not None and line_kind != kind:
            blocks.append([])
        kind = line_kind or kind
        if not blocks:
            blocks.append([])
        blocks[-1].append(line)
    return ["\n".join(block) for block in blocks]


def _documents(path: Path) -> list[Any]:
    parsed = [yaml.load(chunk, Loader=_Loader) for chunk in _chunks(path.read_text())]
    return [document for document in parsed if document]


def _load(path: Path) -> Any:
    """The first non-empty document — for single-document files."""
    documents = _documents(path)
    assert documents, f"{path.name} parsed to nothing"
    return documents[0]


def _automations(path: Path) -> list[dict]:
    """Every automation block in a file, across all of its chunks."""
    found: list[dict] = []
    for document in _documents(path):
        items = document if isinstance(document, list) else [document]
        found += [
            item for item in items if isinstance(item, dict) and "alias" in item
        ]
    return found


def _input_select(path: Path) -> dict:
    for document in _documents(path):
        if isinstance(document, dict) and "input_select" in document:
            return document["input_select"]["active_scene"]
    raise AssertionError(f"{path.name} declares no input_select.active_scene")


def _selected_options(path: Path) -> set[str]:
    """Options the tracker's automations actually select."""
    return {
        step["data"]["option"]
        for block in _automations(path)
        for step in block.get("actions", [])
        if isinstance(step, dict) and step.get("action") == "input_select.select_option"
    }


def _scenes_activated_by(deck: str) -> set[str]:
    """Scenes a deck config activates.

    Read from the parsed config rather than by pattern-matching the text: the
    scene is passed in `service_data` (`scene: scene.work_s`), and a text scan
    also picks up the SERVICE name `scene.turn_on`, which is not a scene.
    """
    import yaml as _yaml

    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("scene", "entity_id", "linked_entity"):
                    for item in [value] if isinstance(value, str) else value or []:
                        if isinstance(item, str) and item.startswith("scene."):
                            found.add(item.split(".", 1)[1])
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(_yaml.safe_load(config_path(deck).read_text()))
    return found


def test_there_is_yaml_to_check() -> None:
    assert AUTOMATION_FILES, f"no automations found in {AUTOMATION_DIR}"
    assert SCENE_TRACKER.exists()


@pytest.mark.parametrize("path", AUTOMATION_FILES, ids=lambda p: p.name)
def test_automation_parses_and_is_complete(path: Path) -> None:
    """An automation with no trigger is accepted by Home Assistant and never
    runs — the quietest possible failure.
    """
    blocks = _automations(path)
    assert blocks, f"{path.name} contains no automation block (needs an `alias`)"
    for block in blocks:
        name = block.get("alias")
        assert any(key in block for key in TRIGGER_KEYS), f"{name}: no trigger"
        assert any(key in block for key in ACTION_KEYS), f"{name}: no action"
        assert block.get("mode", "single") in (
            "single", "restart", "queued", "parallel",
        ), f"{name}: unknown mode {block.get('mode')!r}"


def test_scene_tracker_declares_the_helper() -> None:
    """`none` must be first: the file documents it as the reset value, and the
    decks treat "no scene active" as this exact option.
    """
    helper = _input_select(SCENE_TRACKER)
    options = helper["options"]
    assert options[0] == "none", f"first option is {options[0]!r}, not 'none'"
    assert len(set(options)) == len(options), "duplicate scene options"
    assert helper.get("initial") == "none"


def test_every_scene_automation_sets_a_declared_option() -> None:
    """One automation per scene keeps the helper updated. Selecting an option
    outside the list makes Home Assistant log an error and the deck key never
    highlights.
    """
    options = set(_input_select(SCENE_TRACKER)["options"])
    selected = _selected_options(SCENE_TRACKER)
    assert selected, "no scene automations found"
    assert sorted(selected - options) == [], "automations select undeclared options"


def test_every_scene_has_an_automation_to_track_it() -> None:
    """The reverse: an option nothing ever sets is a scene the decks can render
    a highlight for but which never becomes active.
    """
    options = set(_input_select(SCENE_TRACKER)["options"]) - {"none"}
    tracked = _selected_options(SCENE_TRACKER)
    assert sorted(options - tracked) == [], "scene options with no tracking automation"


def test_automation_ids_are_unique() -> None:
    """Home Assistant keys automations by `id`; a collision means the UI edits
    one and runs the other.
    """
    ids = [
        block["id"]
        for path in [SCENE_TRACKER, *AUTOMATION_FILES]
        for block in _automations(path)
        if "id" in block
    ]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert duplicates == [], f"duplicate automation ids: {duplicates}"


@pytest.mark.parametrize("deck", DECKS)
def test_scene_states_the_decks_render_are_real_options(deck: str) -> None:
    """The cross-file seam.

    Each deck highlights a scene key with
    `is_state("input_select.active_scene", "<scene>")`. That string has to be an
    option the helper can actually hold, or the key is permanently unlit — with
    no error anywhere, because both halves are individually valid.
    """
    import re

    options = set(_input_select(SCENE_TRACKER)["options"])
    compared = set(re.findall(
        r"is_state\(\s*[\"']input_select\.active_scene[\"']\s*,\s*[\"'](\w+)[\"']",
        config_text(deck),
    ))
    assert compared, f"{deck} renders no scene highlight — has the pattern changed?"
    assert sorted(compared - options) == [], (
        f"decks/{deck}/configuration.yaml highlights scenes that "
        f"input_select.active_scene can never hold; options are {sorted(options)}"
    )


@pytest.mark.parametrize("deck", DECKS)
def test_scenes_the_decks_activate_are_tracked(deck: str) -> None:
    """A deck key that activates `scene.x` should also cause the helper to
    become `x`, otherwise pressing it leaves the key unlit and the previous
    scene still showing as active.
    """
    options = set(_input_select(SCENE_TRACKER)["options"])
    activated = _scenes_activated_by(deck)
    assert activated, f"{deck} activates no scenes — has the pattern changed?"
    assert sorted(activated - options) == [], (
        f"decks/{deck} activates scenes the tracker does not know about"
    )

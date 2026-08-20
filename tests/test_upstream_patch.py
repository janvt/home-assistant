"""`decks/plus-xl/patch_touchscreen_rotation.py` — the one place this repo edits
installed upstream source.

It rewrites a specific block inside `home_assistant_streamdeck_yaml.py` because
the Plus XL's touch strip is blank without it. That makes it the most fragile
thing here: it matches upstream text verbatim, and it is re-applied after every
`task xl:install` (which recreates the venv). Two failure modes matter —

  * upstream edits that block, the match fails, and the strip stays blank;
  * the patch half-applies and leaves the installed module syntactically
    broken, which takes the whole app down rather than just the strip.

The patcher is careful about both (it refuses to write unless it finds exactly
one occurrence). These tests hold it to that, end to end, against a COPY of the
installed module — nothing here modifies the real venv.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from conftest import DECKS_DIR

PATCHER = DECKS_DIR / "plus-xl" / "patch_touchscreen_rotation.py"


@pytest.fixture(scope="session")
def patcher() -> ModuleType:
    spec = importlib.util.spec_from_file_location("patch_ts", PATCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def upstream_copy(app: Any, patcher: ModuleType, tmp_path: Path) -> Path:
    """A writable copy of the installed app module, pristine.

    Skips when the installed copy is already patched — that's the normal state
    of a working Mac deck (`task xl:patch` runs as a dependency of `xl:run`),
    and there is no way to recover the original text from it. CI installs a
    fresh app, so these tests do run there.
    """
    source = Path(app.__file__).read_text()
    if patcher.MARKER in source:
        pytest.skip(
            "the installed app is already patched — run these against a fresh "
            "install (CI does) to exercise the patcher end to end",
        )
    target = tmp_path / "home_assistant_streamdeck_yaml.py"
    target.write_text(source)
    return target


def _run(patcher: ModuleType, target: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the patcher against `target` by standing in for the real module."""
    monkeypatch.setitem(
        sys.modules, "home_assistant_streamdeck_yaml", SimpleNamespace(__file__=str(target)),
    )
    patcher.main()


def test_the_block_it_matches_still_exists_upstream(
    app: Any, patcher: ModuleType,
) -> None:
    """The seam guard: this is what breaks on an upstream bump.

    Either the installed module is already patched, or the exact pristine block
    is there exactly once. Anything else means the patch no longer applies and
    the Plus XL's strip will be blank until `update_dial()` is re-read.
    """
    source = Path(app.__file__).read_text()
    if patcher.MARKER in source:
        assert patcher.CACHE_DECL in source, "patched, but the tile cache is missing"
        return
    assert source.count(patcher.PRISTINE) == 1, (
        f"expected exactly one pristine touchscreen-write block in "
        f"{app.__file__}, found {source.count(patcher.PRISTINE)} — upstream "
        f"changed update_dial(); review the patcher"
    )


def test_patching_rewrites_the_write_path_and_adds_the_cache(
    patcher: ModuleType, upstream_copy: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(patcher, upstream_copy, monkeypatch)
    patched = upstream_copy.read_text()
    assert patcher.MARKER in patched
    assert patcher.CACHE_DECL in patched, "no module-level tile cache"
    assert patcher.PRISTINE not in patched, "the unrotated write path is still there"
    assert patched.index(patcher.CACHE_DECL) < patched.index("def update_dial("), (
        "the cache must be declared above the function that uses it"
    )


def test_the_patched_module_still_compiles(
    patcher: ModuleType, upstream_copy: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A syntax error here breaks the whole app, not just the touch strip —
    and it would only surface at the next launch.
    """
    _run(patcher, upstream_copy, monkeypatch)
    compile(upstream_copy.read_text(), str(upstream_copy), "exec")


def test_patching_is_idempotent(
    patcher: ModuleType, upstream_copy: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`task xl:patch` runs as a dependency of `xl:run` and `xl:service`, so it
    is applied over and over. Nesting the patch would repaint the strip twice
    per dial update.
    """
    _run(patcher, upstream_copy, monkeypatch)
    once = upstream_copy.read_text()
    _run(patcher, upstream_copy, monkeypatch)
    assert upstream_copy.read_text() == once
    assert once.count(patcher.MARKER) == 1
    assert once.count(patcher.CACHE_DECL) == 1


def test_an_older_patch_is_upgraded_in_place(
    patcher: ModuleType, upstream_copy: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v1 rotated the per-region image; v2 repaints the whole strip. A machine
    still carrying v1 must end up on v2, not with both.
    """
    v1 = (
        '    # PATCHED(streamdeck-xl): honour TOUCHSCREEN_ROTATION\n'
        '    _ts_rotation = deck.touchscreen_image_format().get("rotation", 0)\n'
        '    if _ts_rotation:\n'
        '        image = image.rotate(_ts_rotation, expand=True)\n'
    )
    upstream_copy.write_text(
        upstream_copy.read_text().replace(patcher.PRISTINE, v1 + patcher.PRISTINE),
    )
    _run(patcher, upstream_copy, monkeypatch)
    patched = upstream_copy.read_text()
    assert "PATCHED(streamdeck-xl): honour TOUCHSCREEN_ROTATION" not in patched
    assert patched.count(patcher.MARKER) == 1
    compile(patched, str(upstream_copy), "exec")


def test_it_refuses_to_patch_unrecognised_source(
    patcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When upstream moves the block, the patcher must exit loudly and leave the
    file untouched — a partial write is far worse than an unpatched deck.
    """
    target = tmp_path / "home_assistant_streamdeck_yaml.py"
    original = "def update_dial(\n    a, b\n):\n    pass\n"  # no pristine block
    target.write_text(original)
    with pytest.raises(SystemExit):
        _run(patcher, target, monkeypatch)
    assert target.read_text() == original, "the module was modified before bailing out"


def test_the_rotated_path_repaints_the_whole_strip(patcher: ModuleType) -> None:
    """Both halves of the fix have to be in the replacement text: rotate the
    bytes, and write the full strip from x=0 (partial writes at a non-zero x
    silently don't land on this hardware).
    """
    assert ".rotate(_ts_rot, expand=True)" in patcher.NEW
    assert "set_touchscreen_image(img_bytes.getvalue(), 0, 0" in patcher.NEW
    # ... and rotation-0 decks (the Pi's Plus) must keep the original path, in
    # the `else` arm. Compared with whitespace collapsed, since the replacement
    # re-indents the original statements one level deeper.
    def squashed(text: str) -> str:
        return " ".join(text.split())

    assert "else:" in patcher.NEW
    assert squashed(patcher.PRISTINE) in squashed(patcher.NEW), (
        "the unrotated fast path was not preserved for rotation-0 decks"
    )

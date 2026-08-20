"""`streamdeck/generate_icons.py` — the shared image renderer.

Every key and dial frame on both decks comes out of this file, and a wrong
image is invisible until you look at the hardware: a missing icon file makes
the app raise on that key (so the key silently does nothing), and a badly
placed one just looks wrong forever. So these tests check the geometry and the
actual pixels, not just that the code runs.

Rendering here uses a system font with a synthetic codepoint map, so it needs
no network. The tests that need the real Material Design Icons webfont — the
ones proving each deck's icon NAMES exist, and the one pinning the renderer's
output list — use the build cache and skip when it's cold (see conftest).
"""
from __future__ import annotations

import shutil
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

from conftest import DECKS, DEVICE, expected_icon_names, spec

# 0x41 is "A" — present in any real font, so a synthetic map renders visible
# ink without needing the MDI webfont.
FAKE_CP = "41"


@pytest.fixture()
def fonts(gen: ModuleType) -> tuple:
    """(icon_font, label_font, ttf_path) from a real system TrueType font."""
    label = gen._label_font(17)
    return gen._label_font(54), label, label.path


def _cps(*names: str) -> dict[str, str]:
    return {name: FAKE_CP for name in names}


def _ink_rows(img: Image.Image, background: tuple[int, int, int]) -> set[int]:
    """Rows containing drawn ink — glyph or label pixels.

    Black is treated as background too: the chip is a rounded rectangle painted
    onto a black tile, so the four corners are legitimately black and would
    otherwise register as ink on every row.
    """
    px = img.convert("RGB").load()
    w, h = img.size
    return {
        y for y in range(h) for x in range(w)
        if px[x, y] != background and px[x, y] != (0, 0, 0)
    }


# ── geometry ────────────────────────────────────────────────────────────────
def test_geometry_at_the_reference_size_is_an_identity(gen: ModuleType) -> None:
    """The look was tuned at 120px; scaling must not perturb it there."""
    geo = gen.geometry(gen.REF_KEY)
    assert (geo.key, geo.icon_px, geo.icon_cy, geo.label_px, geo.label_cy, geo.radius) == (
        gen.REF_KEY, gen.REF_ICON_PX, gen.REF_ICON_CY,
        gen.REF_LABEL_PX, gen.REF_LABEL_CY, gen.REF_RADIUS,
    )


@pytest.mark.parametrize("deck", DECKS)
def test_geometry_fits_inside_the_key(gen: ModuleType, deck: str) -> None:
    """Nothing may be scaled off the tile: a clipped glyph or a label past the
    bottom edge is the failure mode when a new deck size is added.
    """
    key_px = spec(gen, deck).KEY_PX
    assert key_px == DEVICE[deck]["key_px"], "spec KEY_PX no longer matches the hardware"
    geo = gen.geometry(key_px)
    assert geo.key == key_px
    assert 0 < geo.icon_px < geo.key
    assert 0 < geo.label_px < geo.icon_px
    assert 0 < geo.icon_cy < geo.label_cy < geo.key, "label must sit below the glyph"
    assert geo.label_cy + geo.label_px / 2 <= geo.key, "label runs off the bottom edge"
    assert 0 < geo.radius < geo.key / 2


def test_geometry_scales_proportionally(gen: ModuleType) -> None:
    ref, small = gen.geometry(120), gen.geometry(112)
    for field in ("icon_px", "icon_cy", "label_px", "label_cy", "radius"):
        assert getattr(small, field) == round(getattr(ref, field) * 112 / 120)


# ── the MDI codepoint map ───────────────────────────────────────────────────
def test_codepoints_parses_the_webfont_css(gen: ModuleType, tmp_path: Path) -> None:
    css = tmp_path / "mdi.css"
    css.write_text(
        '.mdi-coffee::before { content: "\\F0176"; }\n'
        '.mdi-volume-high::before {\n  content: "\\F057E";\n}\n'
        '.mdi-not-an-icon:hover { color: red; }\n',
    )
    assert gen._codepoints(css) == {"coffee": "F0176", "volume-high": "F057E"}


def test_codepoints_reads_the_real_css(mdi_codepoints: dict[str, str]) -> None:
    assert len(mdi_codepoints) > 5000, "MDI css parsed but produced almost nothing"
    assert "coffee" in mdi_codepoints
    assert all(int(cp, 16) for cp in list(mdi_codepoints.values())[:50])


@pytest.mark.parametrize("deck", DECKS)
def test_every_icon_name_in_the_spec_exists_in_the_font(
    gen: ModuleType, deck: str, mdi_codepoints: dict[str, str],
) -> None:
    """A typo'd or renamed MDI name is a hard `sys.exit` mid-render, which on a
    running deck means a half-rendered icons dir.
    """
    module = spec(gen, deck)
    used = {mdi for _n, mdi, _l, _s in getattr(module, "STATEFUL", [])}
    used |= {mdi for _n, mdi, _l, _s in getattr(module, "ACTION", [])}
    used |= {mdi for _n, mdi, _l in getattr(module, "INFO", [])}
    assert sorted(name for name in used if name not in mdi_codepoints) == []


def test_dial_style_icons_exist_in_the_font(
    gen: ModuleType, mdi_codepoints: dict[str, str],
) -> None:
    missing = [icon for _c, icon, _s in gen.DIAL_STYLES.values()
               if icon not in mdi_codepoints]
    assert missing == []
    # render_gauge falls back from volume-off to volume-mute for muted frames.
    assert {"volume-off", "volume-mute"} & set(mdi_codepoints)


@pytest.mark.parametrize("deck", DECKS)
def test_every_style_in_the_spec_is_in_the_palette(gen: ModuleType, deck: str) -> None:
    """An unknown style name is a KeyError inside the render loop."""
    module = spec(gen, deck)
    styles = {s for _n, _m, _l, s in getattr(module, "STATEFUL", [])}
    styles |= {s for _n, _m, _l, s in getattr(module, "ACTION", [])}
    assert sorted(styles - set(gen.STYLES)) == []
    assert sorted({s for _n, s, _l in module.DIALS} - set(gen.DIAL_STYLES)) == []
    assert sorted(set(gen.INFO_THRESHOLD_STYLES) - set(gen.STYLES)) == []


def test_palette_entries_are_complete_colour_triples(gen: ModuleType) -> None:
    for name, colours in gen.STYLES.items():
        assert len(colours) == 3, f"{name} is not (bg, icon, label)"
        assert all(c.startswith("#") and len(c) == 7 for c in colours), name


# ── key rendering ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("deck", DECKS)
def test_render_key_writes_a_square_png_at_the_deck_size(
    gen: ModuleType, deck: str, fonts: tuple, tmp_path: Path,
) -> None:
    icon_font, label_font, _ = fonts
    geo = gen.geometry(DEVICE[deck]["key_px"])
    gen.render_key(
        "probe", "desk", "Label", "blue", geo=geo, out=tmp_path,
        cps=_cps("desk"), icon_font=icon_font, label_font=label_font,
    )
    with Image.open(tmp_path / "probe.png") as img:
        assert img.size == (geo.key, geo.key)
        assert img.mode == "RGB"
        colours = {c for _n, c in img.convert("RGB").getcolors(maxcolors=1 << 16)}
    assert gen.STYLES["blue"][0].lower() in {
        "#%02x%02x%02x" % c for c in colours
    }, "chip background colour missing — style was not applied"


def test_render_key_draws_the_label_low_and_the_glyph_high(
    gen: ModuleType, fonts: tuple, tmp_path: Path,
) -> None:
    icon_font, label_font, _ = fonts
    geo = gen.geometry(120)
    common = {"geo": geo, "out": tmp_path, "cps": _cps("desk"),
              "icon_font": icon_font, "label_font": label_font}
    gen.render_key("labelled", "desk", "Work", "blue", **common)
    gen.render_key("bare", "desk", "", "blue", **common)
    bg = (0x37, 0x8A, 0xDD)  # "blue" chip background

    with Image.open(tmp_path / "labelled.png") as img:
        labelled = _ink_rows(img, bg)
    with Image.open(tmp_path / "bare.png") as img:
        bare = _ink_rows(img, bg)

    assert any(abs(y - geo.label_cy) <= geo.label_px for y in labelled), (
        "no ink near the label's centre line — the label was not drawn"
    )
    assert max(bare) < geo.label_cy - geo.label_px / 2, (
        "an unlabelled key drew ink down in the label zone; the glyph should be "
        "centred in the tile instead (the quiet '...' nav keys rely on this)"
    )
    # ... and being centred means the ink is symmetric about the tile's middle,
    # rather than sitting high where it would leave a hole under it.
    centre = sum(bare) / len(bare)
    assert abs(centre - geo.key / 2) <= geo.key * 0.05, (
        f"unlabelled glyph centred at y={centre:.0f}, expected ~{geo.key / 2:.0f}"
    )
    # The labelled tile puts its glyph higher, leaving room for the text.
    glyph_rows = [y for y in labelled if y < geo.label_cy - geo.label_px]
    assert sum(glyph_rows) / len(glyph_rows) < geo.key / 2


def test_render_info_key_leaves_a_gap_for_the_live_value(
    gen: ModuleType, fonts: tuple, tmp_path: Path,
) -> None:
    """INFO tiles are backgrounds for the app's own `text:` overlay. The whole
    point of the layout (icon at 0.20, unit label at 0.80) is the clear band
    between them — if the two ever meet, the live reading is drawn on top of
    artwork and becomes unreadable.
    """
    icon_font, label_font, _ = fonts
    geo = gen.geometry(112)
    gen.render_info_key(
        "co2", "molecule-co2", "ppm", "green", geo=geo, out=tmp_path,
        cps=_cps("molecule-co2"), icon_font=icon_font, label_font=label_font,
    )
    with Image.open(tmp_path / "co2.png") as img:
        ink = _ink_rows(img, (0x63, 0x99, 0x22))  # "green" chip background

    clear = [y for y in range(geo.key) if y not in ink]
    runs, run = [], []
    for y in clear:
        if run and y == run[-1] + 1:
            run.append(y)
        else:
            runs.append(run := [y])
    middle = [r for r in runs if r[0] < geo.key * 0.75 and r[-1] > geo.key * 0.35]
    assert middle, "no clear band between the icon and the unit label"
    assert max(len(r) for r in middle) >= geo.key * 0.15, (
        f"gap for the live value is only {max(len(r) for r in middle)}px of "
        f"{geo.key} — text_size 26-28 will collide with the artwork"
    )


@pytest.mark.parametrize("render", ["render_key", "render_info_key"])
def test_an_unknown_icon_name_fails_loudly(
    gen: ModuleType, fonts: tuple, tmp_path: Path, render: str,
) -> None:
    icon_font, label_font, _ = fonts
    with pytest.raises(SystemExit):
        getattr(gen, render)(
            "x", "no-such-mdi-icon", "L", "blue", geo=gen.geometry(120),
            out=tmp_path, cps=_cps("desk"),
            icon_font=icon_font, label_font=label_font,
        )


# ── dial frames ─────────────────────────────────────────────────────────────
def test_gauge_frames_are_the_shared_strip_segment_size(
    gen: ModuleType, fonts: tuple, tmp_path: Path,
) -> None:
    """200x100 is what makes one renderer serve both decks: the Plus's 800px
    strip over 4 dials and the XL's 1200px over 6 are the same per-dial size.
    """
    _icon, _label, ttf = fonts
    gen.render_gauge("probe", "volume", "Test", 50, out=tmp_path,
                     cps=_cps("volume-high"), mdi_ttf=ttf, label_ttf=ttf)
    with Image.open(tmp_path / "dials" / "probe_50.png") as img:
        assert img.size == (gen.DIAL_W, gen.DIAL_H) == (200, 100)


def test_gauge_fill_grows_with_the_value(
    gen: ModuleType, fonts: tuple, tmp_path: Path,
) -> None:
    """The bar is the only part a user reads at a glance, so its height must be
    monotonic in the value — and empty at 0, not a stub of rounded corner.
    """
    _icon, _label, ttf = fonts
    accent = tuple(int(gen.DIAL_STYLES["volume"][0][i:i + 2], 16) for i in (1, 3, 5))

    def filled(pct: int) -> int:
        gen.render_gauge("bar", "volume", "Test", pct, out=tmp_path,
                         cps=_cps("volume-high"), mdi_ttf=ttf, label_ttf=ttf)
        with Image.open(tmp_path / "dials" / f"bar_{pct}.png") as img:
            px = img.convert("RGB").load()
            # Count only inside the bar's own column band, so the accent
            # coloured icon and text don't pollute the measurement.
            return sum(
                1 for y in range(gen.DIAL_H) for x in range(138, 165)
                if sum(abs(a - b) for a, b in zip(px[x, y], accent)) < 40
            )

    counts = [filled(p) for p in (0, 25, 50, 75, 100)]
    assert counts[0] == 0, "0% still drew fill"
    assert counts == sorted(counts) and len(set(counts)) == 5, f"not monotonic: {counts}"


def test_muted_gauge_frame_is_grey_and_empty(
    gen: ModuleType, fonts: tuple, tmp_path: Path,
) -> None:
    _icon, _label, ttf = fonts
    cps = _cps("volume-high", "volume-off")
    gen.render_gauge("m", "volume", "Test", 90, out=tmp_path, cps=cps,
                     mdi_ttf=ttf, label_ttf=ttf, muted=True)
    accent = tuple(int(gen.DIAL_STYLES["volume"][0][i:i + 2], 16) for i in (1, 3, 5))
    with Image.open(tmp_path / "dials" / "m_muted.png") as img:
        px = img.convert("RGB").load()
        assert not any(
            sum(abs(a - b) for a, b in zip(px[x, y], accent)) < 40
            for y in range(gen.DIAL_H) for x in range(138, 165)
        ), "muted frame still shows a filled bar (pct 90 leaked through)"
    assert (tmp_path / "dials" / "m_muted.png").exists()
    assert not (tmp_path / "dials" / "m_90.png").exists(), "muted frame used the pct name"


# ── build(): the whole-deck run ─────────────────────────────────────────────
@pytest.fixture()
def sandbox_build(gen: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run the real `build()` against a copy of a deck spec in a temp dir.

    The font cache stays pointed at the real `.iconbuild/`, so this reuses the
    downloaded webfont instead of fetching it again.
    """
    decks = tmp_path / "decks"
    real_decks = gen.DECKS  # captured before the patch, so a second call still finds it

    def run(deck: str) -> Path:
        target = decks / deck
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy(real_decks / deck / "spec.py", target / "spec.py")
        monkeypatch.setattr(gen, "DECKS", decks)
        gen.build(deck)
        return target / "icons"

    return run


@pytest.mark.parametrize("deck", DECKS)
def test_build_produces_exactly_the_expected_image_set(
    gen: ModuleType, deck: str, sandbox_build, mdi_font: str, mdi_codepoints: dict,
) -> None:
    """Pins the cheap mirror in conftest to the real renderer.

    Every other icon-contract test compares config references against
    `expected_icon_names()`, which reimplements `build()`'s naming. This is the
    one test that runs the actual renderer, so if build() ever changes shape
    the mirror is caught here rather than silently going stale.
    """
    out = sandbox_build(deck)
    keys, dials = expected_icon_names(gen, deck)
    assert {p.name for p in out.glob("*.png")} == keys
    assert {p.name for p in (out / "dials").glob("*.png")} == dials


def test_build_prunes_images_the_spec_no_longer_asks_for(
    gen: ModuleType, sandbox_build, mdi_font: str, mdi_codepoints: dict,
) -> None:
    """A key removed from a layout must not leave its image behind, or the next
    reader can't tell which files are live.
    """
    out = sandbox_build("plus")
    stale_key = out / "removed_key.png"
    stale_dial = out / "dials" / "removed_dial_50.png"
    stale_key.write_bytes(b"")
    stale_dial.write_bytes(b"")
    live = sorted(p.name for p in out.glob("*.png") if p != stale_key)

    sandbox_build("plus")  # second run, same spec
    assert not stale_key.exists() and not stale_dial.exists()
    assert sorted(p.name for p in out.glob("*.png")) == live, "pruned a live image"

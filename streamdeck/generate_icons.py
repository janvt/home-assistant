#!/usr/bin/env python3
"""Shared Stream Deck image renderer for every deck in decks/.

Renders two kinds of image, both referenced from a deck's `configuration.yaml`
via its templated `icon:` field:

  * keys        — a coloured chip with a smaller icon and a label below it,
                  at the deck's native key size (Plus 120px, Plus XL 112px).
  * dial frames — a vertical fill bar + icon/value/label, one PNG per step.
                  Always 200x100: the Plus strip is 800x100 over 4 dials and
                  the Plus XL's is 1200x100 over 6, so a segment is 200x100 on
                  both and these frames are shared verbatim.

Usage:  python generate_icons.py --deck plus
Output: decks/<deck>/icons/{*.png,dials/*.png}

WHAT LIVES WHERE: this file owns the drawing code and the palette (shared by
all decks). Each deck's decks/<deck>/spec.py owns its content — key size, which
tiles, which dials. Add a deck by creating a new decks/<name>/spec.py.

Key geometry is expressed relative to REF_KEY (the 120px size the look was
tuned at) and scaled to the deck's key size, so one renderer serves all decks.

Build deps (not committed): the Material Design Icons webfont + css are cached
in .iconbuild/ on first run; labels use a system sans font. Needs Pillow.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import urllib.request
from pathlib import Path
from types import ModuleType, SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
BUILD = HERE / ".iconbuild"
DECKS = HERE / "decks"
MDI_VERSION = "7.4.47"

# ── palette (shared by all decks) ───────────────────────────────────────────
# name -> (background, icon colour, label colour)
STYLES = {
    "off":   ("#C9C9CE", "#6E6E73", "#3A3A3C"),
    "amber": ("#EF9F27", "#412402", "#412402"),
    "blue":  ("#378ADD", "#FFFFFF", "#FFFFFF"),
    "red":   ("#E24B4A", "#FFFFFF", "#FFFFFF"),
    "green": ("#639922", "#FFFFFF", "#FFFFFF"),
}

# ── key geometry, tuned at REF_KEY px and scaled per deck ───────────────────
REF_KEY = 120
REF_ICON_PX = 54   # glyph size (smaller than the key -> leaves room for a label)
REF_ICON_CY = 44   # glyph vertical centre
REF_LABEL_PX = 17
REF_LABEL_CY = 95  # label vertical centre
REF_RADIUS = 18    # chip corner radius

# ── dial gauges (touchscreen strip) — identical on every deck ───────────────
DIAL_W, DIAL_H = 200, 100
SS = 4  # supersample factor for crisp edges

# style -> (accent colour, mdi icon, frame step %). The step is the display
# granularity; set the matching turn increment via each dial's `attributes.step`
# in that deck's configuration.yaml.
DIAL_STYLES = {
    "volume": ("#38D6F2", "volume-high",   2),
    "bright": ("#F7A828", "brightness-7",  5),
    "shade":  ("#63C63B", "window-shutter", 5),
}


def _fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, dest)


def _codepoints(css: Path) -> dict[str, str]:
    text = css.read_text()
    return dict(
        re.findall(r'\.mdi-([a-z0-9-]+)::before\s*\{\s*content:\s*"\\([0-9A-Fa-f]+)"', text)
    )


def _label_font(size: int) -> ImageFont.FreeTypeFont:
    # A real TTF is required for legible labels. Covers macOS and common Linux
    # (Raspberry Pi OS) locations. If none are found, install one, e.g.
    #   sudo apt-get install -y fonts-dejavu-core
    candidates = (
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        # Linux / Raspberry Pi OS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    sys.exit(
        "No TrueType label font found. Install one, e.g.:\n"
        "  sudo apt-get install -y fonts-dejavu-core"
    )


def load_spec(deck: str) -> ModuleType:
    """Import decks/<deck>/spec.py as a module."""
    path = DECKS / deck / "spec.py"
    if not path.exists():
        sys.exit(f"no spec for deck {deck!r} (expected {path})")
    spec = importlib.util.spec_from_file_location(f"{deck}_spec", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def geometry(key_px: int) -> SimpleNamespace:
    """Scale the reference key geometry to this deck's key size."""
    def s(v: int) -> int:
        return round(v * key_px / REF_KEY)
    return SimpleNamespace(
        key=key_px, icon_px=s(REF_ICON_PX), icon_cy=s(REF_ICON_CY),
        label_px=s(REF_LABEL_PX), label_cy=s(REF_LABEL_CY), radius=s(REF_RADIUS),
    )


def render_key(name: str, mdi: str, label: str, style: str, *,
               geo: SimpleNamespace, out: Path, cps: dict[str, str],
               icon_font: ImageFont.FreeTypeFont,
               label_font: ImageFont.FreeTypeFont) -> None:
    if mdi not in cps:
        sys.exit(f"unknown MDI icon: {mdi}")
    bg, icon_c, label_c = STYLES[style]
    img = Image.new("RGB", (geo.key, geo.key), "#000000")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, geo.key - 1, geo.key - 1), radius=geo.radius, fill=bg)
    glyph = chr(int(cps[mdi], 16))
    draw.text((geo.key / 2, geo.icon_cy), glyph, font=icon_font, fill=icon_c, anchor="mm")
    draw.text((geo.key / 2, geo.label_cy), label, font=label_font, fill=label_c, anchor="mm")
    out.mkdir(parents=True, exist_ok=True)
    img.save(out / f"{name}.png")


def render_gauge(slug: str, style: str, label: str, pct: int, *,
                 out: Path, cps: dict[str, str], mdi_ttf: str, label_ttf: str,
                 muted: bool = False) -> None:
    """Render one 200x100 dial frame: a vertical fill bar + icon, value, label.
    With muted=True, render a single greyed 'muted' frame (mute icon, empty bar)."""
    color, icon, _ = DIAL_STYLES[style]
    if muted:
        color = "#6E6E73"
        icon = "volume-off" if "volume-off" in cps else "volume-mute"
    if icon not in cps:
        sys.exit(f"unknown MDI icon: {icon}")
    w, h = DIAL_W * SS, DIAL_H * SS
    im = Image.new("RGB", (w, h), "#000000")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=16 * SS, fill="#191A1D")

    # icon (top), value (centre), label (bottom) — grouped on the left
    rcx = 78 * SS
    d.text((rcx, 27 * SS), chr(int(cps[icon], 16)),
           font=ImageFont.truetype(mdi_ttf, 26 * SS), fill=color, anchor="mm")
    if muted:
        d.text((rcx, 57 * SS), "MUTE", font=ImageFont.truetype(label_ttf, 22 * SS),
               fill=color, anchor="mm")
    else:
        d.text((rcx, 57 * SS), str(pct), font=ImageFont.truetype(label_ttf, 38 * SS),
               fill="#FFFFFF", anchor="mm")
    d.text((rcx, 84 * SS), label, font=ImageFont.truetype(label_ttf, 13 * SS),
           fill="#B8B8BE", anchor="mm")

    # vertical fill bar on the right, tight to the text (fills bottom -> top)
    bx0, bx1, by0, by1 = 138 * SS, 164 * SS, 14 * SS, 86 * SS
    br = 8 * SS
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=br, fill="#2E3036")  # track
    bar_pct = 0 if muted else pct
    if bar_pct > 0:
        fy0 = by1 - (by1 - by0) * bar_pct / 100.0
        rr = int(min(br, (by1 - fy0) / 2))
        d.rounded_rectangle((bx0, fy0, bx1, by1), radius=rr, fill=color)

    (out / "dials").mkdir(parents=True, exist_ok=True)
    name = f"{slug}_muted.png" if muted else f"{slug}_{pct}.png"
    im.resize((DIAL_W, DIAL_H), Image.LANCZOS).save(out / "dials" / name)


def build(deck: str) -> None:
    spec = load_spec(deck)
    geo = geometry(spec.KEY_PX)
    out = DECKS / deck / "icons"

    _fetch(f"https://cdn.jsdelivr.net/npm/@mdi/font@{MDI_VERSION}/fonts/materialdesignicons-webfont.ttf",
           BUILD / "mdi.ttf")
    _fetch(f"https://cdn.jsdelivr.net/npm/@mdi/font@{MDI_VERSION}/css/materialdesignicons.css",
           BUILD / "mdi.css")
    cps = _codepoints(BUILD / "mdi.css")
    mdi_ttf = str(BUILD / "mdi.ttf")
    icon_font = ImageFont.truetype(mdi_ttf, geo.icon_px)
    label_font = _label_font(geo.label_px)

    common = {"geo": geo, "out": out, "cps": cps,
              "icon_font": icon_font, "label_font": label_font}
    for name, mdi, label, style in getattr(spec, "STATEFUL", []):
        render_key(f"{name}_on", mdi, label, style, **common)
        render_key(f"{name}_off", mdi, label, "off", **common)
    for name, mdi, label, style in getattr(spec, "ACTION", []):
        render_key(name, mdi, label, style, **common)

    label_ttf = label_font.path
    for slug, style, label in getattr(spec, "DIALS", []):
        step = DIAL_STYLES[style][2]
        for pct in range(0, 101, step):
            render_gauge(slug, style, label, pct, out=out, cps=cps,
                         mdi_ttf=mdi_ttf, label_ttf=label_ttf)
        if style == "volume":  # extra "muted" frame for media dials
            render_gauge(slug, style, label, 0, out=out, cps=cps,
                         mdi_ttf=mdi_ttf, label_ttf=label_ttf, muted=True)

    n_keys = len(list(out.glob("*.png")))
    n_dials = len(list((out / "dials").glob("*.png")))
    print(f"[{deck}] wrote {n_keys} key images ({geo.key}px) "
          f"and {n_dials} dial frames to {out}")


def main() -> None:
    available = sorted(p.parent.name for p in DECKS.glob("*/spec.py"))
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--deck", required=True, choices=[*available, "all"],
                        help="which deck to render for (or 'all')")
    args = parser.parse_args()
    for deck in (available if args.deck == "all" else [args.deck]):
        build(deck)


if __name__ == "__main__":
    main()

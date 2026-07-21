#!/usr/bin/env python3
"""Generate Stream Deck key images: a coloured chip with a smaller icon and a
label below it, one PNG per button state.

Run:  python generate_icons.py
Output: icons/*.png (120x120, the Stream Deck Plus native key size)

The button config references these via a templated `icon:` field. Re-run this
whenever the spec or palette below changes, then redeploy.

Build deps (isolated, not committed): the Material Design Icons webfont + css
are downloaded into .iconbuild/ on first run; labels use a system sans font.
Requires Pillow (`pip install pillow`).
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
BUILD = HERE / ".iconbuild"
OUT = HERE / "icons"
KEY = 120  # Stream Deck Plus key size in px
MDI_VERSION = "7.4.47"

# ── palette (matches the button colour scheme) ──────────────────────────────
# name -> (background, icon colour, label colour)
STYLES = {
    "off":   ("#C9C9CE", "#6E6E73", "#3A3A3C"),
    "amber": ("#EF9F27", "#412402", "#412402"),
    "blue":  ("#378ADD", "#FFFFFF", "#FFFFFF"),
    "red":   ("#E24B4A", "#FFFFFF", "#FFFFFF"),
    "green": ("#639922", "#FFFFFF", "#FFFFFF"),
}

# ── button spec: (output name, mdi icon, label, active style) ───────────────
# Stateful buttons render <name>_on (active style) and <name>_off (grey).
# Action buttons render <name> in their domain style.
STATEFUL = [
    ("chill",     "sofa",         "Chill",     "amber"),
    ("vinyl",     "album",        "Vinyl",     "amber"),
    ("pain_cave", "bike-fast",    "Pain Cave", "amber"),
    ("work_s",    "desk",         "Work S",    "amber"),
    ("hallway",   "wall-sconce",  "Hallway",   "amber"),
    ("outside",   "outdoor-lamp", "Outside",   "amber"),
    ("fan",       "emoticon-poop","Fan",       "blue"),
    ("guest",     "account-group","Guest",     "blue"),
    ("cleaning",  "broom",        "Cleaning",  "blue"),
]
ACTION = [
    ("lights_off", "lightbulb-off",       "Lights Off", "amber"),
    ("open_all",   "window-shutter-open", "Open All",   "green"),
    ("close_all",  "window-shutter",      "Close All",  "green"),
    ("apartment",  "door-open",           "Apartment",  "red"),
    ("house",      "gate-open",           "House",      "red"),
    ("menu",       "dots-horizontal",     "Menu",       "blue"),
]

ICON_PX = 54      # glyph size (smaller than the key -> leaves room for a label)
ICON_CY = 44      # glyph vertical centre
LABEL_PX = 17
LABEL_CY = 95     # label vertical centre
RADIUS = 18       # chip corner radius

# ── dial gauges (touchscreen strip) ─────────────────────────────────────────
# The Stream Deck Plus touch strip is 800x100, split into four 200x100 dial
# segments. Dials move in fixed 5% steps, so we pre-render a frame per 5% and
# the dial's `icon:` field templates to the current value.
DIAL_W, DIAL_H = 200, 100
SS = 4            # supersample factor for crisp edges

# style -> (accent colour, mdi icon, frame step %). The step is the display
# granularity; set the matching turn increment via each dial's `attributes.step`
# in configuration.yaml.
DIAL_STYLES = {
    "volume": ("#38D6F2", "volume-high",   2),
    "bright": ("#F7A828", "brightness-7",  5),
    "shade":  ("#63C63B", "window-shutter", 10),
}
# (slug, style, label) — one dial each; frames are <slug>_<pct>.png
DIALS = [
    ("lr_volume",         "volume", "Living Room"),
    ("madagascar_volume", "volume", "Madagascar"),
    ("lr_bright",         "bright", "LR Ceiling"),
    ("kitchen_bright",    "bright", "Kitchen"),
    ("lr_shade",          "shade",  "Living Room"),
    ("kitchen_shade",     "shade",  "Kitchen"),
    ("bedroom_shade",     "shade",  "Bedroom"),
    ("guest_shade",       "shade",  "Guest"),
]


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


def render(name: str, mdi: str, label: str, style: str,
           cps: dict[str, str], icon_font: ImageFont.FreeTypeFont,
           label_font: ImageFont.FreeTypeFont) -> None:
    if mdi not in cps:
        sys.exit(f"unknown MDI icon: {mdi}")
    bg, icon_c, label_c = STYLES[style]
    img = Image.new("RGB", (KEY, KEY), "#000000")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, KEY - 1, KEY - 1), radius=RADIUS, fill=bg)
    glyph = chr(int(cps[mdi], 16))
    draw.text((KEY / 2, ICON_CY), glyph, font=icon_font, fill=icon_c, anchor="mm")
    draw.text((KEY / 2, LABEL_CY), label, font=label_font, fill=label_c, anchor="mm")
    OUT.mkdir(exist_ok=True)
    img.save(OUT / f"{name}.png")


def render_gauge(slug: str, style: str, label: str, pct: int,
                 cps: dict[str, str], mdi_ttf: str, label_ttf: str) -> None:
    """Render one 200x100 dial frame: a vertical fill bar + icon, value, label."""
    color, icon, _ = DIAL_STYLES[style]
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
    d.text((rcx, 54 * SS), str(pct), font=ImageFont.truetype(label_ttf, 38 * SS),
           fill="#FFFFFF", anchor="mm")
    d.text((rcx, 84 * SS), label, font=ImageFont.truetype(label_ttf, 13 * SS),
           fill="#B8B8BE", anchor="mm")

    # vertical fill bar on the right, tight to the text (fills bottom -> top)
    bx0, bx1, by0, by1 = 138 * SS, 164 * SS, 14 * SS, 86 * SS
    br = 8 * SS
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=br, fill="#2E3036")  # track
    if pct > 0:
        fy0 = by1 - (by1 - by0) * pct / 100.0
        rr = int(min(br, (by1 - fy0) / 2))
        d.rounded_rectangle((bx0, fy0, bx1, by1), radius=rr, fill=color)

    (OUT / "dials").mkdir(parents=True, exist_ok=True)
    im.resize((DIAL_W, DIAL_H), Image.LANCZOS).save(OUT / "dials" / f"{slug}_{pct}.png")


def main() -> None:
    _fetch(f"https://cdn.jsdelivr.net/npm/@mdi/font@{MDI_VERSION}/fonts/materialdesignicons-webfont.ttf",
           BUILD / "mdi.ttf")
    _fetch(f"https://cdn.jsdelivr.net/npm/@mdi/font@{MDI_VERSION}/css/materialdesignicons.css",
           BUILD / "mdi.css")
    cps = _codepoints(BUILD / "mdi.css")
    icon_font = ImageFont.truetype(str(BUILD / "mdi.ttf"), ICON_PX)
    label_font = _label_font(LABEL_PX)

    for name, mdi, label, style in STATEFUL:
        render(f"{name}_on", mdi, label, style, cps, icon_font, label_font)
        render(f"{name}_off", mdi, label, "off", cps, icon_font, label_font)
    for name, mdi, label, style in ACTION:
        render(name, mdi, label, style, cps, icon_font, label_font)

    mdi_ttf, label_ttf = str(BUILD / "mdi.ttf"), _label_font(LABEL_PX).path
    for slug, style, label in DIALS:
        step = DIAL_STYLES[style][2]
        for pct in range(0, 101, step):
            render_gauge(slug, style, label, pct, cps, mdi_ttf, label_ttf)

    n_keys = len(list(OUT.glob("*.png")))
    n_dials = len(list((OUT / "dials").glob("*.png")))
    print(f"wrote {n_keys} key images and {n_dials} dial frames to {OUT}")


if __name__ == "__main__":
    main()

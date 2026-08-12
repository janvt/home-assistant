#!/usr/bin/env python3
"""Patch the installed home_assistant_streamdeck_yaml for Plus XL touchscreens.

TWO upstream problems, both only affecting decks whose TOUCHSCREEN_ROTATION != 0
(the Plus XL reports 90; the Plus reports 0 and is untouched by this patch):

1. ROTATION IGNORED. `StreamDeckPlusXL.set_touchscreen_image()` swaps the region
   geometry for the device (`int_x = y_pos; int_y = x_pos; int_w = height;
   int_h = width`), so the device works in a rotated frame and the JPEG bytes
   must be rotated to match — that's what `PILHelper.to_native_touchscreen_format()`
   is for. The app instead encodes with a bare `image.save(..., "JPEG")`, i.e.
   unrotated, which is only correct on a rotation-0 deck. Result: blank strip.

2. PARTIAL-REGION WRITES DON'T LAND. Verified on real hardware: writing each
   dial's 200x100 region at x=200*k only takes effect for k=0 — every dial past
   the first stays blank. A single full-strip write (x=0, y=0, 1200x100, rotated)
   renders all six correctly.

So for rotated decks we cache each dial's tile and repaint the ENTIRE strip on
every dial update. Rotation-0 decks keep the original per-region fast path.

Idempotent, and upgrades an earlier version of this patch in place. Applied by
`task xl:patch` (and via the deps of `xl:run` / `xl:service`); re-applied after
any `task xl:install`, which recreates the venv.

Upstream-worthy fix: use `PILHelper.to_native_touchscreen_format(deck, image)`
and full-strip composition for rotated decks.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER = "PATCHED(streamdeck-xl) v2: full-strip touchscreen writes"
CACHE_DECL = '_STRIP_TILES: dict[int, dict[int, Image.Image]] = {}'

# The pristine upstream block.
PRISTINE = """    img_bytes = io.BytesIO()
    image.save(img_bytes, format="JPEG")
    lcd_image_bytes = img_bytes.getvalue()
    deck.set_touchscreen_image(
        lcd_image_bytes,
        dial_offset,
        0,
        width=size_per_dial[0],
        height=size_per_dial[1],
    )
"""

NEW = f'''    # {MARKER}
    # The Plus XL reports TOUCHSCREEN_ROTATION=90 and its set_touchscreen_image
    # swaps the region geometry for the device, so bytes must be rotated. And
    # partial-region writes at a non-zero x silently don't land (verified on
    # hardware) — only a full-strip write does. So cache this dial's tile and
    # repaint the whole strip. Rotation-0 decks (the Plus) keep the original path.
    _ts_fmt = deck.touchscreen_image_format()
    _ts_rot = _ts_fmt.get("rotation", 0)
    if _ts_rot:
        _tiles = _STRIP_TILES.setdefault(id(deck), {{}})
        _tiles[dial_key] = image
        _sw, _sh = _ts_fmt["size"]
        _strip = Image.new("RGB", (_sw, _sh), "black")
        for _k, _tile in _tiles.items():
            _strip.paste(_tile, (_k * size_per_dial[0], 0))
        _rotated = _strip.rotate(_ts_rot, expand=True)
        img_bytes = io.BytesIO()
        _rotated.save(img_bytes, format="JPEG")
        deck.set_touchscreen_image(img_bytes.getvalue(), 0, 0, width=_sw, height=_sh)
    else:
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG")
        lcd_image_bytes = img_bytes.getvalue()
        deck.set_touchscreen_image(
            lcd_image_bytes,
            dial_offset,
            0,
            width=size_per_dial[0],
            height=size_per_dial[1],
        )
'''


def main() -> None:
    import home_assistant_streamdeck_yaml as m

    path = Path(m.__file__)
    src = path.read_text()

    if MARKER in src:
        print(f"already patched (v2): {path}")
        return

    # Strip any earlier version of this patch, restoring the pristine block.
    v1 = re.compile(
        r"    # PATCHED\(streamdeck-xl\): honour TOUCHSCREEN_ROTATION.*?"
        r"    _ts_rotation = deck\.touchscreen_image_format\(\)\.get\(\"rotation\", 0\)\n"
        r"    if _ts_rotation:\n"
        r"        image = image\.rotate\(_ts_rotation, expand=True\)\n",
        re.DOTALL,
    )
    if v1.search(src):
        src = v1.sub("", src)
        print("removed earlier v1 patch")

    if src.count(PRISTINE) != 1:
        sys.exit(
            f"cannot patch {path}: expected exactly 1 occurrence of the "
            f"touchscreen write block, found {src.count(PRISTINE)}. Upstream code "
            f"changed — review update_dial() and adjust this patch."
        )
    src = src.replace(PRISTINE, NEW)

    # Module-level tile cache, inserted just above update_dial().
    if CACHE_DECL not in src:
        anchor = "def update_dial(\n"
        if src.count(anchor) != 1:
            sys.exit(f"cannot locate update_dial() in {path}")
        src = src.replace(anchor, f"{CACHE_DECL}\n\n\n{anchor}", 1)

    path.write_text(src)
    print(f"patched full-strip touchscreen writes in {path}")


if __name__ == "__main__":
    main()

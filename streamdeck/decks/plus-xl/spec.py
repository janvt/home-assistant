"""Stream Deck Plus XL — image spec (what to render for this deck).

Consumed by ../../generate_icons.py (the shared renderer). Only *content* and
device geometry live here; the palette and drawing code are shared with the Plus.

Device: 36 keys (9x4) at 112x112, 6 dials, 1200x100 touch strip. A dial segment
is 1200/6 = 200x100 — identical to the Plus's 800/4 — so dial frames render
from the same code at the same size.

Layout is deliberately SPARSE — only 15 of the 36 keys are populated:

      col: 1        2       3         4        5        6      7 8   9
  row 1     Work S   Work    Chill     Vinyl    Pain C   ·      · ·   Lights Off
  row 2     Hallway  Kitchen LivingRm  Outside  Bathrm   Record · ·   House
  row 3     ·        ·       ·         ·        ·        ·      · ·   Apartment
  row 4     ·        ·       ·         ·        ·        ·      · ·   Fan

Row 1 = scenes, row 2 = lights, right edge (col 9) = the always-reachable
actions. Everything else is `special_type: empty`.
"""

KEY_PX = 112  # Stream Deck Plus XL native key size

# ── keys ────────────────────────────────────────────────────────────────────
# (slug, mdi icon, label, active style)
# STATEFUL renders <slug>_on (active style) + <slug>_off (grey).
# ACTION renders <slug> in its domain style.
STATEFUL = [
    # row 1 — scenes (highlighted from input_select.active_scene)
    ("work_s",      "desk",             "Work S",    "amber"),
    ("work",        "briefcase",        "Work",      "amber"),
    ("chill",       "sofa",             "Chill",     "amber"),
    ("vinyl",       "album",            "Vinyl",     "amber"),
    ("pain_cave",   "bike-fast",        "Pain Cave", "amber"),

    # row 2 — room lights
    ("hallway",     "human-walker",     "Hallway",   "amber"),
    ("kitchen",     "ceiling-light",    "Kitchen",   "amber"),
    ("lr_ceiling",  "ceiling-light",    "Living Rm", "amber"),
    ("outside",     "cloud",            "Outside",   "amber"),
    ("bathroom",    "shower",           "Bathroom",  "amber"),
    ("record",      "record-player",    "Record",    "amber"),

    # col 9 row 4 — bathroom fan hold
    ("fan",         "emoticon-poop",    "Fan",       "blue"),
]
ACTION = [
    # col 9 — right-edge actions
    ("lights_off",       "lightbulb-off",     "Lights Off", "amber"),
    ("unlock_house",     "lock-open-variant", "House",      "red"),
    ("unlock_apartment", "door-open",         "Apartment",  "red"),
]

# ── dials ───────────────────────────────────────────────────────────────────
# (slug, style, label) — frames are dials/<slug>_<pct>.png. Six dials here vs
# the Plus's four; same renderer, same 200x100 frames.
DIALS = [
    ("lr_volume",         "volume", "Living Room"),
    ("madagascar_volume", "volume", "Madagascar"),
    ("lr_bright",         "bright", "LR Ceiling"),
    ("kitchen_bright",    "bright", "Kitchen"),
    ("lr_shade",          "shade",  "Living Room"),
    ("kitchen_shade",     "shade",  "Kitchen"),
]

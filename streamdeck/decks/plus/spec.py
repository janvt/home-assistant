"""Stream Deck Plus — image spec (what to render for this deck).

Consumed by ../../generate_icons.py (the shared renderer). Only *content* and
device geometry live here; the palette and drawing code are shared.

Device: 8 keys (4x2) at 120x120, 4 dials, 800x100 touch strip (200x100/dial).
"""

KEY_PX = 120  # Stream Deck Plus native key size

# ── keys ────────────────────────────────────────────────────────────────────
# (slug, mdi icon, label, active style)
# STATEFUL renders <slug>_on (active style) + <slug>_off (grey).
# ACTION renders <slug> in its domain style.
STATEFUL = [
    ("chill",     "sofa",          "Chill",     "amber"),
    ("vinyl",     "album",         "Vinyl",     "amber"),
    ("pain_cave", "bike-fast",     "Pain Cave", "amber"),
    ("work_s",    "desk",          "Work S",    "amber"),
    ("hallway",   "human-walker",  "Hallway",   "amber"),
    ("outside",   "cloud",         "Outside",   "amber"),
    ("fan",       "emoticon-poop", "Fan",       "blue"),
    ("guest",     "account-group", "Guest",     "blue"),
    ("cleaning",  "broom",         "Cleaning",  "blue"),
]
ACTION = [
    ("lights_off", "lightbulb-off",       "Lights Off", "amber"),
    ("open_all",   "window-shutter-open", "Open All",   "green"),
    ("close_all",  "window-shutter",      "Close All",  "green"),
    ("apartment",  "door-open",           "Apartment",  "red"),
    ("house",      "home",                "House",      "red"),
    ("menu",       "dots-horizontal",     "Menu",       "blue"),
    # Active look for the plain "Work" scene (shown by the Work S key when
    # scene.work is active, via long-press). Amber like an active scene.
    ("work",       "briefcase",           "Work",       "amber"),
]

# ── dials ───────────────────────────────────────────────────────────────────
# (slug, style, label) — frames are dials/<slug>_<pct>.png
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

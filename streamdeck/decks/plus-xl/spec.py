"""Stream Deck Plus XL — image spec (what to render for this deck).

Consumed by ../../generate_icons.py (the shared renderer). Only *content* and
device geometry live here; the palette and drawing code are shared with the Plus.

Device: 36 keys (9x4) at 112x112, 6 dials, 1200x100 touch strip. A dial segment
is 1200/6 = 200x100 — identical to the Plus's 800/4 — so dial frames render
from the same code at the same size.

Layout is its own design (not a copy of the Plus): 36 keys means everything
fits on one page, so there's no mode/paging key. Rows, left to right:
  1  scenes
  2  room lights
  3  shades + media
  4  modes, doors, routines
"""

KEY_PX = 112  # Stream Deck Plus XL native key size

# ── keys ────────────────────────────────────────────────────────────────────
# (slug, mdi icon, label, active style)
# STATEFUL renders <slug>_on (active style) + <slug>_off (grey).
# ACTION renders <slug> in its domain style.
STATEFUL = [
    # row 1 — scenes (highlighted from input_select.active_scene)
    ("chill",       "sofa",             "Chill",     "amber"),
    ("vinyl",       "album",            "Vinyl",     "amber"),
    ("pain_cave",   "bike-fast",        "Pain Cave", "amber"),
    ("work",        "briefcase",        "Work",      "amber"),
    ("work_s",      "desk",             "Work S",    "amber"),
    ("cleaning_sc", "spray-bottle",     "Clean",     "amber"),
    ("sleep",       "weather-night",    "Sleep",     "amber"),

    # row 2 — room lights
    ("lr_ceiling",  "ceiling-light",    "Living Rm", "amber"),
    ("kitchen",     "ceiling-light",    "Kitchen",   "amber"),
    ("hallway",     "human-walker",     "Hallway",   "amber"),
    ("outside",     "cloud",            "Outside",   "amber"),
    ("bedroom",     "bed",              "Bedroom",   "amber"),
    ("bathroom",    "shower",           "Bathroom",  "amber"),
    ("reading",     "floor-lamp",       "Reading",   "amber"),
    ("record",      "record-player",    "Record",    "amber"),
    ("signe",       "floor-lamp-torchiere", "Signe", "amber"),

    # row 4 — mode helpers
    ("guest",       "account-group",    "Guest",     "blue"),
    ("cleaning",    "broom",            "Cleaning",  "blue"),
    ("be_smart",    "brain",            "Be Smart",  "blue"),
    ("fan",         "emoticon-poop",    "Fan",       "blue"),
]
ACTION = [
    # row 1 — whole-home light action
    ("lights_off",  "lightbulb-off",       "Lights Off", "amber"),

    # row 3 — shades
    ("open_all",    "window-shutter-open", "Open All",   "green"),
    ("close_all",   "window-shutter",      "Close All",  "green"),

    # row 3 — media transport
    ("play_pause",  "play-pause",          "Play",       "blue"),
    ("prev",        "skip-previous",       "Prev",       "blue"),
    ("next",        "skip-next",           "Next",       "blue"),
    ("tv",          "television",          "TV",         "blue"),
    ("appletv",     "apple",               "Apple TV",   "blue"),
    ("xbox",        "microsoft-xbox",      "Xbox",       "blue"),

    # row 4 — doors (5s cancel guard in configuration.yaml)
    ("apartment",   "door-open",           "Apartment",  "red"),
    ("house",       "home",                "House",      "red"),

    # row 4 — routines
    ("come_home",   "home-import-outline", "Come Home",  "green"),
    ("leave_home",  "exit-run",            "Leave",      "green"),
    ("wake_up",     "weather-sunset-up",   "Wake Up",    "green"),
    ("unlock",      "lock-open-variant",   "Unlock",     "red"),
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

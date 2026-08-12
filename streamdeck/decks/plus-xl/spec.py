"""Stream Deck Plus XL — image spec (what to render for this deck).

Consumed by ../../generate_icons.py (the shared renderer). Only *content* and
device geometry live here; the palette and drawing code are shared with the Plus.

Device: 36 keys (9x4) at 112x112, 6 dials, 1200x100 touch strip. A dial segment
is 1200/6 = 200x100 — identical to the Plus's 800/4 — so dial frames render
from the same code at the same size.

Layout populates 24 of the 36 keys, kept as compact blocks rather than spread
to the edges:

      col: 1        2       3         4        5       6           7        8       9
  row 1     Work S   Work    Chill     Vinyl    Pain C  Lights Off  Claude   Firefox 1Password
  row 2     Hallway  Kitchen LivingRm  Outside  Record  House       Slack    Warp    PHPStorm
  row 3     Cleaning Guest   Awake     Be Smart Fan     Apartment   Finder   Mail    Safari
  row 4     MuteLR   MuteMad MuteMac   Line In  ·       ·           ·        ·       ·

Rows 1-3 are five wide, so the left block squares off: scenes, then lights,
then the input_boolean toggles. Column 6 is the vertical strip of
always-reachable actions. Columns 7-9 (rows 1-3) are Mac app launchers —
`mac.open_app`, see ../../ext/ — with 1Password in the corner since it's used
constantly. Row 4 col 4 groups Living Room into Madagascar's Line In
(`script.streamdeck_audio_scene_linein`, defined in Home Assistant, not this
repo). Everything else is `special_type: empty`.
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
    ("record",      "record-player",    "Record",    "amber"),

    # row 3 — input_boolean toggles (blue = "mode", per the other decks)
    ("cleaning",    "broom",            "Cleaning",  "blue"),
    ("guest",       "account-group",    "Guest",     "blue"),
    ("awake",       "eye",              "Awake",     "blue"),
    ("be_smart",    "brain",            "Be Smart",  "blue"),
    ("fan",         "emoticon-poop",    "Fan",       "blue"),
]
ACTION = [
    # col 6 — the vertical strip of always-reachable actions
    ("lights_off",       "lightbulb-off",     "Lights Off", "amber"),
    ("unlock_house",     "lock-open-variant", "House",      "red"),
    ("unlock_apartment", "door-open",         "Apartment",  "red"),

    # row 1 col 9 — launches the Mac app (mac.open_app, see ../../ext/)
    ("onepassword",      "onepassword",       "1Password",  "blue"),

    # row 4 cols 1-3 — mute toggles, sitting under the three volume dials.
    # These are ACTION pairs rather than STATEFUL entries because the two states
    # need DIFFERENT icons (a greyed volume-off would read as "muted" when it
    # means the opposite). STATEFUL renders one mdi in two styles; here we want
    # two mdi glyphs, so the config template picks between two files.
    ("mute_lr_on",   "volume-off",  "Living Rm",  "cyan"),
    ("mute_lr_off",  "volume-high", "Living Rm",  "off"),
    ("mute_mad_on",  "volume-off",  "Madagascar", "cyan"),
    ("mute_mad_off", "volume-high", "Madagascar", "off"),
    ("mute_mac_on",  "volume-off",  "Mac",        "cyan"),
    ("mute_mac_off", "volume-high", "Mac",        "off"),

    # row 4 col 4 — audio scene: group Living Room into Madagascar's Line In.
    # A plain action, not STATEFUL: Sonos exposes no single boolean for
    # "grouped", so there's nothing sensible to highlight.
    ("audio_scene_linein", "audio-input-rca", "Line In", "green"),

    # cols 7-9, rows 1-3 — Mac app launchers (mac.open_app, see ../../ext/).
    # No on/off state to track, so these are plain ACTION keys like 1Password.
    ("claude",        "creation",       "Claude",   "blue"),
    ("firefox",       "firefox",        "Firefox",  "blue"),
    ("slack",         "slack",          "Slack",    "blue"),
    ("warp",          "console",        "Warp",     "blue"),
    ("phpstorm",      "language-php",   "PHPStorm", "blue"),
    ("finder",        "apple-finder",   "Finder",   "blue"),
    ("mail",          "mail",           "Mail",     "blue"),
    ("safari",        "apple-safari",   "Safari",   "blue"),
]

# ── dials ───────────────────────────────────────────────────────────────────
# (slug, style, label) — frames are dials/<slug>_<pct>.png. Six dials here vs
# the Plus's four; same renderer, same 200x100 frames.
# Dial 3 is this Mac's own output volume, not an HA entity — see ../../ext/.
DIALS = [
    ("lr_volume",         "volume", "Living Room"),
    ("madagascar_volume", "volume", "Madagascar"),
    ("mac_volume",        "volume", "Mac"),
    ("kitchen_bright",    "bright", "Kitchen"),
    ("lr_shade",          "shade",  "Living Room"),
    ("kitchen_shade",     "shade",  "Kitchen"),
]

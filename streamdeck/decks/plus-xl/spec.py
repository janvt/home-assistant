"""Stream Deck Plus XL — image spec (what to render for this deck).

Consumed by ../../generate_icons.py (the shared renderer). Only *content* and
device geometry live here; the palette and drawing code are shared with the Plus.

Device: 36 keys (9x4) at 112x112, 6 dials, 1200x100 touch strip. A dial segment
is 1200/6 = 200x100 — identical to the Plus's 800/4 — so dial frames render
from the same code at the same size.

Two pages now: Home and Settings, reached via a page-nav key each way
(`go-to-page` by name in both directions — with only two pages, a dedicated
key each way reads clearer than next-page/previous-page cycling).

Home populates 29 of 36 keys, kept as compact blocks rather than spread to the
edges:

      col: 1        2       3         4        5       6           7        8       9
  row 1     Work S   Work    Chill     Vinyl    Pain C  Lights Off  Claude   Firefox 1Password
  row 2     Hallway  Kitchen LivingRm  Outside  Record  House       Slack    Warp    PHPStorm
  row 3     Cleaning Guest   ·         ·        Fan     Apartment   Finder   Mail    Safari
  row 4     MuteLR   MuteMad MuteMac   Line In  CO2     PowerUse    ·        ·       ...

Rows 1-3 are five wide, so the left block squares off: scenes, then lights,
then the input_boolean toggles (Awake and Be Smart moved to the Settings page
— see below). Column 6 is the vertical strip of always-reachable actions.
Columns 7-9 (rows 1-3) are Mac app launchers — `mac.open_app`, see ../../ext/
— with 1Password in the corner since it's used constantly. Row 4 col 4 groups
Living Room into Madagascar's Line In (`script.streamdeck_audio_scene_linein`,
defined in Home Assistant, not this repo). Row 4 cols 5-6 are no-op display
tiles — indoor CO2, then (under the Apartment lock key) live apartment power
draw — see the `INFO` list below. Bottom right (row 4 col 9) is the Settings
page-nav key — deliberately just "..." (no icon glyph, no label), so it
reads as a quiet "more" affordance rather than another feature button.
Everything else is `special_type: empty`.

Settings is a second page, not a second grid to fill — deliberately sparse:

      col: 1        2         3   ...   9
  row 1     Awake    Be Smart  ·   ...   ·
  row 4     ·        ·         ·   ...   Home

Home (row 4 col 9) is in the same physical spot as Home page's Settings key —
same corner either way, regardless of which page you're on.

Dial 1 on this page drives the deck's own screen brightness
(`input_number.streamdeck_xl_brightness` — see the README's "Exposing deck
settings to Home Assistant" section): the one dial here that isn't a Home
Assistant entity in the usual sense, but a setting on the deck itself. Dials
2-6 are intentionally undefined on this page — the app blanks unconfigured
touchscreen segments automatically, and nudging one just logs harmlessly
instead of doing anything, which is fine for a page nobody lingers on.
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

    # page navigation — Home <-> Settings. Deliberately unlabelled: an empty
    # label centers the glyph and renders no text (see generate_icons.py's
    # render_key), so these read as a quiet "..." rather than another
    # feature button competing for attention.
    ("settings", "dots-horizontal", "", "blue"),
    ("home",     "dots-horizontal", "", "blue"),

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

# INFO renders <slug>_<green|amber|red> via render_info_key: icon high, unit
# label low, a gap left in between for the app's own live `text:` template —
# a read-only readout, not a button. The matching configuration.yaml entry
# has no `service:`, so pressing it is a no-op (see _handle_key_press:
# nothing runs unless special_type or service is set). configuration.yaml
# picks which of the 3 colour variants to show based on that sensor's own
# thresholds — see the comments there for the actual numbers.
# (slug, mdi icon, label — label is the UNIT, e.g. "ppm", not a place name)
INFO = [
    # row 4 col 5, left of the power tile — indoor CO2 from the desk sensor.
    ("co2", "molecule-co2", "ppm"),
    # row 4 col 6, under the Apartment lock key.
    ("apartment_power", "lightning-bolt", "W"),
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
    # Settings page, dial 1: the deck's own screen brightness.
    ("deck_bright",       "bright", "Deck"),
]

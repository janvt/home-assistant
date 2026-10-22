"""Which timetable train was that? Fuzzy-matches each train the cameras count.

The boards come from `ha-timetable.yaml` (REST sensors, pasted into HA's
configuration once). `sync.py` pushes the rest: the tuning helpers, one
`input_text` per camera holding its last match, and the automation that fills
them. Changing the automation or a default here and running `sync.py` is all
a change needs; the helpers' values are yours to tune on the dashboard.

When a camera's "train passing" helper turns on, the automation lists every
train expected at Altdorf around then and takes the closest one in time:
- trains that stop: their arrival at Altdorf, with its delay;
- trains that fly through southbound: departure from Arth-Goldau plus delay
  plus TRAVEL_SOUTH minutes, for trains whose stops after it skip Altdorf;
- through trains northbound: departure from Bellinzona plus delay plus
  TRAVEL_NORTH minutes, for trains whose stops after it reach Arth-Goldau
  without Altdorf.
Nothing within WINDOW minutes means a train the timetable doesn't have,
usually freight.
"""
from __future__ import annotations

from typing import Any

ALTDORF = "sensor.altdorf_arrivals"
ARTH_GOLDAU = "sensor.arth_goldau_departures"
BELLINZONA = "sensor.bellinzona_departures"
BOARDS = [ALTDORF, ARTH_GOLDAU, BELLINZONA]

TRAVEL_SOUTH = "input_number.train_through_minutes_south"
TRAVEL_NORTH = "input_number.train_through_minutes_north"
WINDOW = "input_number.train_match_window"
# HA slugifies the name into the entity id, so the names must stay as they are.
NUMBERS = [
    dict(entity=TRAVEL_SOUTH, name="Train through minutes south", min=5, max=40, step=1, initial=18,
         unit_of_measurement="min", icon="mdi:arrow-down-bold", mode="box"),
    dict(entity=TRAVEL_NORTH, name="Train through minutes north", min=15, max=60, step=1, initial=32,
         unit_of_measurement="min", icon="mdi:arrow-up-bold", mode="box"),
    dict(entity=WINDOW, name="Train match window", min=1, max=10, step=1, initial=3,
         unit_of_measurement="min", icon="mdi:timer-sand", mode="box"),
]
# {camera label: (its "train passing" helper, the input_text for its last match)}
CAMERAS = {
    "Reolink": ("binary_sensor.train_passing", "input_text.last_train"),
    "iPhone": ("binary_sensor.train_passing_tele", "input_text.last_train_tele"),
}
TEXTS = [dict(entity=text, name="Last train" + ("" if label == "Reolink" else " tele"), max=255,
              icon="mdi:train-variant") for label, (_, text) in CAMERAS.items()]
AUTOMATION_ID = "trains_match_timetable"

# The expected trains as a list of {d: seconds from now, n: name, k: kind}.
# `number` is "000029" for an EC, so it goes through int when it can.
CANDIDATES = (
    "{% set t = now().timestamp() %}{% set ns = namespace(c=[]) %}"
    "{% macro name(j) %}{{ j.category }} {{ j.number | int(j.number) }} → {{ j.to }}{% endmacro %}"
    "{% for j in state_attr('" + ALTDORF + "','stationboard') or [] %}"
    "{% set at = j.stop.arrival or j.stop.departure %}{% if at %}"
    "{% set ns.c = ns.c + [{'d': as_timestamp(at) + (j.stop.delay or 0) * 60 - t, 'n': name(j),"
    " 'k': 'stops, platform ' ~ (j.stop.platform or '?'), 'late': j.stop.delay or 0}] %}{% endif %}{% endfor %}"
    "{% for j in state_attr('" + ARTH_GOLDAU + "','stationboard') or [] %}"
    "{% set s = (j.passList or []) | map(attribute='station.name') | list %}"
    "{% if 'Bellinzona' in s and 'Altdorf UR' not in s %}"
    "{% set ns.c = ns.c + [{'d': as_timestamp(j.stop.departure) + ((j.stop.delay or 0)"
    " + states('" + TRAVEL_SOUTH + "') | float(18)) * 60 - t, 'n': name(j), 'k': 'through, southbound',"
    " 'late': j.stop.delay or 0}] %}{% endif %}{% endfor %}"
    "{% for j in state_attr('" + BELLINZONA + "','stationboard') or [] %}"
    "{% set s = (j.passList or []) | map(attribute='station.name') | list %}"
    "{% if 'Arth-Goldau' in s and 'Altdorf UR' not in s %}"
    "{% set ns.c = ns.c + [{'d': as_timestamp(j.stop.departure) + ((j.stop.delay or 0)"
    " + states('" + TRAVEL_NORTH + "') | float(32)) * 60 - t, 'n': name(j), 'k': 'through, northbound',"
    " 'late': j.stop.delay or 0}] %}{% endif %}{% endfor %}"
)
# One line for the input_text: "19:36 EC 29 → Como S. Giovanni · through,
# southbound · +2 min late · 1 min off", or "19:36 no timetable train (freight?)".
# Cut to the 255 characters an input_text takes.
MATCH = (
    CANDIDATES
    + "{% set w = states('" + WINDOW + "') | float(3) * 60 %}{% set ns2 = namespace(b=none) %}"
    "{% for c in ns.c if (c.d | abs) <= w %}"
    "{% if ns2.b is none or (c.d | abs) < (ns2.b.d | abs) %}{% set ns2.b = c %}{% endif %}{% endfor %}"
    "{% set out %}{{ now().strftime('%H:%M') }} "
    "{% if ns2.b %}{{ ns2.b.n }} · {{ ns2.b.k }}{{ ' · +' ~ ns2.b.late ~ ' min late' if ns2.b.late > 0 }}"
    " · {{ (ns2.b.d / 60) | abs | round(0) | int }} min off"
    "{% else %}no timetable train (freight?){% endif %}{% endset %}{{ out[:255] }}"
)


def automation() -> dict[str, Any]:
    return {
        "id": AUTOMATION_ID,
        "alias": "Trains: match each counted train to the timetable",
        "description": "Managed by dashboards/trains/sync.py (timetable.py). Writes the closest timetable "
                       "train to the camera's input_text; nothing close means freight or a special.",
        "mode": "queued",
        "triggers": [{"trigger": "state", "entity_id": passing, "from": "off", "to": "on", "id": label}
                     for label, (passing, _) in CAMERAS.items()],
        "actions": [{"choose": [
            {"conditions": [{"condition": "trigger", "id": label}],
             "sequence": [{"action": "input_text.set_value", "target": {"entity_id": text},
                           "data": {"value": MATCH}}]}
            for label, (_, text) in CAMERAS.items()]}],
    }


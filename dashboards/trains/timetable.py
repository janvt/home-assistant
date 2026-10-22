"""Which timetable train was that, and which ones did the cameras miss?

The boards and the past-trains sensor live in `ha-timetable.yaml`, pasted into
HA's configuration once: the API can't create REST or trigger-based template
sensors. That file is generated from this one (`python timetable.py`), so the
matching is written once. `sync.py` pushes the rest: the tuning helpers, one
`input_text` per camera holding its last match, and the automation that fills
them. The helpers' values are yours to tune on the dashboard.

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

The other way round, `sensor.timetable_trains_past` notes each camera's
detection times and, every 5 minutes, adds the timetable trains whose time is
over by more than WINDOW, with whether each camera saw one within WINDOW of it.
That lists the trains that went past undetected, per camera.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

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

PAST = "sensor.timetable_trains_past"
# The expected trains as a list of {d: seconds from now, n: name, k: kind,
# key: name and scheduled time, the same on every refresh of the board}.
# `number` is "000029" for an EC, so it goes through int when it can.
CANDIDATES = (
    "{% set t = now().timestamp() %}{% set ns = namespace(c=[]) %}"
    "{% macro name(j) %}{{ j.category }} {{ j.number | int(j.number) }} → {{ j.to }}{% endmacro %}"
    "{% for j in state_attr('" + ALTDORF + "','stationboard') or [] %}"
    "{% set at = j.stop.arrival or j.stop.departure %}{% if at %}"
    "{% set ns.c = ns.c + [{'d': as_timestamp(at) + (j.stop.delay or 0) * 60 - t, 'n': name(j),"
    " 'k': 'stops, platform ' ~ (j.stop.platform or '?'), 'late': j.stop.delay or 0, 'key': name(j) ~ at}] %}{% endif %}{% endfor %}"
    "{% for j in state_attr('" + ARTH_GOLDAU + "','stationboard') or [] %}"
    "{% set s = (j.passList or []) | map(attribute='station.name') | list %}"
    "{% if 'Bellinzona' in s and 'Altdorf UR' not in s %}"
    "{% set ns.c = ns.c + [{'d': as_timestamp(j.stop.departure) + ((j.stop.delay or 0)"
    " + states('" + TRAVEL_SOUTH + "') | float(18)) * 60 - t, 'n': name(j), 'k': 'through, southbound',"
    " 'late': j.stop.delay or 0, 'key': name(j) ~ j.stop.departure}] %}{% endif %}{% endfor %}"
    "{% for j in state_attr('" + BELLINZONA + "','stationboard') or [] %}"
    "{% set s = (j.passList or []) | map(attribute='station.name') | list %}"
    "{% if 'Arth-Goldau' in s and 'Altdorf UR' not in s %}"
    "{% set ns.c = ns.c + [{'d': as_timestamp(j.stop.departure) + ((j.stop.delay or 0)"
    " + states('" + TRAVEL_NORTH + "') | float(32)) * 60 - t, 'n': name(j), 'k': 'through, northbound',"
    " 'late': j.stop.delay or 0, 'key': name(j) ~ j.stop.departure}] %}{% endif %}{% endfor %}"
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


# ── the past-trains sensor (goes into ha-timetable.yaml) ────────────────────
def _seen(label: str) -> str:
    return "seen_" + label.lower()


def _attr(name: str, default: str = "[]") -> str:
    return "(this.attributes.get('" + name + "', " + default + ") if this.attributes is defined else " + default + ")"


def past_sensor() -> dict[str, Any]:
    """Trigger-based: `this` is the sensor before the trigger, so each attribute
    builds on its own last value. Detection times are kept 2 h, past trains 24 h."""
    seen = {_seen(label): (
        "{% set keep = " + _attr(_seen(label)) + " | select('gt', now().timestamp() - 7200) | list %}"
        "{{ keep + [now().timestamp() | int] if trigger.id == '" + label + "' else keep }}")
        for label in CAMERAS}
    flags = "".join(
        "{% set f_" + label.lower() + " = " + _attr(_seen(label)) + " | select('ge', ct - w) | select('le', ct + w)"
        " | list | count > 0 %}" for label in CAMERAS)
    entry = ("{'t': ct, 'n': c.n, 'k': c.k, 'key': c.key"
             + "".join(", '" + label.lower() + "': f_" + label.lower() for label in CAMERAS) + "}")
    past = (
        "{% set old = " + _attr("past") + " | selectattr('t', 'gt', now().timestamp() - 86400) | list %}"
        "{% set since = " + _attr("since", "0") + " | int(0) %}"
        "{% if trigger.id != 'check' %}{{ old }}{% else %}"
        + CANDIDATES
        + "{% set w = states('" + WINDOW + "') | float(3) * 60 %}"
        "{% set keys = old | map(attribute='key') | list %}{% set ns3 = namespace(new=[]) %}"
        "{% for c in ns.c | sort(attribute='d') if c.d < -w and c.d > -1800 and c.key not in keys %}"
        "{% set ct = (t + c.d) | int %}{% if ct > since %}" + flags
        + "{% set ns3.new = ns3.new + [" + entry + "] %}{% endif %}{% endfor %}"
        "{{ (old + ns3.new)[-200:] }}{% endif %}")
    missed_by_all = " and ".join("not p." + label.lower() for label in CAMERAS)
    return {
        "triggers": [{"trigger": "state", "entity_id": passing, "from": "off", "to": "on", "id": label}
                     for label, (passing, _) in CAMERAS.items()]
                    + [{"trigger": "time_pattern", "minutes": "/5", "id": "check"}],
        "sensor": [{
            "name": "Timetable trains past",
            "unique_id": "trains_timetable_past",
            "icon": "mdi:train-car",
            # Missed by every camera today. Built from the previous `past`, so it
            # trails the list by one trigger (at most 5 minutes).
            "state": "{% set ns = namespace(n=0) %}{% for p in " + _attr("past") + " %}"
                     "{% if p.t > today_at().timestamp() and " + missed_by_all + " %}{% set ns.n = ns.n + 1 %}"
                     "{% endif %}{% endfor %}{{ ns.n }}",
            # When the sensor started watching: trains before it would all look missed.
            "attributes": {"since": "{{ " + _attr("since", "0") + " or now().timestamp() | int }}",
                           **seen, "past": past},
        }],
    }


HEADER = """\
# ─────────────────────────────────────────────────────────────────────────────
# Trains past the window: the timetable, and the trains the cameras missed
#
# GENERATED by dashboards/trains/timetable.py (`python timetable.py`), which
# holds the matching once for this file and for the automation sync.py pushes.
# Change it there, not here: a test fails when the two differ.
#
# WHAT
#   rest: three station boards from transport.opendata.ch (free, no key),
#     refreshed every 5 minutes:
#     - Altdorf UR arrivals: trains that stop at Altdorf.
#     - Arth-Goldau departures: southbound trains; those whose stops skip
#       Altdorf fly through it, TRAVEL_SOUTH min after leaving Arth-Goldau.
#     - Bellinzona departures: northbound trains; those that skip Altdorf fly
#       through it TRAVEL_NORTH min after leaving Bellinzona.
#     Each board starts a little in the past, so a train that has just passed
#     is still on it. Only the fields the matching needs are fetched, to keep
#     each sensor's attributes small.
#   template: sensor.timetable_trains_past, the timetable trains that went
#     past, with whether each camera saw them. Its state is how many no camera
#     saw today.
#
# INSTALL
#   As a package: copy this file to /config/packages/trains_timetable.yaml,
#   have configuration.yaml load the folder,
#       homeassistant:
#         packages: !include_dir_named packages
#   and restart Home Assistant (packages load only on a restart). After a
#   change, replace the file and restart again. Everything else (helpers, the
#   matching automation, the dashboard) is pushed by
#   dashboards/trains/sync.py over the API.
#
# RATE
#   3 boards every 300 s is ~860 requests a day. transport.opendata.ch is a
#   free community service: don't poll faster.
# ─────────────────────────────────────────────────────────────────────────────

"""
BOARD_FIELDS = ["category", "number", "to", "stop/departure", "stop/delay"]


def _board(name: str, uid: str, station: str, back: int, limit: int, extra: str, fields: list[str]) -> dict[str, Any]:
    since = "(now() - timedelta(minutes=" + str(back) + "))"
    url = ("https://transport.opendata.ch/v1/stationboard?station=" + station + extra + "&limit=" + str(limit)
           + "&datetime={{ " + since + ".strftime('%Y-%m-%d') }}%20{{ " + since + ".strftime('%H:%M') }}"
           + "".join("&fields[]=stationboard/" + f for f in fields))
    return {"resource_template": url, "scan_interval": 300, "timeout": 20,
            "sensor": [{"name": name, "unique_id": uid, "icon": "mdi:train",
                        "value_template": "{{ value_json.stationboard | count }}",
                        "json_attributes": ["stationboard"]}]}


def package() -> dict[str, Any]:
    return {
        "rest": [
            _board("Altdorf arrivals", "trains_board_altdorf_arrivals", "8505113", 15, 20, "&type=arrival",
                   BOARD_FIELDS + ["stop/arrival", "stop/platform"]),
            _board("Arth-Goldau departures", "trains_board_arth_goldau_departures", "Arth-Goldau", 40, 40, "",
                   BOARD_FIELDS + ["passList/station/name"]),
            _board("Bellinzona departures", "trains_board_bellinzona_departures", "Bellinzona", 60, 40, "",
                   BOARD_FIELDS + ["passList/station/name"]),
        ],
        "template": [past_sensor()],
    }


def render() -> str:
    return HEADER + yaml.safe_dump(package(), sort_keys=False, allow_unicode=True, width=10_000)


if __name__ == "__main__":
    (Path(__file__).resolve().parent / "ha-timetable.yaml").write_text(render())
    print("wrote ha-timetable.yaml", file=sys.stderr)

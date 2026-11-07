"""The Infrastructure dashboard (`dashboard-infrastructure`): the roads and
tunnels around us. The Gotthard view has the road tunnel; the Roads view the
Axenstrasse and the closures of the A2 and A4, each way; the Passes view the
alpine passes nearby; the Flights view the planes overhead, from FlightRadar24.

`build()` returns the whole config, owned by the script like the Trains one: a
card added in the UI is gone after the next sync.

Everything on the Gotthard view comes from the Gotthard integration
(github.com/janvt/homeassistant-gotthard): FEDRO's traffic messages for the
tunnel's queues, closures and messages, and the two portal webcams. The north
portal's queue is southbound before Göschenen, the south portal's northbound
before Airolo.

The Passes view comes from the Alpine Passes integration
(github.com/janvt/homeassistant-alpine-passes), which reads alpen-paesse.ch of
IG Alpenpässe.
"""
from __future__ import annotations

from typing import Any

DASHBOARD = "dashboard-infrastructure"
TITLE = "Infrastructure"
ICON = "mdi:highway"

TUNNEL = "binary_sensor.gotthard_tunnel"
QUEUE = {"north": "sensor.gotthard_queue_before_the_north_portal",
         "south": "sensor.gotthard_queue_before_the_south_portal"}
DELAY = {"north": "sensor.gotthard_delay_before_the_north_portal",
         "south": "sensor.gotthard_delay_before_the_south_portal"}
CLOSURE = "sensor.gotthard_next_tunnel_closure"
MESSAGES = "sensor.gotthard_traffic_messages"
WEBCAM = {"north": "camera.gotthard_north_portal_goschenen", "south": "camera.gotthard_south_portal_airolo"}
UPDATE = "update.gotthard_update"
# The A2 and A4 closures, the Axenstrasse among them: the integration's
# "National roads" device.
AXENSTRASSE = "binary_sensor.national_roads_axenstrasse"
AXEN_CLOSURE = "sensor.national_roads_next_axenstrasse_closure"
ROADS = {  # road: [(sensor, direction), …], northbound first
    "A2": [("sensor.national_roads_a2_closures_northbound_to_basel", "towards Basel"),
           ("sensor.national_roads_a2_closures_southbound_to_chiasso", "towards Chiasso")],
    "A4": [("sensor.national_roads_a4_closures_northbound_to_schaffhausen", "towards Schaffhausen"),
           ("sensor.national_roads_a4_closures_southbound_to_altdorf", "towards Altdorf")],
}
# The traffic counters (opt in in the integration's options): a device per
# station, from north to south, with traffic, lorries and speed each way.
STATIONS = [("a2_stans", "Stans"), ("a2_buochs", "Buochs"), ("a2_seedorf", "Seedorf"), ("a2_altdorf", "Altdorf"),
            ("a2_amsteg", "Amsteg"), ("a2_gurtnellen", "Gurtnellen"), ("a2_wassen", "Wassen"),
            ("a2_goschenen", "Göschenen"), ("a2_quinto", "Quinto"), ("a4_goldau", "Goldau"), ("a4_schwyz", "Schwyz"),
            ("a4_sisikon_axenstrasse", "Sisikon (Axenstrasse)")]
DIRECTIONS = {"south": "southbound", "north": "northbound"}
KINDS = ("traffic", "lorries", "speed")


def station(key: str, direction: str, kind: str) -> str:
    return f"sensor.{key}_{DIRECTIONS[direction]}_{kind}"


FORMING = {"south": "binary_sensor.gotthard_queue_forming_before_the_north_portal",  # southbound queue
           "north": "binary_sensor.gotthard_queue_forming_before_the_south_portal"}
AXEN_TRAFFIC = "binary_sensor.national_roads_axenstrasse_traffic"
TRAVEL = {"altdorf_goschenen": "Altdorf → Göschenen", "goschenen_altdorf": "Göschenen → Altdorf",
          "altdorf_stans": "Altdorf → Stans", "stans_altdorf": "Stans → Altdorf"}


def travel(route: str) -> str:
    return f"sensor.national_roads_travel_time_{route}"


# The closures (restrictions too, if turned on in the integration's options)
# as calendars.
CALENDARS = {"calendar.gotthard_tunnel_closures": "Gotthard tunnel", "calendar.national_roads_axenstrasse": "Axenstrasse (A4)",
             "calendar.national_roads_gotthard_pass": "Gotthard Pass", "calendar.national_roads_a2": "A2",
             "calendar.national_roads_a4": "A4"}
COUNTED = [*(station(k, d, kind) for k, _ in STATIONS for d in DIRECTIONS for kind in KINDS),
           *FORMING.values(), AXEN_TRAFFIC, *map(travel, TRAVEL)]
# Every entity the integration makes, all of them on the page.
ENTITIES = [TUNNEL, *QUEUE.values(), *DELAY.values(), CLOSURE, MESSAGES, *WEBCAM.values(), UPDATE,
            AXENSTRASSE, AXEN_CLOSURE, *(sensor for directions in ROADS.values() for sensor, _ in directions),
            *COUNTED, *CALENDARS]

# The passes within about 40 km of home, nearest first, as the Alpine Passes
# integration names them (its entry has the same passes).
PASSES = {"klausenpass": "Klausenpass", "ibergereggpass": "Ibergereggpass", "sustenpass": "Sustenpass",
          "pragelpass": "Pragelpass", "oberalppass": "Oberalppass", "gotthardpass": "Gotthardpass",
          "lukmanierpass": "Lukmanierpass", "furkapass": "Furkapass"}
PASS_ENTITY = {"status": "sensor.{}_status", "since": "sensor.{}_status_since",
               "temperature": "sensor.{}_temperature", "weather": "sensor.{}_weather",
               "open": "binary_sensor.{}_open", "chains": "binary_sensor.{}_snow_chains_required",
               "trucks": "binary_sensor.{}_truck_restrictions"}
# Every entity of the passes, all of them on the page.
PASS_ENTITIES = [entity.format(slug) for slug in PASSES for entity in PASS_ENTITY.values()]
# When the integration last read the site: old if the site cannot be read.
PASSES_LAST_UPDATE = "sensor.alpine_passes_last_update"
WEATHER = {"clear": "clear", "clouds": "cloudy", "atmosphere": "misty", "drizzle": "drizzle",
           "rain": "rain", "snow": "snow", "thunderstorm": "thunderstorms"}

PORTALS = {"north": ("North portal, southbound", "Göschenen"),
           "south": ("South portal, northbound", "Airolo")}

# The messages, without their "Freigegeben:" and with when they end.
MESSAGE_LIST = ("{% for m in state_attr('" + MESSAGES + "', 'messages') or [] %}"
                "- {{ m.text | regex_replace('^\\\\w+: ', '') }}"
                "{{ ' _(until ' ~ as_timestamp(m.end) | timestamp_custom('%d.%m. %H:%M') ~ ')_' if m.end }}\n"
                "{% else %}No messages about the Gotthard.{% endfor %}")
CLOSURE_LIST = ("{% for c in state_attr('" + CLOSURE + "', 'closures') or [] %}"
                "- **{{ as_timestamp(c.start) | timestamp_custom('%a %d.%m. %H:%M') }}"
                "{{ ' to ' ~ as_timestamp(c.end) | timestamp_custom('%H:%M') if c.end }}**: "
                "{{ c.text | regex_replace('^\\\\w+: ', '') }}\n"
                "{% else %}No closures of the tunnel announced.{% endfor %}")


def heading(text: str, icon: str, style: str = "title") -> dict[str, Any]:
    return {"type": "heading", "heading": text, "heading_style": style, "icon": icon}


def tile(entity: str, name: str, columns: int = 6, **extra: Any) -> dict[str, Any]:
    return {"type": "tile", "entity": entity, "name": name, "vertical": True,
            "grid_options": {"columns": columns}, **extra}


def hist(entities: dict[str, str], title: str, hours: int = 24) -> dict[str, Any]:
    return {"type": "history-graph", "title": title, "hours_to_show": hours,
            "entities": [{"entity": e, "name": n} for e, n in entities.items()]}


def now_section() -> dict[str, Any]:
    cards = [heading("Gotthard road tunnel", "mdi:tunnel"), tile(TUNNEL, "Tunnel", 4),
             tile(CLOSURE, "Next closure", 4), tile(AXENSTRASSE, "Axenstrasse (A4)", 4)]
    for portal, (name, town) in PORTALS.items():
        cards += [heading(f"{name} ({town})", "mdi:car-multiple", "subtitle"),
                  tile(QUEUE[portal], "Queue"), tile(DELAY[portal], "Delay")]
    return {"type": "grid", "cards": cards}


def webcam_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Webcams", "mdi:webcam"),
        *({"type": "picture-entity", "entity": WEBCAM[portal], "name": f"{town} ({name.split(',')[0]})",
           "camera_view": "auto", "show_state": False, "grid_options": {"columns": "full"}}
          for portal, (name, town) in PORTALS.items()),
    ]}


def messages_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Traffic messages", "mdi:message-alert"),
        {"type": "markdown", "content": MESSAGE_LIST, "grid_options": {"columns": "full"}},
        heading("Tunnel closures announced", "mdi:calendar-alert", "subtitle"),
        {"type": "markdown", "content": CLOSURE_LIST, "grid_options": {"columns": "full"}},
        tile(UPDATE, "Gotthard integration", 12, vertical=False),
        {"type": "markdown", "content":
            "<small>Data: FEDRO (ASTRA) via opentransportdata.swiss, every 5 minutes. A queue with no "
            "length in its message shows as unknown. Webcams on the A2, updated every 5 minutes.</small>",
         "grid_options": {"columns": "full"}},
    ]}


def history_section() -> dict[str, Any]:
    names = {portal: town for portal, (_, town) in PORTALS.items()}
    return {"type": "grid", "column_span": 3, "cards": [
        heading("History", "mdi:chart-timeline-variant"),
        dict(hist({QUEUE[p]: n for p, n in names.items()}, "Queue, last 24 hours (km)"),
             grid_options={"columns": 6}),
        dict(hist({DELAY[p]: n for p, n in names.items()}, "Delay, last 24 hours (min)"),
             grid_options={"columns": 6}),
        dict(hist({TUNNEL: "Tunnel"}, "Tunnel open, last 7 days", hours=168), grid_options={"columns": 12}),
        {"type": "statistics-graph", "title": "Longest delay per day (30 days)", "stat_types": ["max"],
         "entities": [{"entity": DELAY[p], "name": n} for p, n in names.items()],
         "period": "day", "days_to_show": 30, "chart_type": "bar", "grid_options": {"columns": 12}},
    ]}


def calendar_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 3, "cards": [
        heading("Closures to come", "mdi:calendar-alert"),
        # A week's list needs the height: at the default, it shows a day or two.
        {"type": "calendar", "initial_view": "listWeek", "grid_options": {"columns": "full", "rows": 10},
         "entities": list(CALENDARS)},
    ]}


def axenstrasse_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Axenstrasse (A4)", "mdi:road-variant"),
        tile(AXENSTRASSE, "Axenstrasse (A4)", 4), tile(AXEN_TRAFFIC, "Traffic counted", 4),
        tile(AXEN_CLOSURE, "Next closure", 4),
        {"type": "markdown", "grid_options": {"columns": "full"}, "content":
            "{{ '<small>The traffic messages say closed, but vehicles are counted at Sisikon, so it shows as '"
            "'open.</small>' if state_attr('" + AXENSTRASSE + "', 'traffic_flowing') and state_attr('" + AXENSTRASSE + "', 'closures') }}"},
    ]}


def road_section(road: str) -> dict[str, Any]:
    """How many closures each way now. What they are, and those to come, are
    in the calendar above: lists here repeated it, and each other, as a
    closure both ways is on both directions."""
    return {"type": "grid", "cards": [
        heading(f"{road} closures now", "mdi:highway"),
        *(tile(sensor, direction.capitalize(), 6) for sensor, direction in ROADS[road]),
    ]}


def roads_history_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 3, "cards": [
        heading("History", "mdi:chart-timeline-variant"),
        dict(hist({AXENSTRASSE: "Axenstrasse (A4)", TUNNEL: "Gotthard tunnel"}, "Open, last 7 days", hours=168),
             grid_options={"columns": 12}),
    ]}


def station_table() -> str:
    """Every station now: vehicles and speed each way, and lorries."""
    def cell(key: str, direction: str, kind: str, digits: int = 0) -> str:
        e = station(key, direction, kind)
        return ("{{ states('" + e + "') | float(0) | round(" + str(digits) + ") | int "
                "if states('" + e + "') | is_number else '–' }}")
    # The columns in KINDS order: traffic, lorries, speed.
    head = ("| Station | " + " | ".join(f"{arrow} {unit}" for arrow in "↓↑" for unit in ("veh/h", "lorries", "km/h"))
            + " |\n|:--|--:|--:|--:|--:|--:|--:|\n")
    rows = "".join(f"| {name} | " + " | ".join(cell(key, d, kind) for d in DIRECTIONS for kind in KINDS) + " |\n"
                   for key, name in STATIONS)
    return head + rows + "\n<small>↓ southbound, ↑ northbound; averaged over the last 10 minutes.</small>"


def traffic_gotthard_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Gotthard approach", "mdi:tunnel"),
        tile(FORMING["south"], "Queue forming, southbound", 6), tile(FORMING["north"], "Queue forming, northbound", 6),
        *(tile(travel(route), name, 6) for route, name in TRAVEL.items()),
        heading("Speed before the portals", "mdi:speedometer", "subtitle"),
        dict(hist({station(k, "south", "speed"): n for k, n in STATIONS[4:8]}, "Southbound (km/h)"),
             grid_options={"columns": "full"}),
        dict(hist({station("a2_quinto", "north", "speed"): "Quinto", station("a2_goschenen", "north", "speed"): "Göschenen"},
                  "Northbound (km/h)"), grid_options={"columns": "full"}),
    ]}


def traffic_map_section() -> dict[str, Any]:
    def speed_map(direction: str) -> dict[str, Any]:
        return {"type": "map", "title": f"{DIRECTIONS[direction].capitalize()} speed", "default_zoom": 9,
                "hours_to_show": 0, "theme_mode": "auto", "grid_options": {"columns": "full", "rows": 6},
                "entities": [{"entity": station(k, direction, "speed"), "label_mode": "state"} for k, _ in STATIONS]}
    return {"type": "grid", "cards": [heading("Map", "mdi:map"), speed_map("south"), speed_map("north")]}


def traffic_table_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Every station now", "mdi:table"),
        {"type": "markdown", "content": station_table(), "grid_options": {"columns": "full"}},
        tile(AXEN_TRAFFIC, "Axenstrasse (A4) traffic", 12, vertical=False),
    ]}


def traffic_history_section() -> dict[str, Any]:
    def per_hour(entities: dict[str, str], title: str) -> dict[str, Any]:
        return {"type": "statistics-graph", "title": title, "stat_types": ["mean"], "period": "hour", "days_to_show": 7,
                "chart_type": "line", "entities": [{"entity": e, "name": n} for e, n in entities.items()],
                "grid_options": {"columns": 6}}
    return {"type": "grid", "column_span": 3, "cards": [
        heading("Per hour, last 7 days", "mdi:chart-bell-curve"),
        per_hour({station("a2_goschenen", "south", "traffic"): "Southbound",
                  station("a2_goschenen", "north", "traffic"): "Northbound"}, "Göschenen, vehicles per hour"),
        per_hour({station("a4_sisikon_axenstrasse", "south", "traffic"): "Southbound",
                  station("a4_sisikon_axenstrasse", "north", "traffic"): "Northbound"}, "Axenstrasse (A4), vehicles per hour"),
        per_hour({station("a2_goschenen", "south", "lorries"): "Southbound",
                  station("a2_goschenen", "north", "lorries"): "Northbound"}, "Göschenen, lorries per hour"),
        per_hour({travel(r): n for r, n in TRAVEL.items()}, "Travel times (min)"),
        dict(hist({station(k, "south", "traffic"): n for k, n in STATIONS[:9]}, "A2 southbound, last 24 hours (veh/h)"),
             grid_options={"columns": 12}),
    ]}


def pass_entity(slug: str, kind: str) -> str:
    return PASS_ENTITY[kind].format(slug)


def conditions_table() -> str:
    """A row per pass: the site's own words for its status (with snow chains
    and truck limits), when that last changed, the temperature and weather."""
    rows = ["| Pass | Status | Since | °C | Weather |", "|---|---|---|---|---|"]
    for slug, name in PASSES.items():
        e = {kind: pass_entity(slug, kind) for kind in PASS_ENTITY}
        rows.append(
            f"| {name} "
            f"| {{{{ state_attr('{e['status']}', 'status') or states('{e['status']}') }}}}"
            f"{{{{ ' · snow chains' if is_state('{e['chains']}', 'on') }}}}"
            f"{{{{ ' · truck limits' if is_state('{e['trucks']}', 'on') }}}} "
            f"| {{% set t = as_timestamp(states('{e['since']}'), None) %}}"
            f"{{{{ t | timestamp_custom('%d.%m. %H:%M') if t else '–' }}}} "
            f"| {{{{ states('{e['temperature']}') | float | round | int if is_number(states('{e['temperature']}')) "
            f"else '–' }}}} "
            f"| {{{{ {WEATHER!r}.get(states('{e['weather']}'), '–') }}}} |")
    return "\n".join(rows)


def notices_list() -> str:
    """Each pass's notices (night closures, weight limits, ...), one per line
    on the site; passes without any are left out."""
    template = "{% set ns = namespace(any=false) %}"
    for slug, name in PASSES.items():
        status = pass_entity(slug, "status")
        template += (f"{{% set n = state_attr('{status}', 'notes') %}}{{% if n %}}{{% set ns.any = true %}}"
                     f"**{name}**{{{{ ', ' ~ state_attr('{status}', 'route') if state_attr('{status}', 'route') }}}}\n"
                     "{% for line in n.split('\\n') %}- {{ line }}\n{% endfor %}\n{% endif %}")
    return template + "{% if not ns.any %}No notices.{% endif %}"


# How each status looks on the pass cards: (icon, Mushroom color).
# Restrictions are mostly snow on the road; a closure for the winter looks
# like any other (the second line says which).
PASS_LOOK = {"open": ("mdi:check-circle", "green"), "restricted": ("mdi:snowflake", "amber"),
             "partially_open": ("mdi:circle-half-full", "orange"), "closed": ("mdi:cancel", "red"),
             "winter_closure": ("mdi:cancel", "red")}
UNKNOWN_LOOK = ("mdi:help-circle", "grey")


def by_status(status: str, index: int) -> str:
    """The icon (0) or color (1) for a status sensor's state, as a template."""
    looks = {state: look[index] for state, look in PASS_LOOK.items()}
    return f"{{{{ {looks!r}.get(states('{status}'), '{UNKNOWN_LOOK[index]}') }}}}"


def pass_secondary(slug: str) -> str:
    """The status in words, the temperature, and since when: the time if it
    changed today, else the date."""
    status, temperature, since = (pass_entity(slug, kind) for kind in ("status", "temperature", "since"))
    return (f"{{% set t = states('{temperature}') %}}{{% set s = as_timestamp(states('{since}'), None) %}}"
            f"{{{{ state_translated('{status}') }}}}"
            "{{ ' · ' ~ (t | float | round | int) ~ ' °C' if is_number(t) }}"
            "{{ ' · since ' ~ (s | timestamp_custom('%H:%M') if s | timestamp_custom('%Y-%m-%d') == "
            "now().strftime('%Y-%m-%d') else s | timestamp_custom('%d.%m.')) if s }}")


def pass_badge(slug: str) -> str:
    """Snow chains or truck limits, as a badge on the icon."""
    chains, trucks = pass_entity(slug, "chains"), pass_entity(slug, "trucks")
    return (f"{{{{ 'mdi:link-variant' if is_state('{chains}', 'on') else "
            f"'mdi:truck-remove' if is_state('{trucks}', 'on') else '' }}}}")


def pass_card(slug: str, name: str) -> dict[str, Any]:
    """A Mushroom template card: the status's icon and color, and a second
    line with the status, temperature and since when."""
    status = pass_entity(slug, "status")
    return {"type": "custom:mushroom-template-card", "entity": status, "primary": name,
            "secondary": pass_secondary(slug), "icon": by_status(status, 0), "color": by_status(status, 1),
            "badge_icon": pass_badge(slug), "badge_color": "amber",
            "tap_action": {"action": "more-info"}, "grid_options": {"columns": 6}}


def passes_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Passes nearby", "mdi:image-filter-hdr"),
        *(pass_card(slug, name) for slug, name in PASSES.items()),
    ]}


def conditions_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Conditions", "mdi:thermometer"),
        tile(PASSES_LAST_UPDATE, "Last update from alpen-paesse.ch", 12, vertical=False),
        {"type": "markdown", "content": conditions_table(), "grid_options": {"columns": "full"}},
        {"type": "markdown", "content":
            "<small>Data: IG Alpenpässe (alpen-paesse.ch), every 30 minutes. \"Since\" is when the site "
            "last changed the pass's status.</small>",
         "grid_options": {"columns": "full"}},
    ]}


def notices_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Notices", "mdi:message-alert"),
        {"type": "markdown", "content": notices_list(), "grid_options": {"columns": "full"}},
    ]}


def passes_history_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 3, "cards": [
        heading("History", "mdi:chart-timeline-variant"),
        dict(hist({pass_entity(slug, "open"): name for slug, name in PASSES.items()},
                  "Open, last 7 days", hours=168), grid_options={"columns": 12}),
        dict(hist({pass_entity(slug, "temperature"): name for slug, name in PASSES.items()},
                  "Temperature, last 48 hours (°C)", hours=48), grid_options={"columns": 12}),
    ]}


# The Flights view: the FlightRadar24 integration
# (github.com/AlexandrErohin/home-assistant-flightradar24, HACS). Its area is
# a circle round home, set in its options; each sensor counts flights and has
# them in a `flights` attribute.
FR24 = "flightradar24"
IN_AREA = f"sensor.{FR24}_current_in_area"
ENTERED = f"sensor.{FR24}_entered_area"
EXITED = f"sensor.{FR24}_exited_area"
TRACKED = f"sensor.{FR24}_additional_tracked"
MOST_TRACKED = f"switch.{FR24}_most_tracked"  # a switch: on fetches the list, the list is its attribute
FETCHING = f"switch.{FR24}_api_data_fetching"
ADD_TRACK, REMOVE_TRACK = f"text.{FR24}_add_to_track", f"text.{FR24}_remove_from_track"
CLEAR_TRACKED = f"button.{FR24}_clear_additional_tracked"
FR24_UPDATE = f"update.{FR24}_update"
# The airport's sensors stay unavailable until an airport code is in this.
AIRPORT_TRACK = f"text.{FR24}_airport_track"
BOARDS = {"arrivals": f"sensor.{FR24}_airport_arrivals", "departures": f"sensor.{FR24}_airport_departures"}
# (direction, kind): sensor. Mind the integration's names: only some have
# "airport" in them.
AIRPORT_STATS = {
    ("arrivals", "on_time"): f"sensor.{FR24}_airport_arrivals_on_time",
    ("arrivals", "delayed"): f"sensor.{FR24}_airport_arrivals_delayed",
    ("arrivals", "canceled"): f"sensor.{FR24}_arrivals_canceled",
    ("arrivals", "delay_average"): f"sensor.{FR24}_arrivals_delay_average",
    ("arrivals", "delay_index"): f"sensor.{FR24}_arrivals_delay_index",
    ("departures", "on_time"): f"sensor.{FR24}_departures_on_time",
    ("departures", "delayed"): f"sensor.{FR24}_departures_delayed",
    ("departures", "canceled"): f"sensor.{FR24}_departures_canceled",
    ("departures", "delay_average"): f"sensor.{FR24}_departures_delay_average",
    ("departures", "delay_index"): f"sensor.{FR24}_departures_delay_index",
}
STAT_NAMES = {"on_time": "On time", "delayed": "Delayed", "canceled": "Canceled",
              "delay_average": "Average delay", "delay_index": "Delay index"}
# Every entity the integration makes, all of them on the page.
FLIGHT_ENTITIES = [IN_AREA, ENTERED, EXITED, TRACKED, MOST_TRACKED, FETCHING, ADD_TRACK, REMOVE_TRACK,
                   CLEAR_TRACKED, FR24_UPDATE, AIRPORT_TRACK, *BOARDS.values(), *AIRPORT_STATS.values()]

# FlightRadar24 gives feet and knots; here they're metres and km/h.
FLIGHT_UNITS = {"altitude": "m", "distance": "km", "ground_speed": "kmh"}


# For the two custom cards: the map card asks the sections grid for a fixed
# five rows (~300 px), but draws its map at 16:10 across the section and the
# flight list under it, so it ran over the cards below; the flight card asks
# for nothing. "auto" makes the grid follow what they actually draw.
AUTO_HEIGHT = {"columns": "full", "rows": "auto"}


def _route(origin: str, destination: str) -> str:
    """'Bern → Athens', with a ? for an end FlightRadar24 doesn't know."""
    return (f"{{{{ f.get('{origin}') or '?' }}}} → {{{{ f.get('{destination}') or '?' }}}}")


# The flights tracked outside the area: live or scheduled, with their route.
TRACKED_LIST = ("{% for f in state_attr('" + TRACKED + "', 'flights') or [] %}"
                "- **{{ f.get('flight_number') or f.get('callsign') or f.get('aircraft_registration') or '?' }}** "
                + _route("airport_origin_city", "airport_destination_city") +
                "{{ ' · ' ~ f.aircraft_model if f.get('aircraft_model') }}"
                "{{ ' · _' ~ f.tracked_type ~ '_' if f.get('tracked_type') }}\n"
                "{% else %}No flights tracked. Add one by its flight number, callsign or registration."
                "{% endfor %}")
# The ten flights most watched on FlightRadar24 worldwide.
MOST_TRACKED_TABLE = ("{% set flights = state_attr('" + MOST_TRACKED + "', 'flights') or [] %}"
                      "{% if flights %}| | Flight | Route | Aircraft | Watching |\n|--:|:--|:--|:--|--:|\n"
                      "{% for f in flights %}| {{ loop.index }} "
                      "| {{ f.get('flight_number') or f.get('callsign') or '–' }} "
                      "| " + _route("airport_origin_city", "airport_destination_city") +
                      " | {{ f.get('aircraft_model') or f.get('aircraft_code') or '–' }} "
                      "| {{ f.get('clicks') or '–' }} |\n{% endfor %}"
                      "{% else %}Not fetched: the Most tracked switch is off.{% endif %}")


def airport_board(direction: str) -> str:
    """The next flights in or out: the time, where from or to, the flight,
    and its status ("Delayed 17:02")."""
    time = "time_scheduled_arrival" if direction == "arrivals" else "time_scheduled_departure"
    place = "From" if direction == "arrivals" else "To"
    return ("{% set flights = (state_attr('" + BOARDS[direction] + "', 'flights') or [])[:15] %}"
            f"{{% if flights %}}| Time | {place} | Flight | Status |\n|:--|:--|:--|:--|\n"
            "{% for f in flights %}"
            f"| {{{{ f.{time} | timestamp_custom('%H:%M') if f.get('{time}') else '--:--' }}}} "
            "| {{ f.get('airport_city') or '–' }} | {{ f.get('flight_number') or f.get('callsign') or '–' }} "
            "| {{ f.get('status_text') or '–' }} |\n{% endfor %}"
            f"{{% else %}}No {direction}.{{% endif %}}")


def flights_now_section() -> dict[str, Any]:
    """The integration's own map card, with the flights overhead listed
    under it; it only takes the Current in area sensor."""
    return {"type": "grid", "column_span": 2, "cards": [
        heading("Overhead now", "mdi:airplane-marker"),
        tile(IN_AREA, "In the area", 4), tile(ENTERED, "Just entered", 4), tile(EXITED, "Just left", 4),
        {"type": "custom:flightradar24-card", "entity": IN_AREA, "show_header": False, "show_flights": True,
         "show_tracks": True, "map_style": "topo", "altitude_unit": "m", "distance_unit": "km",
         "speed_unit": "km/h", "grid_options": AUTO_HEIGHT},
    ]}


def flight_card_section() -> dict[str, Any]:
    """A card per flight overhead, with its photo and route; with none
    overhead, the flights tracked elsewhere."""
    return {"type": "grid", "cards": [
        heading("Flight", "mdi:airplane"),
        {"type": "custom:flightradar-flight-card", "grid_options": AUTO_HEIGHT,
         "entities": [{"entity_id": IN_AREA, "title": "Overhead"}, {"entity_id": TRACKED, "title": "Tracked"}],
         "units": FLIGHT_UNITS, "show_distance": "closest", "show_country_flags": "emoji",
         "carousel": {"enable": True, "show_controls": True, "loop": True}},
    ]}


def tracked_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Tracked flights", "mdi:airplane-search"),
        tile(TRACKED, "Tracked", 12, vertical=False),
        {"type": "markdown", "content": TRACKED_LIST, "grid_options": {"columns": "full"}},
        {"type": "entities", "grid_options": {"columns": "full"}, "entities": [
            {"entity": ADD_TRACK, "name": "Track a flight"},
            {"entity": REMOVE_TRACK, "name": "Stop tracking"},
            {"entity": CLEAR_TRACKED, "name": "Stop tracking all"},
        ]},
    ]}


def most_tracked_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Most watched worldwide", "mdi:fire"),
        {"type": "markdown", "content": MOST_TRACKED_TABLE, "grid_options": {"columns": "full"}},
        tile(MOST_TRACKED, "Fetch the most watched", 12, vertical=False),
    ]}


def airport_section() -> dict[str, Any]:
    """The airport typed in above: its boards and today's punctuality. Until
    one is, the sensors are unavailable and only a hint shows."""
    tracking = {"condition": "state", "entity": BOARDS["arrivals"], "state_not": "unavailable"}
    cards: list[dict[str, Any]] = [
        heading("Airport", "mdi:airport"),
        {"type": "entities", "grid_options": {"columns": "full"},
         "entities": [{"entity": AIRPORT_TRACK, "name": "Airport (IATA or ICAO, e.g. ZRH)"}]},
        {"type": "markdown", "grid_options": {"columns": "full"},
         "visibility": [{"condition": "state", "entity": BOARDS["arrivals"], "state": "unavailable"}],
         "content": "<small>Type an airport's code above for its arrivals, departures and delays today; "
                    "empty it to stop.</small>"},
    ]
    for direction in BOARDS:
        cards += [dict(heading(direction.capitalize(), f"mdi:airplane-{'landing' if direction == 'arrivals' else 'takeoff'}",
                               "subtitle"), visibility=[tracking]),
                  *(dict(tile(AIRPORT_STATS[(direction, kind)], name, 4), visibility=[tracking])
                    for kind, name in STAT_NAMES.items() if kind != "delay_index"),
                  dict(tile(AIRPORT_STATS[(direction, "delay_index")], STAT_NAMES["delay_index"], 6),
                       visibility=[tracking]),
                  dict(tile(BOARDS[direction], f"Next {direction}", 6), visibility=[tracking]),
                  {"type": "markdown", "content": airport_board(direction), "visibility": [tracking],
                   "grid_options": {"columns": "full"}}]
    return {"type": "grid", "cards": cards}


def flights_history_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 3, "cards": [
        heading("History", "mdi:chart-timeline-variant"),
        dict(hist({IN_AREA: "In the area"}, "Flights overhead, last 24 hours"), grid_options={"columns": 12}),
        tile(FETCHING, "Fetching from FlightRadar24", 6, vertical=False),
        tile(FR24_UPDATE, "FlightRadar24 integration", 6, vertical=False),
        {"type": "markdown", "grid_options": {"columns": "full"}, "content":
            "<small>Data: FlightRadar24, through the FlightRadar24 integration. After a restart the area "
            "can show too few flights for a few minutes. Turning off fetching stops every call to "
            "FlightRadar24, the map included.</small>"},
    ]}


def build() -> dict[str, Any]:
    return {"views": [
        {"title": "Gotthard", "path": "gotthard", "icon": "mdi:tunnel", "type": "sections", "max_columns": 3,
         "sections": [now_section(), webcam_section(), messages_section(), history_section()]},
        {"title": "Roads", "path": "roads", "icon": "mdi:highway", "type": "sections", "max_columns": 3,
         "sections": [calendar_section(), axenstrasse_section(), road_section("A2"), road_section("A4"), roads_history_section()]},
        {"title": "Passes", "path": "passes", "icon": "mdi:image-filter-hdr", "type": "sections", "max_columns": 3,
         "sections": [passes_section(), conditions_section(), notices_section(), passes_history_section()]},
        {"title": "Traffic", "path": "traffic", "icon": "mdi:car-multiple", "type": "sections", "max_columns": 3,
         "sections": [traffic_gotthard_section(), traffic_map_section(), traffic_table_section(),
                      traffic_history_section()]},
        {"title": "Flights", "path": "flights", "icon": "mdi:airplane", "type": "sections", "max_columns": 3,
         "sections": [flights_now_section(), flight_card_section(), tracked_section(), most_tracked_section(),
                      airport_section(), flights_history_section()]},
    ]}

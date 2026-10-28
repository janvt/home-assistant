"""The Infrastructure dashboard (`dashboard-infrastructure`): the roads and
tunnels around us. The Gotthard view has the road tunnel; the Roads view the
Axenstrasse and the closures of the A2 and A4, each way.

`build()` returns the whole config, owned by the script like the Trains one: a
card added in the UI is gone after the next sync.

Everything on the Gotthard view comes from the Gotthard integration
(github.com/janvt/homeassistant-gotthard): FEDRO's traffic messages for the
tunnel's queues, closures and messages, and the two portal webcams. The north
portal's queue is southbound before Göschenen, the south portal's northbound
before Airolo.
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
# Every entity the integration makes, all of them on the page.
ENTITIES = [TUNNEL, *QUEUE.values(), *DELAY.values(), CLOSURE, MESSAGES, *WEBCAM.values(), UPDATE,
            AXENSTRASSE, AXEN_CLOSURE, *(sensor for directions in ROADS.values() for sensor, _ in directions)]

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


def closure_list(entity: str, attribute: str, empty: str, limit: int = 10) -> str:
    """A closures attribute as a list: when, then the message without its
    "Freigegeben:" (and, for a road's, the road and direction it repeats)."""
    return ("{% for c in (state_attr('" + entity + "', '" + attribute + "') or [])[:" + str(limit) + "] %}"
            "- **{{ as_timestamp(c.start) | timestamp_custom('%a %d.%m. %H:%M') if c.start else 'now' }}"
            "{{ ' to ' ~ as_timestamp(c.end or c.until) | timestamp_custom('%d.%m. %H:%M') if c.end or c.until }}**: "
            "{{ c.text | regex_replace('^\\\\w+: ', '') }}\n"
            "{% else %}" + empty + "{% endfor %}")


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
             tile(CLOSURE, "Next closure", 4), tile(AXENSTRASSE, "Axenstrasse", 4)]
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


def axenstrasse_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Axenstrasse", "mdi:road-variant"),
        tile(AXENSTRASSE, "Axenstrasse"), tile(AXEN_CLOSURE, "Next closure"),
        heading("Closed now", "mdi:road-variant", "subtitle"),
        {"type": "markdown", "content": closure_list(AXENSTRASSE, "closures", "Open."),
         "grid_options": {"columns": "full"}},
        heading("Closures announced", "mdi:calendar-alert", "subtitle"),
        {"type": "markdown", "content": closure_list(AXEN_CLOSURE, "closures", "None announced."),
         "grid_options": {"columns": "full"}},
    ]}


def road_section(road: str) -> dict[str, Any]:
    cards: list[dict[str, Any]] = [heading(f"{road} closures", "mdi:highway")]
    for sensor, direction in ROADS[road]:
        cards += [heading(direction.capitalize(), "mdi:arrow-decision", "subtitle"),
                  tile(sensor, "Closed now", 12, vertical=False),
                  {"type": "markdown", "grid_options": {"columns": "full"}, "content":
                      closure_list(sensor, "current", "") + closure_list(sensor, "planned", "Nothing announced.", 5)}]
    return {"type": "grid", "cards": cards}


def roads_history_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 3, "cards": [
        heading("History", "mdi:chart-timeline-variant"),
        dict(hist({AXENSTRASSE: "Axenstrasse", TUNNEL: "Gotthard tunnel"}, "Open, last 7 days", hours=168),
             grid_options={"columns": 12}),
    ]}


def build() -> dict[str, Any]:
    return {"views": [
        {"title": "Gotthard", "path": "gotthard", "icon": "mdi:tunnel", "type": "sections", "max_columns": 3,
         "sections": [now_section(), webcam_section(), messages_section(), history_section()]},
        {"title": "Roads", "path": "roads", "icon": "mdi:highway", "type": "sections", "max_columns": 3,
         "sections": [axenstrasse_section(), road_section("A2"), road_section("A4"), roads_history_section()]},
    ]}

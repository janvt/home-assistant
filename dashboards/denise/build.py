"""Denise's dashboard (`dashboard-denise`): her default, set in her profile.

Denise lives in Altdorf too, not here, and isn't into the technical side, so
the page says things in plain German sentences instead of sensors and graphs,
and has no controls for any room:

- a greeting with the weather and the Axenstrasse in two lines, and under it
  her own set of alert pills (`PILLS`, keys from `mobile-alerts/pills.py`) as
  icons that open the Hinweise sub-page;
- the forecast for Altdorf, today and the next hours;
- Föhn: blowing, coming or not, in one sentence, with wind and gusts;
- the Axenstrasse: open or closed, how the traffic is moving, and the
  closures announced.

The pills are the same `binary_sensor.pill_<key>` the integration makes for
the Mobile dashboard, so a pill switched off there (Choose alerts) is gone
here too. Dismissing is shared as well, so her cards have no hold action, and
a pill Jan dismissed still shows for her. Their names and lines are German
here (`DE`), pills.py stays English. Her row has one chip per pill instead of
the Mobile row's slots: with a short list, few are on at once.

The weather forecast cards follow her profile's language: set it to Deutsch.
`build()` returns the whole config, owned by the script like the other
dashboards: a card added in the UI is gone after the next sync.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"{name.replace('-', '_')}_build", HERE.parent / name / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


weather = _load("weather")
roads = _load("infrastructure")
alerts = _load("mobile-alerts")

DASHBOARD = "dashboard-denise"
TITLE = "Denise"
ICON = "mdi:cat"
VIEW = "home"
SUBVIEW = "hinweise"
NAV = {"action": "navigate", "navigation_path": f"/{DASHBOARD}/{SUBVIEW}"}
# Full screen: kiosk-mode (HACS) hides the header and the sidebar. Her
# Hinweise page has its own back chip, so nothing needs the header. To edit
# the page in the UI, open it with ?disable_km on the URL.
KIOSK = {"hide_header": True, "hide_sidebar": True}

ALTDORF = next(loc for loc in weather.LOCATIONS if loc["path"] == "altdorf")
W = ALTDORF["weather"]
S = weather.slug(ALTDORF)
TEMP_HIGH = f"sensor.{S}_highest_temperature_today"
TEMP_LOW = f"sensor.{S}_lowest_temperature_today"
RAIN_TODAY = f"sensor.{S}_precipitation_today"
WARNINGS = f"sensor.{S}_weather_warning_next_24_hours"
FOEHN = weather.sensor(ALTDORF, "fohn")
FOEHN_OUTLOOK = f"sensor.{S}_fohn_outlook"
WIND = weather.sensor(ALTDORF, "wind_speed")
GUSTS = weather.sensor(ALTDORF, "wind_speed_max")
AXEN = roads.AXENSTRASSE
AXEN_NEXT = roads.AXEN_CLOSURE
AXEN_CALENDAR = "calendar.national_roads_axenstrasse"
AXEN_STATION = "a4_sisikon_axenstrasse"
TO_ALTDORF = roads.station(AXEN_STATION, "south", "traffic")
TO_BRUNNEN = roads.station(AXEN_STATION, "north", "traffic")
SPEEDS = [roads.station(AXEN_STATION, d, "speed") for d in ("south", "north")]

WEEKDAYS = "['Mo','Di','Mi','Do','Fr','Sa','So']"
CONDITIONS = {"clear-night": "Klare Nacht", "cloudy": "Bewölkt", "exceptional": "Ungewöhnliches Wetter",
              "fog": "Nebel", "hail": "Hagel", "lightning": "Gewitter", "lightning-rainy": "Gewitter mit Regen",
              "partlycloudy": "Teils bewölkt", "pouring": "Starker Regen", "rainy": "Regen", "snowy": "Schnee",
              "snowy-rainy": "Schneeregen", "sunny": "Sonnig", "windy": "Windig", "windy-variant": "Windig und bewölkt"}


def _n(entity: str, digits: int = 0) -> str:
    """A sensor's number, rounded; whole numbers without the ".0"."""
    if digits:
        return f"states('{entity}')|float(0)|round({digits})"
    return f"states('{entity}')|float(0)|round(0)|int"


def _closed_until(entity: str) -> str:
    return ("{% set c = state_attr('" + entity + "','closures') or [] %}"
            "{{ ('Gesperrt bis ' ~ (as_timestamp(c[0].get('until')) | timestamp_custom('%H:%M'))) "
            "if c and c[0].get('until') else 'Gesperrt' }}")


POLLEN = ("{% set names = {'alder': 'Erle', 'ash': 'Esche', 'beech': 'Buche', 'birch': 'Birke', 'grasses': 'Gräser', "
          "'hazel': 'Hasel', 'oak': 'Eiche'} %}"
          "{% set ns = namespace(hi=[]) %}{% for k, lim in {'alder': 70, 'ash': 100, 'beech': 70, 'birch': 70, "
          "'grasses': 50, 'hazel': 70, 'oak': 70}.items() %}"
          "{% if states('sensor.luzern_pollen_' ~ k)|float(0) >= lim %}{% set ns.hi = ns.hi + [names[k]] %}{% endif %}"
          "{% endfor %}Stark: {{ ns.hi | join(', ') }}")

# Her pills, in German: key → (name, line under it). They show in pills.py's
# order. Nothing about this flat (doors, fridge, servers, the VPN).
DE: dict[str, tuple[str, str]] = {
    "weather_warning": ("Wetterwarnung",
                        "{% for w in state_attr('" + WARNINGS + "','warnings') or [] %}{{ ' · ' if not loop.first }}"
                        "{{ w.event }} ({{ {'yellow': 'gelb', 'orange': 'orange', 'red': 'rot'}.get(w.level, w.level) }})"
                        "{% endfor %}"),
    "hail": ("Hagel", "{{ " + _n("sensor.altdorf_ur_radar_hail_probability") + " }} % Hagelrisiko in Altdorf"),
    "downpour": ("Starkregen", "{{ " + _n("sensor.altdorf_ur_radar_rain_last_hour", 1) + " }} mm Regen in der letzten Stunde"),
    "lightning_nearby": ("Gewitter in der Nähe",
                         "Letzter Blitz {{ " + _n("sensor.altdorf_lightning_distance") + " }} km von Altdorf"),
    "raining_now": ("Es regnet", "{{ " + _n("sensor.altdorf_ur_radar_rain_rate", 1) + " }} mm pro Stunde in Altdorf"),
    "ground_frost": ("Bodenfrost", "{{ " + _n("sensor.altdorf_temperature_5_cm_above_ground", 1)
                     + " }} °C am Boden: Vorsicht, es kann glatt sein"),
    "snow_in_altdorf": ("Schnee in Altdorf", "{{ " + _n("sensor.altdorf_snow_depth") + " }} cm Schnee liegen"),
    "schachen_spate": ("Der Schächen führt Hochwasser",
                       "{{ " + _n("sensor.schachen_burglen_discharge", 1) + " }} m³/s bei Bürglen"),
    "lake_high": ("Hoher Seestand", "Vierwaldstättersee {{ ((states('sensor.vierwaldstattersee_brunnen_level')|float(0) "
                                    "- 433.57) * 100)|round(0)|int }} cm über dem Mittel"),
    "gotthard_tunnel_closed": ("Gotthardtunnel gesperrt", _closed_until("binary_sensor.gotthard_tunnel")),
    "axenstrasse_closed": ("Axenstrasse gesperrt", _closed_until(AXEN)),
    "gotthard_jam": ("Stau am Gotthard",
                     "Richtung Süden {{ " + _n("sensor.gotthard_delay_before_the_north_portal")
                     + " }} Min., Richtung Norden {{ " + _n("sensor.gotthard_delay_before_the_south_portal")
                     + " }} Min. Wartezeit"),
    "rain_next_hour": ("Bald Regen", "{{ " + _n("sensor.altdorf_ur_chance_of_rain_next_hour")
                       + " }} % Regenwahrscheinlichkeit in der nächsten Stunde"),
    "frost_tonight": ("Frost heute Nacht", "Bis {{ " + _n("sensor.altdorf_ur_lowest_temperature_tonight", 1) + " }} °C"),
    "snow_coming": ("Schnee erwartet", "{{ " + _n("sensor.altdorf_ur_snow_next_24_hours", 1)
                    + " }} mm in Altdorf in den nächsten 24 Stunden"),
    "fohn_altdorf": ("Föhn in Altdorf", "Böen bis {{ " + _n(GUSTS) + " }} km/h"),
    "fohn_coming": ("Föhn im Anzug", "{{ 'Starker Föhn' if is_state('" + FOEHN_OUTLOOK + "','strong_south') "
                                     "else 'Föhn' }} in den nächsten Stunden wahrscheinlich"),
    "sun_above_the_fog": ("Sonne über dem Nebel", "Altdorf liegt im Grau, in Andermatt scheint die Sonne"),
    "pollen_high": ("Viel Pollen", POLLEN),
    "holiday_tomorrow": ("Morgen ist Feiertag", "{{ state_attr('calendar.holidays_in_switzerland','message') }}"),
    "record_warm": ("Rekordwarm", "{{ state_attr('sensor.altdorf_high_vs_normal','high') }} °C heute, bisheriger "
                                  "Rekord für das Datum {{ states('sensor.altdorf_record_high_for_the_date') }} °C"),
    "record_cold": ("Rekordkalt", "{{ state_attr('sensor.altdorf_low_vs_normal','low') }} °C heute, bisheriger "
                                  "Rekord für das Datum {{ state_attr('sensor.altdorf_record_high_for_the_date',"
                                  "'record_low') }} °C"),
}
PILLS = set(DE)


def pills() -> list[dict[str, Any]]:
    return [p for p in alerts.ALERTS if p["key"] in PILLS]


def _on(pill: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"condition": "state", "entity": alerts.entity(pill), "state": "on"}]


def _quiet() -> dict[str, Any]:
    return {"type": "markdown", "text_only": True, "content": "<center><small>Keine Hinweise: alles ruhig.</small></center>",
            "visibility": [{"condition": "state", "entity": alerts.entity(p), "state_not": "on"} for p in pills()]}


def _md(content: str, **extra: Any) -> dict[str, Any]:
    return {"type": "markdown", "content": content, **extra}


def _heading(text: str, icon: str) -> dict[str, Any]:
    return {"type": "heading", "heading": text, "heading_style": "title", "icon": icon}


# ── the greeting ────────────────────────────────────────────────────────────
GREETING = (
    "{% set h = now().hour %}"
    "## {{ 'Guten Morgen' if h < 11 else ('Guten Tag' if h < 18 else 'Guten Abend') }}, Denise\n"
    "{% set c = " + repr(CONDITIONS) + ".get(states('" + W + "')) %}"
    "{{ c ~ ', ' if c }}{{ state_attr('" + W + "','temperature')|float(0)|round(0)|int }} °C in Altdorf. "
    "Heute {{ " + _n(TEMP_LOW) + " }} bis {{ " + _n(TEMP_HIGH) + " }} °C"
    "{{ ', ' ~ (" + _n(RAIN_TODAY, 1) + ") ~ ' mm Regen' if " + _n(RAIN_TODAY, 1) + " > 0 }}.<br>"
    "Die Axenstrasse ist {{ '**offen**' if is_state('" + AXEN + "','on') else '**gesperrt**' }}."
)


def chips_card() -> dict[str, Any]:
    """One chip per pill, shown while it's on; tapping opens Hinweise."""
    def chip(p: dict[str, Any]) -> dict[str, Any]:
        e = alerts.entity(p)
        return {"type": "conditional", "conditions": _on(p),
                "chip": {"type": "template", "icon": p["icon"], "icon_color": "{{ state_attr('" + e + "', 'color') }}",
                         "content": DE[p["key"]][0], "tap_action": NAV}}
    return {"type": "custom:mushroom-chips-card", "alignment": "center", "chips": [chip(p) for p in pills()]}


def greeting_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 2, "cards": [_md(GREETING), chips_card(), _quiet()]}


# ── the weather ─────────────────────────────────────────────────────────────
WARNING = ("{% for w in state_attr('" + WARNINGS + "','warnings') or [] %}"
           "{% set on = w.onset|as_datetime|as_local %}{% set off = w.expires|as_datetime|as_local %}"
           "{% set wd = " + WEEKDAYS + " %}"
           "<ha-alert alert-type=\"{{ 'error' if w.level == 'red' else 'warning' }}\" title=\"{{ w.event }}\">"
           "{{ ('bis ' ~ wd[off.weekday()] ~ ' ' ~ off.strftime('%H:%M')) if on <= now() else "
           "('von ' ~ wd[on.weekday()] ~ ' ' ~ on.strftime('%H:%M') ~ ' bis ' ~ wd[off.weekday()] ~ ' ' "
           "~ off.strftime('%H:%M')) }}</ha-alert>{% endfor %}")


def weather_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        _heading("Wetter in Altdorf", "mdi:weather-partly-cloudy"),
        _md(WARNING, visibility=[{"condition": "state", "entity": WARNINGS, "state": ["yellow", "orange", "red"]}]),
        {"type": "weather-forecast", "entity": W, "forecast_type": "daily", "show_current": True,
         "show_forecast": True},
        {"type": "weather-forecast", "entity": W, "forecast_type": "hourly", "show_current": False,
         "show_forecast": True},
    ]}


# ── Föhn ────────────────────────────────────────────────────────────────────
FOEHN_TEXT = (
    "{% set f = states('" + FOEHN + "') %}{% set o = states('" + FOEHN_OUTLOOK + "') %}"
    "{% set g = " + _n(GUSTS) + " %}"
    "{% if f == 'foehn' %}<ha-alert alert-type=\"warning\" title=\"Der Föhn bläst\">Böen bis {{ g }} km/h.</ha-alert>"
    "{% elif f == 'mixed' %}<ha-alert alert-type=\"info\" title=\"Ein wenig Föhn\">Böen bis {{ g }} km/h.</ha-alert>"
    "{% elif o == 'strong_south' %}<ha-alert alert-type=\"warning\" title=\"Starker Föhn im Anzug\">"
    "In den nächsten Stunden wird es stürmisch.</ha-alert>"
    "{% elif o == 'south' %}<ha-alert alert-type=\"info\" title=\"Föhn im Anzug\">"
    "In den nächsten Stunden wird es windig.</ha-alert>"
    "{% else %}<ha-alert alert-type=\"success\" title=\"Kein Föhn\">Und vorerst auch keiner in Sicht.</ha-alert>"
    "{% endif %}"
)


def foehn_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        _heading("Föhn", "mdi:weather-windy"),
        _md(FOEHN_TEXT),
        weather.tile(WIND, "Wind", grid_options={"columns": 6}),
        weather.tile(GUSTS, "Böen", grid_options={"columns": 6}),
        _md("<small>Föhn ist der warme, trockene und böige Südwind im Reusstal.</small>", text_only=True),
    ]}


# ── the Axenstrasse ─────────────────────────────────────────────────────────
AXEN_STATUS = (
    "{% if is_state('" + AXEN + "','on') %}"
    "<ha-alert alert-type=\"success\" title=\"Offen\">Die Axenstrasse ist befahrbar.</ha-alert>"
    "{% else %}{% set c = state_attr('" + AXEN + "','closures') or [] %}"
    "{% set until = state_attr('" + AXEN_CALENDAR + "','end_time') if is_state('" + AXEN_CALENDAR + "','on') "
    "else (c[0].get('until') if c else none) %}"
    "<ha-alert alert-type=\"error\" title=\"Gesperrt\">"
    "{{ ('Voraussichtlich bis ' ~ (as_timestamp(until)|timestamp_custom('%H:%M')) ~ ' Uhr.') if until "
    "else 'Die Axenstrasse ist zurzeit gesperrt.' }}</ha-alert>{% endif %}"
)
AXEN_TRAFFIC = (
    "{% set a = states('" + TO_ALTDORF + "') %}{% set b = states('" + TO_BRUNNEN + "') %}"
    "{% set v = [" + ", ".join(f"states('{s}')|float(0)" for s in SPEEDS) + "] | select('gt', 0) | list %}"
    "{% if a|is_number and b|is_number %}"
    "**Verkehr jetzt:** {{ 'läuft flüssig' if not v or v|min >= 40 else ('zähflüssig' if v|min >= 20 else 'Stau') }}"
    "<br><small>Rund {{ a|float|round(-1)|int }} Fahrzeuge pro Stunde Richtung Altdorf, "
    "{{ b|float|round(-1)|int }} Richtung Brunnen.</small>{% endif %}"
)
# The closures announced, from the next-closure sensor: its own times, and
# FEDRO's "Sachlage" (what's closed and why) in their German.
AXEN_CLOSURES = (
    "**Angekündigte Sperrungen**\n\n"
    "{% set wd = " + WEEKDAYS + " %}"
    "{% for c in (state_attr('" + AXEN_NEXT + "','closures') or [])[:5] %}"
    "{% set s = c.start|as_datetime|as_local %}{% set e = c.end|as_datetime|as_local if c.end else none %}"
    "{% set m = c.text | regex_findall('Sachlage: (.*?)(?: Dauer:| Empfehlung:|$)') %}"
    "- {{ wd[s.weekday()] }} {{ s.strftime('%d.%m.') }}, {{ s.strftime('%H:%M') }}"
    "{% if e %} bis {{ (wd[e.weekday()] ~ ' ') if e.date() != s.date() }}{{ e.strftime('%H:%M') }}{% endif %} Uhr"
    "{{ '<br><small>' ~ m[0] ~ '</small>' if m }}\n"
    "{% else %}Keine Sperrungen angekündigt.{% endfor %}"
)


def axenstrasse_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        _heading("Axenstrasse", "mdi:road-variant"),
        _md(AXEN_STATUS), _md(AXEN_TRAFFIC), _md(AXEN_CLOSURES),
    ]}


# ── Hinweise ────────────────────────────────────────────────────────────────
def _card(p: dict[str, Any]) -> dict[str, Any]:
    e = alerts.entity(p)
    name, line = DE[p["key"]]
    return {"type": "custom:mushroom-template-card", "entity": e, "primary": name, "secondary": line,
            "icon": p["icon"], "icon_color": "{{ state_attr('" + e + "', 'color') }}", "multiline_secondary": True,
            "fill_container": True, "grid_options": {"columns": 12}, "tap_action": {"action": "none"},
            "visibility": _on(p)}


def subview() -> dict[str, Any]:
    back = {"type": "custom:mushroom-chips-card", "chips": [{"type": "back"}]}
    return {"title": "Hinweise", "path": SUBVIEW, "icon": "mdi:bell-ring-outline", "type": "sections",
            "max_columns": 2, "subview": True, "back_path": f"/{DASHBOARD}/{VIEW}", "sections": [
                {"type": "grid", "column_span": 2, "cards": [
                    back, _heading("Hinweise", "mdi:bell-ring-outline"), _quiet(), *map(_card, pills())]}]}


def build() -> dict[str, Any]:
    return {"kiosk_mode": KIOSK, "views": [
        {"title": TITLE, "path": VIEW, "icon": ICON, "type": "sections", "max_columns": 2,
         "sections": [greeting_section(), weather_section(), foehn_section(), axenstrasse_section()]},
        subview()]}

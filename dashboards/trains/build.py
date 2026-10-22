"""The Trains debug dashboard (`dashboard-trains`): is Frigate seeing the trains?

`build()` returns the whole dashboard config, owned by the script like the
Weather one: a card added in the UI is gone after the next sync.

Two Frigate cameras look at the same lens. `train_track` is a full-resolution
crop of the track from the main stream and does the detecting; its `track_hd`
zone is the part a train has to cross. `train_slice` is the wide view on the
sub stream and keeps the recordings and the microphone. In the sub stream a
train is too small for the model, so its own detection finds nothing.

`train_tele` is an iPhone telephoto (Blackmagic Camera, via MediaMTX) that
detects trains too, with no zone yet. Both counts run side by side for now,
to see which camera gets them right; the pill stays on the Reolink one.

The page shows the picture Frigate detects on and the one it draws its boxes
on, whether it thinks a train is there right now, the knobs that decide that,
how hard the box is working, and the last 24 hours of it.
"""
from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

_tt = runpy.run_path(str(Path(__file__).resolve().parent / "timetable.py"))

DASHBOARD = "dashboard-trains"
TITLE = "Trains"
ICON = "mdi:train"
CAMERA = "train_track"      # detects
WIDE = "train_slice"        # records, listens
TELE = "train_tele"         # iPhone telephoto, detects too
ZONE = "track_hd"
FRIGATE = "http://10.69.42.175:5000"
# The train count, made by the Mobile alert pills' sync (mobile-alerts/pills.py):
# "passing" is the zone sensor held on for 30 s, the counts keep statistics.
PASSING = "binary_sensor.train_passing"
TODAY = "sensor.trains_today"
THIS_HOUR = "sensor.trains_this_hour"
TELE_PASSING = "binary_sensor.train_passing_tele"
TELE_TODAY = "sensor.trains_today_tele"
TELE_THIS_HOUR = "sensor.trains_this_hour_tele"
# Frigate's own debug picture: object boxes, the zone and motion boxes drawn
# in. HA doesn't proxy it, so it only loads on the LAN over http.
DEBUG_IMAGE = (f"{FRIGATE}/api/{CAMERA}/latest.jpg"
               "?bbox=1&zones=1&mask=1&motion=1&regions=1&timestamp=1&h=480")

# Diagnostic entities the Frigate integration ships disabled. sync.py turns on
# the ones listed here, since the page is pointless without them.
DISABLED_BY_DEFAULT = [
    f"sensor.{CAMERA}_camera_fps", f"sensor.{CAMERA}_detection_fps", f"sensor.{CAMERA}_process_fps",
    f"sensor.{CAMERA}_skipped_fps", f"sensor.{CAMERA}_expected_fps",
    f"sensor.{CAMERA}_ffmpeg_cpu_usage", f"sensor.{CAMERA}_capture_cpu_usage", f"sensor.{CAMERA}_detect_cpu_usage",
    "sensor.frigate_ov_inference_speed", "sensor.frigate_core_i3_n300_igpu_gpu_load",
    "sensor.frigate_status", "sensor.frigate_uptime",
    f"number.{CAMERA}_threshold", f"number.{CAMERA}_contour_area", f"switch.{CAMERA}_improve_contrast",
    f"sensor.{TELE}_camera_fps", f"sensor.{TELE}_detection_fps", f"sensor.{TELE}_skipped_fps",
]


def cam(kind: str, camera: str = CAMERA) -> str:
    """`binary_sensor.train_track_motion` from ("binary_sensor", "motion")."""
    domain, _, key = kind.partition(".")
    return f"{domain}.{camera}_{key}"


def wide(kind: str) -> str:
    return cam(kind, WIDE)


def tele(kind: str) -> str:
    return cam(kind, TELE)


def zone(kind: str) -> str:
    domain, _, key = kind.partition(".")
    return f"{domain}.{ZONE}_{key}"


# ── card helpers ────────────────────────────────────────────────────────────
def heading(text: str, icon: str, style: str = "title") -> dict[str, Any]:
    return {"type": "heading", "heading": text, "heading_style": style, "icon": icon}


def tile(entity: str, name: str, **extra: Any) -> dict[str, Any]:
    card = {"type": "tile", "entity": entity, "name": name, "vertical": True}
    card.update(extra)
    return card


def toggle(entity: str, name: str) -> dict[str, Any]:
    return tile(entity, name, features=[{"type": "toggle"}], features_position="inline", vertical=False,
                grid_options={"columns": 6})


def slider(entity: str, name: str) -> dict[str, Any]:
    return tile(entity, name, features=[{"type": "numeric-input", "style": "buttons"}], vertical=False,
                grid_options={"columns": 6, "rows": 2})


def hist(entities: list[str], title: str, hours: int = 24, **extra: Any) -> dict[str, Any]:
    card = {"type": "history-graph", "title": title, "hours_to_show": hours,
            "entities": [{"entity": e} for e in entities]}
    card.update(extra)
    return card


def full(card: dict[str, Any]) -> dict[str, Any]:
    return dict(card, grid_options={"columns": "full"})


# ── sections ────────────────────────────────────────────────────────────────
def camera_card(view: str, **extra: Any) -> dict[str, Any]:
    """The advanced camera card on all three cameras, opening on `view` (live,
    timeline …). The crop comes first; the wide view and the iPhone record."""
    card = {"type": "custom:advanced-camera-card",
            "cameras": [{"camera_entity": f"camera.{c}", "frigate": {"url": FRIGATE}} for c in (CAMERA, TELE, WIDE)],
            "view": {"default": view}, "grid_options": {"columns": "full"}}
    card.update(extra)
    return card


def picture_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 2, "cards": [
        heading("What Frigate sees", "mdi:cctv"),
        camera_card("live"),
        heading("Debug overlay (LAN only)", "mdi:vector-square", "subtitle"),
        {"type": "custom:advanced-camera-card",
         "cameras": [{"camera_entity": f"camera.{CAMERA}", "id": "debug", "title": "Debug overlay",
                      "live_provider": "image", "image": {"mode": "url", "url": DEBUG_IMAGE, "refresh_seconds": 1}}],
         "menu": {"style": "none"}, "grid_options": {"columns": "full"}},
        {"type": "markdown", "content":
            "The full-resolution crop Frigate detects on. The outlined area is the **track_hd** zone a "
            "train has to cross. Red boxes: motion. Green: the regions sent to the detector. "
            "Labelled boxes: tracked objects with their score. Comes straight from Frigate, so it "
            "stays blank on ha.janvt.dev.",
         "grid_options": {"columns": "full"}},
    ]}


def now_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Right now", "mdi:train-variant"),
        tile(zone("binary_sensor.train_occupancy"), "Train on the track", grid_options={"columns": 6}),
        tile(cam("binary_sensor.train_occupancy"), "Train in frame", grid_options={"columns": 6}),
        tile(cam("binary_sensor.motion"), "Motion", grid_options={"columns": 4}),
        tile(wide("binary_sensor.train_sound"), "Train sound", grid_options={"columns": 4}),
        tile(cam("sensor.review_status"), "Review", grid_options={"columns": 4}),
        tile(zone("sensor.train_active_count"), "Moving on track", grid_options={"columns": 4}),
        tile(zone("sensor.train_count"), "On track", grid_options={"columns": 4}),
        tile(cam("sensor.train_count"), "In frame", grid_options={"columns": 4}),
        tile(wide("sensor.sound_level"), "Sound level", grid_options={"columns": 12}),
        tile(tele("binary_sensor.train_occupancy"), "iPhone: train in frame", grid_options={"columns": 6}),
        tile(tele("binary_sensor.motion"), "iPhone: motion", grid_options={"columns": 6}),
        heading("Last train", "mdi:image", "subtitle"),
        {"type": "picture-entity", "entity": f"image.{CAMERA}_train", "name": "Reolink", "show_state": False,
         "grid_options": {"columns": 6}},
        {"type": "picture-entity", "entity": f"image.{TELE}_train", "name": "iPhone", "show_state": False,
         "grid_options": {"columns": 6}},
    ]}


def settings_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Settings", "mdi:tune-variant"),
        toggle(cam("switch.detect"), "Detect"),
        toggle(cam("switch.motion"), "Motion"),
        toggle(cam("switch.improve_contrast"), "Contrast boost"),
        toggle(cam("switch.snapshots"), "Snapshots"),
        toggle(cam("switch.review_alerts"), "Alerts"),
        toggle(cam("switch.review_detections"), "Detections"),
        toggle(wide("switch.audio_detection"), "Audio (wide)"),
        toggle(wide("switch.recordings"), "Record (wide)"),
        slider(cam("number.threshold"), "Motion threshold"),
        slider(cam("number.contour_area"), "Contour area"),
        slider(_tt["TRAVEL_SOUTH"], "Through, Arth-Goldau → Altdorf"),
        slider(_tt["TRAVEL_NORTH"], "Through, Bellinzona → Altdorf"),
        slider(_tt["WINDOW"], "Match window ±"),
        {"type": "markdown", "content":
            "Changes here last until Frigate restarts: the config file wins after that. "
            "Lower the **motion threshold** or **contour area** if a train goes by without a red box. "
            "A train on **track_hd** is an alert. Audio and recordings run on the wide camera.",
         "grid_options": {"columns": "full"}},
    ]}


def health_section() -> dict[str, Any]:
    return {"type": "grid", "cards": [
        heading("Frigate", "mdi:heart-pulse"),
        tile("sensor.frigate_status", "Status", grid_options={"columns": 6}),
        tile("sensor.frigate_uptime", "Uptime", grid_options={"columns": 6}),
        tile(cam("sensor.camera_fps"), "Camera fps", grid_options={"columns": 4}),
        tile(cam("sensor.expected_fps"), "Expected", grid_options={"columns": 4}),
        tile(cam("sensor.skipped_fps"), "Skipped", grid_options={"columns": 4}),
        tile(cam("sensor.process_fps"), "Processed fps", grid_options={"columns": 6}),
        tile(cam("sensor.detection_fps"), "Detections/s", grid_options={"columns": 6}),
        tile("sensor.frigate_ov_inference_speed", "Inference", grid_options={"columns": 6}),
        tile("sensor.frigate_core_i3_n300_igpu_gpu_load", "GPU", grid_options={"columns": 6}),
        tile(tele("sensor.camera_fps"), "iPhone fps", grid_options={"columns": 4}),
        tile(tele("sensor.detection_fps"), "iPhone det/s", grid_options={"columns": 4}),
        tile(tele("sensor.skipped_fps"), "iPhone skipped", grid_options={"columns": 4}),
        tile(cam("sensor.ffmpeg_cpu_usage"), "ffmpeg CPU", grid_options={"columns": 4}),
        tile(cam("sensor.capture_cpu_usage"), "Capture CPU", grid_options={"columns": 4}),
        tile(cam("sensor.detect_cpu_usage"), "Detect CPU", grid_options={"columns": 4}),
        tile("update.frigate_server", "Frigate version", grid_options={"columns": 12}),
        {"type": "button", "name": "Open Frigate", "icon": "mdi:open-in-new", "show_state": False,
         "tap_action": {"action": "url", "url_path": f"{FRIGATE}/review?cameras={CAMERA}"},
         "grid_options": {"columns": 12, "rows": 1}},
    ]}


def bars(entities: dict[str, str], title: str, period: str, days: int, **extra: Any) -> dict[str, Any]:
    """One bar per hour or day and camera ({entity: legend name}): the count's
    maximum in it, which is its total since the count resets at the start of each."""
    card = {"type": "statistics-graph", "title": title, "stat_types": ["max"],
            "entities": [{"entity": e, "name": n} for e, n in entities.items()],
            "period": period, "days_to_show": days, "chart_type": "bar"}
    card.update(extra)
    return card


def past_table() -> str:
    """Today's tally per camera, then the last 20 timetable trains with a
    tick or cross per camera. Built every 5 minutes by the past-trains sensor."""
    past, cams = _tt["PAST"], list(_tt["CAMERAS"])
    head = ("{% set p = state_attr('" + past + "','past') or [] %}"
            "{% set today = p | selectattr('t', 'gt', today_at().timestamp()) | list %}"
            "**Today:** {{ today | count }} timetable trains past"
            + "".join(" · " + c + " saw {{ today | selectattr('" + c.lower() + "') | list | count }}" for c in cams)
            + " · **missed by both: {{ states('" + past + "') }}**\n\n"
            "| Time | Train | | " + " | ".join(cams) + " |\n|:--|:--|:--|" + ":-:|" * len(cams) + "\n")
    rows = ("{% for e in (p | sort(attribute='t', reverse=true))[:20] %}"
            "| {{ e.t | timestamp_custom('%H:%M') }} | {{ e.n }} | {{ e.k }} | "
            + " | ".join("{{ '✓' if e." + c.lower() + " else '✗' }}" for c in cams)
            + " |\n{% else %}| | Nothing yet: the list fills every 5 minutes. | | " + " | " * (len(cams) - 1)
            + " |\n{% endfor %}")
    return head + rows


def count_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 4, "cards": [
        heading("Train count: Reolink and iPhone side by side", "mdi:counter"),
        tile(TODAY, "Reolink today", grid_options={"columns": 4}),
        tile(THIS_HOUR, "Reolink this hour", grid_options={"columns": 4}),
        tile(PASSING, "Reolink passing", grid_options={"columns": 4}),
        tile(TELE_TODAY, "iPhone today", grid_options={"columns": 4}),
        tile(TELE_THIS_HOUR, "iPhone this hour", grid_options={"columns": 4}),
        tile(TELE_PASSING, "iPhone passing", grid_options={"columns": 4}),
        full(hist([TODAY, TELE_TODAY], "Today's count (live)")),
        dict(bars({THIS_HOUR: "Reolink", TELE_THIS_HOUR: "iPhone"}, "Trains per hour (48 h)", "hour", 2),
             grid_options={"columns": 6}),
        dict(bars({TODAY: "Reolink", TELE_TODAY: "iPhone"}, "Trains per day (30 days)", "day", 30),
             grid_options={"columns": 6}),
        heading("Which train was it?", "mdi:timetable", "subtitle"),
        tile(_tt["CAMERAS"]["Reolink"][1], "Reolink: last train", grid_options={"columns": 12}),
        tile(_tt["CAMERAS"]["iPhone"][1], "iPhone: last train", grid_options={"columns": 12}),
        dict({"type": "logbook", "title": "Latest trains, matched to the timetable", "hours_to_show": 24,
              "target": {"entity_id": [text for _, text in _tt["CAMERAS"].values()]}}, grid_options={"columns": 12}),
        heading("Timetable trains past: did the cameras see them?", "mdi:train-car", "subtitle"),
        {"type": "markdown", "content": past_table(), "grid_options": {"columns": "full"}},
        {"type": "markdown", "content":
            "Each counted train is matched to the closest timetable train at Altdorf: trains that stop, and "
            "through trains (EC, IC 21) estimated from Arth-Goldau (southbound) and Bellinzona (northbound). "
            "No train within the window means one the timetable doesn't list, usually freight. "
            "Tune the travel times under Settings if through trains keep landing a few minutes off.",
         "grid_options": {"columns": "full"}},
        {"type": "markdown", "content":
            "Reolink: a train counts when it enters the **track_hd** zone. iPhone: when Frigate sees a train "
            "anywhere in its picture (no zone yet, so the far track counts too). "
            "For both, one that drops out for under 30 s counts once. "
            "HA adds a bar once its hour is over, so the hour that is running only shows in the "
            "tiles and the live chart; today's bar counts up to the last full hour. "
            "The charts only start from when the count was set up.",
         "grid_options": {"columns": "full"}},
    ]}


def history_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 4, "cards": [
        heading("Last 24 hours", "mdi:chart-timeline-variant"),
        full(hist([zone("binary_sensor.train_occupancy"), cam("binary_sensor.train_occupancy"),
                   tele("binary_sensor.train_occupancy"), cam("binary_sensor.motion"),
                   wide("binary_sensor.train_sound")], "Train, motion and sound")),
        dict(hist([wide("sensor.sound_level")], "Sound level"), grid_options={"columns": 6}),
        dict(hist([cam("sensor.camera_fps"), cam("sensor.process_fps"), cam("sensor.detection_fps"),
                   cam("sensor.skipped_fps")], "Frames per second"), grid_options={"columns": 6}),
        dict(camera_card("timeline"), grid_options={"columns": 6}),
        dict({"type": "logbook", "title": "Logbook", "hours_to_show": 24,
              "target": {"entity_id": [zone("binary_sensor.train_occupancy"), cam("binary_sensor.train_occupancy"),
                                       wide("binary_sensor.train_sound"), cam("sensor.review_status")]}},
             grid_options={"columns": 6}),
    ]}


def build() -> dict[str, Any]:
    return {"views": [{"title": "Tracks", "path": "tracks", "icon": ICON, "type": "sections", "max_columns": 4,
                       "sections": [picture_section(), now_section(), count_section(), settings_section(),
                                    health_section(), history_section()]}]}

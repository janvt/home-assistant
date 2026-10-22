"""The Trains debug dashboard (`dashboard-trains`): is Frigate seeing the trains?

`build()` returns the whole dashboard config, owned by the script like the
Weather one: a card added in the UI is gone after the next sync.

Two Frigate cameras look at the same lens. `train_track` is a full-resolution
crop of the track from the main stream and does the detecting; its `track_hd`
zone is the part a train has to cross. `train_slice` is the wide view on the
sub stream and keeps the recordings and the microphone. In the sub stream a
train is too small for the model, so its own detection finds nothing.

The page shows the picture Frigate detects on and the one it draws its boxes
on, whether it thinks a train is there right now, the knobs that decide that,
how hard the box is working, and the last 24 hours of it.
"""
from __future__ import annotations

from typing import Any

DASHBOARD = "dashboard-trains"
TITLE = "Trains"
ICON = "mdi:train"
CAMERA = "train_track"      # detects
WIDE = "train_slice"        # records, listens
ZONE = "track_hd"
FRIGATE = "http://10.69.42.175:5000"
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
]


def cam(kind: str, camera: str = CAMERA) -> str:
    """`binary_sensor.train_track_motion` from ("binary_sensor", "motion")."""
    domain, _, key = kind.partition(".")
    return f"{domain}.{camera}_{key}"


def wide(kind: str) -> str:
    return cam(kind, WIDE)


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
    """The advanced camera card on both cameras, opening on `view` (live,
    timeline …). The crop comes first; the wide view has the recordings."""
    card = {"type": "custom:advanced-camera-card",
            "cameras": [{"camera_entity": f"camera.{c}", "frigate": {"url": FRIGATE}} for c in (CAMERA, WIDE)],
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
        heading("Last train", "mdi:image", "subtitle"),
        {"type": "picture-entity", "entity": f"image.{CAMERA}_train", "show_state": False, "show_name": False},
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
        tile(cam("sensor.ffmpeg_cpu_usage"), "ffmpeg CPU", grid_options={"columns": 4}),
        tile(cam("sensor.capture_cpu_usage"), "Capture CPU", grid_options={"columns": 4}),
        tile(cam("sensor.detect_cpu_usage"), "Detect CPU", grid_options={"columns": 4}),
        tile("update.frigate_server", "Frigate version", grid_options={"columns": 12}),
        {"type": "button", "name": "Open Frigate", "icon": "mdi:open-in-new", "show_state": False,
         "tap_action": {"action": "url", "url_path": f"{FRIGATE}/review?cameras={CAMERA}"},
         "grid_options": {"columns": 12, "rows": 1}},
    ]}


def history_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 4, "cards": [
        heading("Last 24 hours", "mdi:chart-timeline-variant"),
        full(hist([zone("binary_sensor.train_occupancy"), cam("binary_sensor.train_occupancy"),
                   cam("binary_sensor.motion"), wide("binary_sensor.train_sound")], "Train, motion and sound")),
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
                       "sections": [picture_section(), now_section(), settings_section(), health_section(),
                                    history_section()]}]}

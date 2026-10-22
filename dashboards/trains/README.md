# Trains debug dashboard

The **Trains** dashboard (`/dashboard-trains`, admins only) is for tuning
Frigate's train detection.

Frigate has two cameras on the same Reolink. `train_track` is a full-resolution
crop of the track from the 2560×1920 main stream (go2rtc crops it) and does the
detecting; a train has to cross its `track_hd` zone. `train_slice` is the wide
view on the 640×480 sub stream and keeps the recordings and the microphone. In
the sub stream a train is only about 120×45 px, too small for the model, so
detection there finds nothing.

| File | What |
|------|------|
| [`build.py`](build.py) | Builds the whole dashboard config. Pure functions. |
| [`sync.py`](sync.py) | Creates the dashboard if needed, enables the Frigate diagnostics it uses, pushes it. |

## What's on it

- **What Frigate sees:** both cameras live (advanced camera card, crop first),
  and the crop's debug picture with the zone, motion boxes, detector regions and
  object boxes drawn in, refreshed every second. That one comes straight from
  Frigate at `10.69.42.175:5000`, so it only loads on the LAN over http.
- **Right now:** train on the track and in frame, motion, train sound, review
  status, the counts, sound level and the last train snapshot.
- **iPhone telephoto (`train_tele`):** Blackmagic Camera on an iPhone, pushing
  to MediaMTX (`10.69.42.222`), which Frigate reads. It detects trains too,
  with no zone yet; its live picture, last train, frame rates and count sit
  next to the Reolink's, to compare the two cameras.
- **Train count:** Reolink and iPhone side by side: today, this hour, and whether one is passing; a live chart
  of today's count; bars of
  trains per hour (48 h) and per day (30 days), and the latest trains. The
  count helpers come from the Mobile alert pills' sync (`HISTORY_STATS` in
  `mobile-alerts/pills.py`).
- **Settings:** the crop's switches, motion threshold and contour area, plus
  audio and recording on the wide camera. They
  last until Frigate restarts; its config file wins after that.
- **Frigate:** status, uptime, fps (camera, processed, detections, skipped),
  inference speed, GPU and CPU load, version, and a link to Frigate's review page.
- **Last 24 hours:** train, motion and sound on one timeline, sound level, fps,
  Frigate's own timeline of the camera, and a logbook.

## Changing it

```bash
.venv-test/bin/python dashboards/trains/sync.py            # dry run
.venv-test/bin/python dashboards/trains/sync.py --apply
```

It uses the same `dashboards/.env` as the other dashboards. **The script owns
this dashboard:** a card added in the HA UI is gone after the next `--apply`.
The Frigate integration ships its fps, CPU, inference and tuning entities
disabled; the sync enables the ones in `DISABLED_BY_DEFAULT`.

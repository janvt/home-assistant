# Trains debug dashboard

The **Trains** dashboard (`/dashboard-trains`, admins only) is for tuning
Frigate's train detection on the `train_slice` camera and its `track` zone.

| File | What |
|------|------|
| [`build.py`](build.py) | Builds the whole dashboard config. Pure functions. |
| [`sync.py`](sync.py) | Creates the dashboard if needed, enables the Frigate diagnostics it uses, pushes it. |

## What's on it

- **What Frigate sees:** the live stream (advanced camera card), and Frigate's
  debug picture with the zone, motion mask, motion boxes, detector regions and
  object boxes drawn in, refreshed every second. That one comes straight from
  Frigate at `10.69.42.175:5000`, so it only loads on the LAN over http.
- **Right now:** train on the track and in frame, motion, train sound, review
  status, the counts, sound level and the last train snapshot.
- **Settings:** the camera's switches, motion threshold and contour area. They
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

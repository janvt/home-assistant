# Stream Deck → Home Assistant (headless Raspberry Pi 5)

Runs [basnijholt/home-assistant-streamdeck-yaml](https://github.com/basnijholt/home-assistant-streamdeck-yaml)
in Docker Compose on a headless Raspberry Pi 5, driving an Elgato Stream Deck
plugged into the Pi's USB. The included [configuration.yaml](configuration.yaml)
defines a **Home** page with a light/climate button pair and two Stream Deck Plus
**dials** — one for light brightness, one for climate target temperature.

## Files

| File | Purpose |
|------|---------|
| [`docker-compose.yaml`](docker-compose.yaml) | Container definition (image, USB access, config mount) |
| [`configuration.yaml`](configuration.yaml) | Pages, buttons and dials |
| [`.env.example`](.env.example) | Template for Home Assistant host + token |

## Prerequisites

- Raspberry Pi 5 running a 64-bit OS (Raspberry Pi OS Bookworm or similar), headless.
- Docker Engine + Compose plugin:
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"   # log out/in afterwards
  ```
  The upstream image publishes an `arm64` variant, so it runs natively on the Pi 5.
- A Stream Deck connected to the Pi over USB.

## Setup

1. **Copy this directory to the Pi** (e.g. `~/streamdeck`) and `cd` into it.

2. **Create your `.env`** from the template and fill in your Home Assistant
   host and a long-lived access token:
   ```bash
   cp .env.example .env
   nano .env
   ```
   Create the token in Home Assistant under
   *Profile → Security → Long-lived access tokens*.

   There is **no separate port setting** — the connection URI is
   `<WEBSOCKET_PROTOCOL>://<HASS_HOST>/api/websocket`, so put the port in
   `HASS_HOST` if HA isn't on the protocol default. For a bare HA on a LAN IP
   (plain HTTP), use `HASS_HOST=<ip>:8123` and `WEBSOCKET_PROTOCOL=ws`. Behind
   an HTTPS reverse proxy, use the hostname and `WEBSOCKET_PROTOCOL=wss`.

3. **Adjust `configuration.yaml`** so the `entity_id`s match your setup.

4. **Start it:**
   ```bash
   docker compose up -d
   docker compose logs -f      # watch it connect and detect the Stream Deck
   ```

The Stream Deck lights up with the **Home** page. `auto_reload: true` means
edits to `configuration.yaml` are picked up without a restart.

## USB access

The compose file uses `privileged: true` plus a `/dev/bus/usb` mount — the
simplest approach that reliably works headless. To avoid `privileged`, install
a udev rule on the host instead and drop `privileged` from the compose file:

```bash
echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"' \
  | sudo tee /etc/udev/rules.d/70-streamdeck.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then reconnect the Stream Deck. The `0fd9` vendor id covers all Elgato Stream
Deck models. Keep the `devices: [/dev/bus/usb:/dev/bus/usb]` mapping either way.

## Run on boot

`restart: unless-stopped` in the compose file brings the container back after a
reboot as long as the Docker daemon starts on boot (the default). To confirm:

```bash
sudo systemctl enable docker
```

## Dials (Stream Deck Plus)

Four dials, left → right, defined in [`configuration.yaml`](configuration.yaml):

| # | Control | Turn | Push |
|---|---------|------|------|
| 1 | Living Room media volume | set volume | toggle mute |
| 2 | Madagascar media volume | set volume | — |
| 3 | Living Room ceiling light | set brightness | toggle Living Room lights |
| 4 | Kitchen ceiling light | set brightness | — |

**How turn + push share one dial:** the app merges two *consecutive* `dials`
entries into a single physical dial when their `dial_event_type` differs (a
`TURN` entry immediately followed by a `PUSH` entry). Two `TURN` entries in a
row stay on separate dials. That's why the file has six entries that collapse to
four dials — **don't reorder them**.

**Units matter:** `dial_value()` reads the entity's `state_attribute` in its
native units, so `min/max/step` are set to match — `volume_level` on `0–1`,
`brightness` on `0–255` — and the display/service templates convert to a
percentage. Keeping them aligned avoids the dial jumping on the first turn.

The `entity_id`s (`media_player.living_room`, `media_player.madagascar`,
`light.living_room_ceiling`, `light.living_room`, `light.kitchen_ceiling`) are
placeholders — swap them for yours. See the
[upstream docs](https://github.com/basnijholt/home-assistant-streamdeck-yaml)
for the full schema and helper functions (`dial_value()`, `dial_attr()`).

## Troubleshooting

- **Stream Deck not detected** — check `docker compose logs`, confirm it shows
  up in `lsusb` on the host, and verify USB access (privileged or udev rule).
- **`ConnectionRefusedError` on port 443** — the host is reachable but nothing
  answers on that port. HA on a LAN IP speaks plain `ws` on `8123`, not `wss`
  on `443`; set `HASS_HOST=<ip>:8123` and `WEBSOCKET_PROTOCOL=ws`.
- **Auth errors** — re-check `HASS_HOST`/`HASS_TOKEN` in `.env`; `HASS_HOST`
  should have no scheme (no `http://`), just `host:port`.
- **Wrong entities** — the defaults are placeholders; edit `configuration.yaml`.

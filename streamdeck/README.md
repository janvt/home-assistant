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

## Buttons (LCD keys)

The eight LCD keys fill left→right, top→bottom, so the `buttons:` list order maps
straight onto the two rows:

| Key | Row | Label | Action |
|-----|-----|-------|--------|
| 1 | top | Chill | toggle `scene.chill` ↔ Living Room off |
| 2 | top | Vinyl | toggle `scene.vinyl` ↔ Living Room off |
| 3 | top | Pain Cave | toggle `scene.pain_cave` ↔ Living Room off |
| 4 | top | Work S | toggle `scene.work_s` ↔ Kitchen off |
| 5 | bottom | Living Room | toggle `light.living_room_ceiling_light` |
| 6 | bottom | Kitchen | toggle `light.kitchen_ceiling_light` |

Keys 7–8 are unused — add more `buttons:` entries to fill them. HA also has a
separate `scene.work` ("Work") if key 4 was meant to be that instead of
`scene.work_s`.

### Scene toggle behaviour

The top-row buttons don't just fire a scene — they **toggle** it, driven by the
`input_select.active_scene` helper (kept in sync by the HA `Mark <scene> active`
automations, which set it to the scene's short name whenever that scene runs).
Each button calls `script.streamdeck_scene_toggle` with the scene and the area:

- `active_scene` **≠** this scene → activate the scene (the automation then sets
  `active_scene` to it).
- `active_scene` **=** this scene → `light.turn_off` the whole area and reset the
  helper to `none`.

So pressing a *different* scene switches to it; pressing the *active* one clears
the room. Each button's `entity_id` is `input_select.active_scene`, so it
re-renders when the active scene changes, and `icon_mdi_color` shows amber for
the active scene, grey otherwise.

The script lives in HA (created via the config API, editable/removable under
**Settings → Automations & Scenes → Scripts**), not in this repo:

```yaml
alias: Stream Deck Scene Toggle
mode: restart
fields: { scene: {}, area: {} }
sequence:
  - variables: { scene_key: "{{ scene.split('.')[-1] }}" }
  - if:
      - condition: template
        value_template: "{{ is_state('input_select.active_scene', scene_key) }}"
    then:
      - service: light.turn_off
        target: { area_id: "{{ area }}" }
      - service: input_select.select_option
        target: { entity_id: input_select.active_scene }
        data: { option: none }
    else:
      - service: scene.turn_on
        target: { entity_id: "{{ scene }}" }
```

This assumes the scene's short name matches an `input_select.active_scene`
option (`scene.chill` → `chill`, etc.), which holds for the current scenes.

## Dials (Stream Deck Plus)

Four dials, left → right, defined in [`configuration.yaml`](configuration.yaml):

| # | Control | Turn | Push |
|---|---------|------|------|
| 1 | Living Room media volume (`media_player.living_room`) | set volume | toggle mute |
| 2 | Madagascar media volume (`media_player.unnamed_room`) | set volume | toggle mute |
| 3 | Living Room ceiling light (`light.living_room_ceiling_light`) | set brightness | toggle **Living Room area** lights |
| 4 | Kitchen ceiling light (`light.kitchen_ceiling_light`) | set brightness | toggle **Kitchen area** lights |

**How turn + push share one dial:** the app merges two *consecutive* `dials`
entries into a single physical dial when their `dial_event_type` differs (a
`TURN` entry immediately followed by a `PUSH` entry). Two `TURN` entries in a
row stay on separate dials. That's why the file has eight entries (four
TURN/PUSH pairs) that collapse to four dials — **don't reorder them**.

**Units matter:** `dial_value()` reads the entity's `state_attribute` in its
native units, so `min/max/step` are set to match — `volume_level` on `0–1`,
`brightness` on `0–255` — and the display/service templates convert to a
percentage. Keeping them aligned avoids the dial jumping on the first turn.

**Area toggles:** dials 3 and 4 push with `service: light.toggle` and a
`target: {area_id: ...}`, flipping every light in that HA area. Confirm the
IDs with `{{ area_id('Living Room') }}` / `{{ area_id('Kitchen') }}` in HA's
Developer Tools → Template. See the
[upstream docs](https://github.com/basnijholt/home-assistant-streamdeck-yaml)
for the full schema and helper functions (`dial_value()`, `dial_attr()`).

## Troubleshooting

- **Stream Deck not detected** — check `docker compose logs`, confirm it shows
  up in `lsusb` on the host, and verify USB access (privileged or udev rule).
- **`TransportError: Failed to write feature report (-1)`** (crash at
  `deck.reset()`) — the deck enumerated but rejected a USB write. Stop the
  restart loop with `docker compose down`, unplug/replug the Stream Deck, then
  `docker compose up`. If it persists, it's a USB-link issue: put the deck on a
  USB 2.0 port or powered hub (the Pi 5's USB 3.0 ports can be flaky with Stream
  Decks) and watch `dmesg -w` while replugging for reset/power errors.
- **`ConnectionRefusedError` on port 443** — the host is reachable but nothing
  answers on that port. HA on a LAN IP speaks plain `ws` on `8123`, not `wss`
  on `443`; set `HASS_HOST=<ip>:8123` and `WEBSOCKET_PROTOCOL=ws`.
- **Auth errors** — re-check `HASS_HOST`/`HASS_TOKEN` in `.env`; `HASS_HOST`
  should have no scheme (no `http://`), just `host:port`.
- **Wrong entities** — the defaults are placeholders; edit `configuration.yaml`.

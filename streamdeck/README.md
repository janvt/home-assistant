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
- `python3` + `venv` and a TrueType font, for generating the button images
  (see [Button images](#button-images)):
  ```bash
  sudo apt-get install -y python3-venv fonts-dejavu-core
  ```
- [go-task](https://taskfile.dev) to run the workflow ([`Taskfile.yml`](Taskfile.yml)):
  ```bash
  sudo snap install task --classic   # or: see taskfile.dev/installation
  ```

## Setup

Everything below is wrapped in `task` — run `task` alone to list the commands.

1. **Copy this directory to the Pi** (e.g. `~/streamdeck`) and `cd` into it.

2. **Create and fill in `.env`:**
   ```bash
   task env      # copies .env.example -> .env
   nano .env
   ```
   Set your Home Assistant host and a long-lived access token (create it under
   *Profile → Security → Long-lived access tokens*). There is **no separate port
   setting** — the connection URI is `<WEBSOCKET_PROTOCOL>://<HASS_HOST>/api/websocket`,
   so put the port in `HASS_HOST` if HA isn't on the protocol default. For a bare
   HA on a LAN IP (plain HTTP), use `HASS_HOST=<ip>:8123` and `WEBSOCKET_PROTOCOL=ws`;
   behind an HTTPS reverse proxy, use the hostname and `WEBSOCKET_PROTOCOL=wss`.

3. **Adjust `configuration.yaml`** so the `entity_id`s match your setup.

4. **Deploy** — builds the button images (venv + Pillow on first run), starts the
   container, and tails the logs so you can watch it connect and detect the deck:
   ```bash
   task deploy
   ```

The Stream Deck lights up with the **Home** page. `auto_reload: true` means edits
to `configuration.yaml` are picked up without a restart — but **image changes are
not watched**, so after editing `generate_icons.py` run `task regen` (rebuild +
restart).

### Task reference

| Task | Does |
|------|------|
| `task update` | **git pull → rebuild images → restart** (one-shot update) |
| `task deploy` | build icons → `up -d` → follow logs (first-time bring-up) |
| `task up` | build icons (if venv missing, create it) → start detached |
| `task regen` | rebuild button images → restart (apply icon/label changes) |
| `task icons` | just (re)generate `icons/*.png` |
| `task restart` / `task down` / `task logs` | container lifecycle |
| `task env` | scaffold `.env` from the template |

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

## Pages / views

There are two pages. **Key 8 is the mode button** on both — it's a `next-page`
special button, and `next-page` wraps (`% len(pages)`), so pressing key 8 cycles
Home → Shades → Home. Add a third page later and the same key cycles through all
of them. The dials swap with the page too, not just the buttons.

## Button & dial images

Neither the buttons nor the dials use the tool's built-in rendering — it can't
shrink the icon, put a label below it, or draw a decent gauge.
[`generate_icons.py`](generate_icons.py) pre-renders every key and dial frame as
a PNG, and each `icon:` field points at the right one, templated on state.

`task icons` builds them all: **24 key images** (120×120) and **188 dial frames**
(200×100 — frames per dial vary by granularity). `icons/` is git-ignored (build artifact), so
build it on each machine before start; the MDI webfont is fetched once into
`.iconbuild/`.

```bash
task icons     # creates the venv on first run, then writes icons/ + icons/dials/
```

Tunables live at the top of the script (button `ICON_PX`/`LABEL_PX`/`RADIUS`;
dial `DIAL_STYLES` colours + icons, `SS` supersample). After editing, `task regen`
rebuilds and restarts (`auto_reload` doesn't watch image files). Adding/renaming
a control means updating both the script's spec and the `icon:` path.

### Buttons

Each button's `icon:` points at a PNG, templated on state:

```yaml
icon: '{{ "/app/icons/chill_on.png" if is_state("input_select.active_scene","chill") else "/app/icons/chill_off.png" }}'
```

The chip is a **grey chip when off/inactive** and a **domain colour when
active**; action/nav keys are a solid domain colour always:

| Domain | Colour | Active |
|--------|--------|--------|
| lights, scenes | amber | `#EF9F27` bg, `#412402` icon+label |
| switches, modes, nav | blue | `#378ADD` bg, white |
| locks, doors | red | `#E24B4A` bg, white |
| covers | green | `#639922` bg, white |
| inactive (any) | grey | `#C9C9CE` bg, `#6E6E73` |

### Dials

Dials render as a **vertical fill bar** on the touch strip: a domain-coloured bar
filled bottom-to-top to the value, alongside an icon, the value number, and the
room label. Each dial has a frame per step and the `icon:` templates to the
nearest one. Granularity is per type — **volume 2%, brightness 5%, shades 5%**
— set in two places that must match: the display step in `DIAL_STYLES`
(`generate_icons.py`) and each dial's turn increment (`attributes.step`):

```yaml
icon: '/app/icons/dials/lr_shade_{{ (((dial_value() / 5) | round) * 5) | int }}.png'
```

Gauge colours: **cyan** volume (`#38D6F2`), **amber** brightness (`#F7A828`),
**green** shades (`#63C63B`).

**Eager feedback:** each dial has a `delay` (debounce — `0.6s` volume, `0.3s`
brightness, `0.5s` shades). With it set, a turn re-renders the bar **instantly
from the local value** and the HA service is sent **once** after you stop turning
— so the bar tracks your finger and the shade motor gets a single move to the
target instead of chasing every detent. Without `delay` the bar only redraws on
HA's echoed state (laggy, and shades crawl with the motor).

**Direction & orientation:** all dials use a **negative `attributes.step`**, so
turning right *lowers* the value (`increment_state` does `state += value*step`;
a negative step flips it, clamping still holds). Shades are also **display-
inverted** — the frame is chosen from `100 - dial_value()`, so a **full bar =
closed** and the number reads **% closed** (the service still receives the real
HA position, where 100 = open).

**Mute:** the volume dials are state-driven off `is_volume_muted` — when a media
player is muted the dial shows a dedicated greyed `*_muted.png` frame (mute icon,
"MUTE", empty bar) instead of the level, via a templated `icon:`. Mute changes
render on HA's echo (not the buggy turn path), so both volume dials reflect it.

**Live-render caveat (upstream bug):** the eager/local re-render on turn looks
the dial up by raw list index but is handed the *sorted* index, so it only works
for a dial whose TURN entry sits at that raw position — which holds only when the
dials are **TURN-only** (no paired PUSH). That's why the **shade dials are
TURN-only** (all four live-update). The Home volume/brightness dials keep their
PUSH actions (mute / area-toggle), so only the leftmost (LR volume) live-updates;
the others redraw after the debounce + HA echo. Fixing that without dropping
their push needs a renderer patch (fork).

## Home page — buttons (LCD keys)

The eight LCD keys fill left→right, top→bottom, so the `buttons:` list order maps
straight onto the two rows:

| Key | Row | Label | Action |
|-----|-----|-------|--------|
| 1 | top | Chill | toggle `scene.chill` ↔ Living Room off |
| 2 | top | Vinyl | toggle `scene.vinyl` ↔ Living Room off |
| 3 | top | Pain Cave | toggle `scene.pain_cave` ↔ Living Room off |
| 4 | top | Work S | toggle `scene.work_s` ↔ Kitchen off |
| 5 | bottom | Hallway | toggle `light.shellypro1pm_ec62608ad35c_switch_0` (Hallway Spots) |
| 6 | bottom | Outside | toggle `light.balcony_ceiling_light` |
| 7 | bottom | 💩 | trigger `automation.keep_bathroom_fan_on` |
| 8 | bottom | Shades | **mode button** — cycle to the next view |

HA also has a separate `scene.work` ("Work") if key 4 was meant to be that
instead of `scene.work_s`.
The poop key (7) fires `automation.trigger` on the fan automation, but shows the
status of `input_boolean.keep_bathroom_fan_on`: `linked_entity` points at the
helper so the key re-renders on its changes, and the `emoticon-poop` icon +
`icon_background_color` brighten while the helper is `on`.

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

## Shades page

Reached via the mode button (key 8). Layout:

Keys are colour-grouped into columns (top row = keys 1-4, bottom = 5-8):

| Key | Row | Label | Action |
|-----|-----|-------|--------|
| 1 | top | House | `switch.toggle` on `switch.buzzer` (SwitchBot street door), 5s cancel |
| 2 | top | Open All | `script.open_all_blinds` |
| 3 | top | Guest | toggle `input_boolean.guest_mode` |
| 4 | top | Lights Off | `script.turn_off_all_lights` |
| 5 | bottom | Apartment | `lock.open` on `lock.nuki_schmatzknauf_lock_2` (Nuki — unlatches), 5s cancel |
| 6 | bottom | Close All | `cover.close_cover` on all five shades (explicit list) |
| 7 | bottom | Cleaning | toggle `input_boolean.cleaning_mode` |
| 8 | bottom | Menu | mode button — cycle to next page |

So the columns read: **doors (red)**, **shades (green)**, **modes (blue)**, then
**Lights Off (amber) over Menu**. The two door keys (1 House, 5 Apartment) use
`delay: 5` as an accidental-press guard — a press starts a 5-second countdown
ring before firing, and **pressing again during it cancels**.

Dials (turn = set position; **TURN-only**, no push — see note below):

| # | Shade |
|---|-------|
| 1 | Living Room (`cover.living_room_shades`) |
| 2 | Kitchen (`cover.shellyplus2pm_cc7b5c894ba4`) |
| 3 | Bedroom (`cover.bedroom_shades`) |
| 4 | Guest Bedroom (`cover.guest_bedroom_shades`) |

`cover.east_facing_shades` has no dial (5 shades, 4 dials) but is still included
in **Close All**. All five covers report `supported_features=15` (open/close/set
position/stop).

## Home page — dials (Stream Deck Plus)

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

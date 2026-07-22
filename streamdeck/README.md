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
| `task harden` | idempotently apply the host-level hardening/resilience steps (needs sudo) |

## USB access

The compose file runs the container **unprivileged** (hardened): there is no
`privileged: true`. USB (HID) access is granted narrowly — the `/dev/bus/usb`
mount plus a `device_cgroup_rules` entry allowing only the USB device-node major
(`c 189:* rmw`), with `cap_drop: [ALL]` and `security_opt: no-new-privileges:true`.

Because the container is unprivileged, the host must make the Stream Deck's
device node accessible with a udev rule (**required**, not optional):

```bash
echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"' \
  | sudo tee /etc/udev/rules.d/70-streamdeck.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then reconnect the Stream Deck. The `0fd9` vendor id covers all Elgato Stream
Deck models. Keep the `devices: [/dev/bus/usb:/dev/bus/usb]` mapping.

If the deck still isn't detected, fall back to a privileged container by
temporarily adding `privileged: true` to the service and removing the
`cap_drop`, `security_opt` and `device_cgroup_rules` lines — but the udev rule
above is the intended, hardened path.

## Container hardening

The service applies defence-in-depth so a compromised container has minimal
reach on the Pi:

| Setting | Effect |
|---------|--------|
| _no_ `privileged` | container can't access all host devices / capabilities |
| `security_opt: no-new-privileges:true` | processes can't gain privileges via setuid/setgid |
| `cap_drop: [ALL]` | drops every Linux capability (none are needed for USB HID) |
| `device_cgroup_rules: ['c 189:* rmw']` | permits only USB device nodes, not arbitrary devices |
| `mem_limit: 256m`, `pids_limit: 256` | caps memory and process count to contain runaway/fork behaviour |

The image is **pinned by digest** (`image: basnijholt/...@sha256:...`) rather
than `:latest`, which hardens the supply chain — see
[Resilience → Pinning the image](#pinning-the-image) for how to bump it.

## Run on boot

`restart: unless-stopped` in the compose file brings the container back after a
reboot as long as the Docker daemon starts on boot (the default). To confirm:

```bash
sudo systemctl enable docker
```

## Resilience

`restart: unless-stopped` + `systemctl enable docker` only cover the easy cases
(process crash, clean reboot). For an always-on headless appliance the real
outage causes are **hangs, disk-fill, power loss and kernel freezes**. The
compose file already handles the first two; the rest are host-level steps below.

### Handled in the compose file

| Concern | What's configured |
|---------|-------------------|
| **App hang** (running but wedged) | A `healthcheck` TCP-probes the Home Assistant websocket host, and a small `autoheal` service restarts the container when it goes `unhealthy` (Compose won't restart on health state alone). |
| **Logs filling the SD card** | Both services cap `json-file` logs at `max-size: 10m`, `max-file: 3` — the default driver never rotates, and a restart loop can otherwise fill a small card in hours. |
| **Bad image on restart** | The image is pinned by digest (see [Pinning the image](#pinning-the-image)), so a moving upstream `:latest` can't silently break the next restart. |

The healthcheck assumes `python3` is on the container's PATH (the upstream image
is Python-based); if not, change it to `python` in `docker-compose.yaml`. The
`autoheal` service mounts the Docker socket read-only — that's inherent to how it
restarts containers, so treat it as a trusted, root-equivalent component.

### Host-level steps (do these on the Pi)

Most of these are automated idempotently by [`harden.sh`](harden.sh) — run
`task harden` (needs sudo; it never reboots, and reports the manual/hardware
steps it can't do). The individual commands are documented below for reference.

**Hardware watchdog** — recovers from a *total* kernel freeze (undervoltage,
thermal, driver lockup) that `restart:` can't touch. The Pi has a built-in
watchdog:

```bash
# Enable the watchdog device
echo 'dtparam=watchdog=on' | sudo tee -a /boot/firmware/config.txt
# Have systemd pet it and reboot on a hung host
sudo sed -i 's/^#\?RuntimeWatchdogSec=.*/RuntimeWatchdogSec=15/' /etc/systemd/system.conf
sudo reboot
```

**SD-card durability / power loss** — SD cards corrupt on abrupt power loss, and
this deployment writes icon builds + logs. In rough priority:

- **Boot from a USB SSD** instead of the SD card (the Pi 5 supports it) — far
  more resilient and faster.
- **Use a quality PSU** (the official 27 W USB-C PD). Brownouts/undervoltage
  cause reset loops — the same USB-link flakiness the [Troubleshooting](#troubleshooting)
  section warns about.
- If staying on SD, consider `log2ram` and keeping writes (logs, icons) low.

**Unattended host patches + time sync** — for an always-on box:

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
timedatectl status   # confirm "System clock synchronized: yes" / NTP active
```

Accurate time matters here: websocket TLS and the long-lived token are
time-sensitive, so a drifting clock shows up as auth/connection failures.

### Pinning the image

The image is **pinned by digest** in `docker-compose.yaml` (not `:latest`), so an
update has a fixed, rollback-able reference. The current pin is the multi-arch
`latest` manifest (built from upstream commit
`1ad32a4dfb802401bb3f4b9a8130733b4f6b2e2c`), which keeps both `amd64` and the
`arm64` the Pi 5 pulls.

To move to a newer build, resolve the new digest and swap it in:

```bash
docker inspect --format '{{index .RepoDigests 0}}' \
  basnijholt/home-assistant-streamdeck-yaml:latest
# -> basnijholt/home-assistant-streamdeck-yaml@sha256:<digest>
```

Note the value is a `sha256:` **registry digest**, not a git commit SHA — only
the former works in `image:`. Bump it deliberately when you want a new version.

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
  up in `lsusb` on the host, and verify the udev rule is installed (see
  [USB access](#usb-access)).
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

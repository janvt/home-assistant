# Stream Deck → Home Assistant (two decks)

Runs [basnijholt/home-assistant-streamdeck-yaml](https://github.com/basnijholt/home-assistant-streamdeck-yaml)
against two Elgato decks on two different machines, sharing one image renderer:

| Deck | Host | Runs as | Keys | Dials |
|------|------|---------|------|-------|
| **Stream Deck Plus** | headless Raspberry Pi 5 | Docker Compose | 8 (4×2) @ 120px | 4 |
| **Stream Deck Plus XL** | Mac laptop | native venv | 36 (9×4) @ 112px | 6 |

Each deck owns its `configuration.yaml`, `.env` and rendered `icons/`; they
share the renderer, the palette, and the Home-Assistant-side helpers.

> **One deck per host.** The app's `get_deck()` grabs the first deck it
> enumerates, with no way to select a device, so never plug both decks into the
> same machine — it would pick whichever enumerates first.

## Files

| Path | Purpose |
|------|---------|
| [`generate_icons.py`](generate_icons.py) | **Shared** renderer — key chips + dial gauges for every deck |
| [`decks/<deck>/spec.py`](decks) | That deck's content: key size, which tiles, which dials |
| [`decks/<deck>/configuration.yaml`](decks) | That deck's pages, buttons and dials |
| [`decks/<deck>/.env.example`](decks) | Per-deck HA host + token template (they differ — see below) |
| [`decks/plus/docker-compose.yaml`](decks/plus/docker-compose.yaml) | Pi container (image, USB access, hardening) |
| [`Taskfile.yml`](Taskfile.yml) | `task plus:*` / `task xl:*` workflows |
| [`harden.sh`](harden.sh) | Host hardening/resilience (Pi only) |

## Prerequisites

**Both machines**

- [go-task](https://taskfile.dev) to run the workflow ([`Taskfile.yml`](Taskfile.yml)).
- `python3` + `venv` and a TrueType font, for rendering the deck images.

**Raspberry Pi (Plus)**

- Raspberry Pi 5 running a 64-bit OS (Raspberry Pi OS Bookworm or similar), headless.
- Docker Engine + Compose plugin:
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"   # log out/in afterwards
  ```
  The upstream image publishes an `arm64` variant, so it runs natively on the Pi 5.
- Renderer deps + go-task:
  ```bash
  sudo apt-get install -y python3-venv fonts-dejavu-core
  sudo snap install task --classic   # or: see taskfile.dev/installation
  ```

**Mac (Plus XL)** — *not* Docker: Docker Desktop on macOS runs in a VM with no
USB passthrough, so the app runs natively. `task xl:install` handles the Python
side; it needs Homebrew libs, go-task, and a modern Python:

```bash
brew install go-task hidapi cairo libffi python@3.12
```

> **Python ≥ 3.10 required.** macOS ships 3.9 as `python3` (from the Xcode
> command line tools) and the app refuses to install on it. The Taskfile picks
> the newest `python3.13/3.12/3.11/3.10` it finds on PATH and fails with a clear
> message if none qualifies; override with `task xl:install XLPY=/path/to/python3.12`.

> **Plus XL needs the library from git.** `StreamDeckPlusXL` exists only on
> `python-elgato-streamdeck`'s `master` — the latest release (0.9.8) has neither
> the device class nor its USB product id (`0x00c6`). `task xl:install` installs
> the app first, then force-reinstalls `streamdeck` from `master` so it wins over
> the release the app would otherwise pull in, and verifies the class imports.

## Setup

Everything is wrapped in `task` — run `task` alone to list the commands. Note
each deck needs **its own `.env`**, and the values genuinely differ: the Pi
reaches HA directly at `10.69.42.3:8123` over plain `ws`, while the laptop is on
a different subnet and must go via `ha.janvt.dev` over `wss`. There is no
separate port setting — the URI is `<WEBSOCKET_PROTOCOL>://<HASS_HOST>/api/websocket`,
so any non-default port goes inside `HASS_HOST`.

### Stream Deck Plus (on the Pi)

```bash
task plus:env          # decks/plus/.env from the template
nano decks/plus/.env   # set HASS_TOKEN
task plus:deploy       # render 120px images → up -d → follow logs
```

`auto_reload: true` picks up `configuration.yaml` edits without a restart — but
**image files are not watched**, so after changing a spec or the renderer run
`task plus:regen` (rebuild + restart).

### Stream Deck Plus XL (on the Mac)

```bash
task xl:install        # venv + app + streamdeck from git master (verifies Plus XL support)
task xl:env            # decks/plus-xl/.env from the template
nano decks/plus-xl/.env
task xl:detect         # confirm the deck is seen (prints deck type + pid)
task xl:run            # renders 112px images, then runs in the foreground
```

`task xl:run` runs in the foreground (Ctrl-C to stop) — handy while iterating.

#### Running it automatically at login

```bash
task xl:service          # install + start the LaunchAgent
task xl:service:status   # state / pid / last exit
task xl:service:logs     # tail ~/Library/Logs/streamdeck-xl.log
task xl:service:stop     # stop and uninstall
```

This installs [`com.janvt.streamdeck-xl.plist`](decks/plus-xl/com.janvt.streamdeck-xl.plist)
into `~/Library/LaunchAgents/` and bootstraps it. Design notes:

- It's a **LaunchAgent** (your login session), not a system LaunchDaemon — that's
  what gives it USB HID access to the deck.
- **The token isn't duplicated into the plist**: the agent runs
  `bash -c 'set -a; . ./.env; ...'`, so `HASS_TOKEN` stays only in
  `decks/plus-xl/.env`.
- `HOMEBREW_PREFIX` and `PATH` are set explicitly. launchd starts with a minimal
  environment, and `python-elgato-streamdeck` finds Homebrew's `libhidapi` via
  `HOMEBREW_PREFIX` (falling back to shelling out to `brew`) — without this it
  can't open the deck.
- `KeepAlive`/`SuccessfulExit: false` restarts it if it exits non-zero (crash,
  deck unplugged, HA unreachable). `ThrottleInterval: 30` stops an unplugged deck
  from respawning in a tight loop.
- Re-running `task xl:service` boots it out and back in, so plist edits apply.
- After changing images, `task xl:regen` now **restarts the service automatically**
  if it's loaded (falling back to the manual hint if you're using `xl:run`).

Logs go to `~/Library/Logs/streamdeck-xl.log`. It's not rotated — if it grows,
trim it or add a `newsyslog.d` entry.

### Task reference

| Task | Does |
|------|------|
| `task plus:deploy` | render → `up -d` → follow logs (first-time Pi bring-up) |
| `task plus:update` | **git pull → rebuild images → restart** (one-shot Pi update) |
| `task plus:regen` | rebuild Plus images → restart (apply icon/label changes) |
| `task plus:up` / `down` / `restart` / `logs` | container lifecycle |
| `task plus:env` | scaffold `decks/plus/.env` |
| `task xl:install` | venv + app + `streamdeck` from master (idempotent) |
| `task xl:run` | render + run the Plus XL in the foreground |
| `task xl:detect` | list attached decks (type + USB pid) |
| `task xl:regen` | rebuild Plus XL images (restarts the service if loaded) |
| `task xl:env` | scaffold `decks/plus-xl/.env` |
| `task xl:patch` | patch the app for Plus XL touchscreen rendering (see below) |
| `task xl:service` | install + start the login LaunchAgent |
| `task xl:service:status` / `logs` / `restart` / `stop` | service lifecycle |
| `task icons DECK=plus\|plus-xl` / `task icons:all` | just render images |
| `task harden` | host-level hardening/resilience — **Pi only** (needs sudo) |

## USB access (Pi / Plus only)

> The next four sections — USB access, container hardening, run-on-boot and
> resilience — are all about the **Pi's Docker deployment**. None of it applies
> to the Mac, which runs the app natively in the foreground.


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
- Staying on SD: `task harden` installs **`log2ram`** (RAM-backs `/var/log`,
  syncing to disk periodically) to cut card writes. Container logs are already
  size-capped in compose; keep icon rebuilds occasional. Needs a reboot to mount.

**Unattended host patches + time sync** — for an always-on box:

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
timedatectl status   # confirm "System clock synchronized: yes" / NTP active
```

Accurate time matters here: websocket TLS and the long-lived token are
time-sensitive, so a drifting clock shows up as auth/connection failures.

### Pinning the image

Both images — the app **and** the `autoheal` sidecar — are **pinned by digest**
in `docker-compose.yaml` (not `:latest`), so an update has a fixed,
rollback-able reference. The app pin is the multi-arch `latest` manifest (built
from upstream commit `1ad32a4dfb802401bb3f4b9a8130733b4f6b2e2c`); the autoheal
pin is likewise its multi-arch manifest. Both keep the `arm64` the Pi 5 pulls.

To move to a newer build, resolve the new digest and swap it in:

```bash
docker inspect --format '{{index .RepoDigests 0}}' \
  basnijholt/home-assistant-streamdeck-yaml:latest
# -> basnijholt/home-assistant-streamdeck-yaml@sha256:<digest>
```

Note the value is a `sha256:` **registry digest**, not a git commit SHA — only
the former works in `image:`. Bump it deliberately when you want a new version.

## Pages / views

The **Plus** has two pages, and **key 8 is the mode button** on both — a
`next-page` special button. `next-page` wraps (`% len(pages)`), so pressing key 8
cycles Home → Shades → Home; add a third page and the same key cycles through all
of them. The dials swap with the page too, not just the buttons.

The **Plus XL** has one page — 36 keys means everything fits, so it has no mode
key at all.

## Button & dial images (shared renderer)

Neither the buttons nor the dials use the tool's built-in rendering — it can't
shrink the icon, put a label below it, or draw a decent gauge.
[`generate_icons.py`](generate_icons.py) pre-renders every key and dial frame as
a PNG, and each `icon:` field points at the right one, templated on state.

**One renderer, many decks.** The drawing code and palette are shared; each deck's
[`decks/<deck>/spec.py`](decks) supplies only *content* — its key size and which
tiles/dials it wants. Key geometry is expressed relative to a 120px reference and
scaled to the deck (so the Plus's 120px output is unchanged and the XL's 112px is
derived automatically). Add a deck by dropping in a new `decks/<name>/spec.py`.

Dial frames are **identical across both decks**: the Plus strip is 800×100 over 4
dials and the XL's is 1200×100 over 6, so a segment is 200×100 either way and the
same gauge code serves both.

```bash
task icons:all                 # both decks
task icons DECK=plus-xl        # just one
```

| Deck | Key images | Dial frames |
|------|-----------|-------------|
| plus | 25 @ 120×120 | 230 @ 200×100 |
| plus-xl | 55 @ 112×112 | 188 @ 200×100 |

`decks/*/icons/` is git-ignored (build artifact), so render on each machine
before starting; the MDI webfont is fetched once into `.iconbuild/`.

Shared tunables live at the top of the script (`REF_*` key geometry, `STYLES`
palette, `DIAL_STYLES` colours/icons/granularity, `SS` supersample); per-deck
content lives in `spec.py`. After editing either, re-render and restart
(`auto_reload` doesn't watch image files). Adding/renaming a control means
updating both the deck's `spec.py` and its `configuration.yaml` `icon:` path.

### Icon paths differ per deck

A relative `icon:` resolves against the *app's installed assets dir*, not the
working directory — so paths must be **absolute**:

- **Plus (Docker):** `/app/icons/...` — absolute inside the container, which
  mounts `decks/plus/` at `/app`.
- **Plus XL (native):** the real host path,
  `/Users/janvt/dev/jan/home-assistant/streamdeck/decks/plus-xl/icons/...`. This
  is machine-specific by design; if the checkout moves, update the prefix in that
  deck's `configuration.yaml`.

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

# Stream Deck Plus layout (the Pi)

## Home page — buttons (LCD keys)

The eight LCD keys fill left→right, top→bottom, so the `buttons:` list order maps
straight onto the two rows:

| Key | Row | Label | Action |
|-----|-----|-------|--------|
| 1 | top | Chill | toggle `scene.chill` ↔ Living Room off |
| 2 | top | Vinyl | toggle `scene.vinyl` ↔ Living Room off |
| 3 | top | Pain Cave | toggle `scene.pain_cave` ↔ Living Room off |
| 4 | top | Work S | tap: toggle `scene.work_s` ↔ Kitchen off · **hold ~1s: activate `scene.work`** |
| 5 | bottom | Hallway | toggle `light.shellypro1pm_ec62608ad35c_switch_0` (Hallway Spots) |
| 6 | bottom | Outside | toggle `light.balcony_ceiling_light` |
| 7 | bottom | 💩 | trigger `automation.keep_bathroom_fan_on` |
| 8 | bottom | Shades | **mode button** — cycle to the next view |

Key 4 uses a `long_press:` override — a tap runs the normal toggle, a ~1s hold
(`long_press_duration`, default 1.0s) activates `scene.work` instead. Any button
can take a `long_press` with its own `service`/`entity_id`/`target`. Its icon is
three-way: `work_s_on` (desk) when `scene.work_s` is active, a dedicated
`work.png` (briefcase, "Work") when `scene.work` is active, else the grey
`work_s_off` — so you can tell which of the two Work scenes is on.
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

# Stream Deck Plus XL layout (the Mac)

Its own design, not a copy of the Plus: one page, 36 keys in four rows of nine,
plus six dials. See [`decks/plus-xl/spec.py`](decks/plus-xl/spec.py) for the
tiles and [`decks/plus-xl/configuration.yaml`](decks/plus-xl/configuration.yaml)
for the wiring.

| Row | Contents |
|-----|----------|
| 1 | Scenes — Chill, Vinyl, Pain Cave, Work, Work S, Clean, Sleep, then Lights Off + Open All |
| 2 | Room lights — Living Rm, Kitchen, Hallway, Outside, Bedroom, Bathroom, Reading, Record, Signe |
| 3 | Close All, media transport (Play/Prev/Next), TV / Apple TV / Xbox, then both doors |
| 4 | Modes (Guest, Cleaning, Be Smart, Fan), routines (Come Home, Leave, Wake Up), Unlock |

Scenes here simply **activate** (`scene.turn_on`) and highlight from
`input_select.active_scene` — no toggle-off semantics, since the XL has a
dedicated key per room light for turning things off. Doors and Unlock keep the
same `delay: 5` cancel guard as the Plus.

**All six dials are TURN-only, deliberately.** The eager local re-render looks a
dial up by raw list index while being handed the *sorted* index (see the
[live-render caveat](#dials)), so it only works when no dial has a paired PUSH.
Keeping every dial TURN-only means **all six track your finger live**; mixing
paired and unpaired dials would redraw the wrong segment. Mute and area-toggle
belong on keys here — there are 36 of them.

Dials, left to right: Living Room volume, Madagascar volume, LR ceiling
brightness, Kitchen brightness, LR shades, Kitchen shades. Same reversed turn
direction (negative `step`) and inverted shade bar (full = closed) as the Plus.

## Troubleshooting

- **Plus XL touchscreen blank, or only the first dial renders** — two upstream
  bugs, both fixed by [`patch_touchscreen_rotation.py`](decks/plus-xl/patch_touchscreen_rotation.py)
  (`task xl:patch`, pulled in automatically by `xl:run` / `xl:service`, and
  re-applied after `xl:install` since that recreates the venv):
  1. **Rotation ignored** → *whole strip blank.* The Plus XL reports
     `TOUCHSCREEN_ROTATION = 90` and its `set_touchscreen_image()` swaps the
     region geometry for the device (`int_w = height`, `int_h = width`), so the
     JPEG bytes must be rotated too. The app encodes them unrotated, which is
     only correct on a rotation-0 deck like the Plus.
  2. **Partial-region writes don't land** → *only the first dial renders.*
     Verified on hardware: writing each dial's 200×100 region at `x = 200*k`
     only takes effect for `k = 0`. A single full-strip write (rotated,
     `x=0 y=0 1200×100`) renders all six. The patch therefore caches each dial's
     tile and repaints the whole strip on every update.

  Both paths are gated on the deck's reported rotation, so the Plus keeps its
  original per-region behaviour untouched.
- **`OSError: cannot open resource` / `IconWarning: Failed to render icon`** (on
  the Mac, native install) — that's a *font* error, not an image one. The pip/git
  install ships only the `.py` module with **no `assets/` directory**, so the
  app's bundled `Roboto-Regular.ttf` is missing; the Docker image is fine because
  it has the full checkout. Any button with a `text:` key (even `text: ''`) goes
  through the text renderer and trips it. Two defences, both applied: the XL
  config sets **no `text:` keys at all** (labels are baked into the PNGs, and
  `text` defaults to `None`, which skips the font path entirely), and
  `task xl:font` restores the missing font into the venv. Note a
  `special_type: next-page` button *needs* `text: ''` to suppress its default
  "Next Page" label — so if you add one to the XL, run `task xl:font` first.

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

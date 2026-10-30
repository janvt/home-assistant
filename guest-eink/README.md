# Guest room e-ink display

A Waveshare 7.5" 800×480 black/white/red e-paper panel on the Waveshare ESP32
e-Paper driver board, in a wooden face plate and box. It greets the guest by name
in their language, shows the weather, and carries a QR code for the guest Wi-Fi.
The Wi-Fi password rotates on its own whenever the guest changes.

```
┌──────────────────────────────┬──────────────────┐
│ Welcome,                     │  ▄▄▄▄▄  ▄  ▄▄▄▄▄ │
│ Martina                      │  █   █ ▀▄▀ █   █ │
│ ▬▬                           │  (QR, 290 px)    │
│ ☁ 11°  Partly cloudy         │                  │
│        Wind 6 km/h           │ ᯤ SchmatzGuest    │
│ ───────────────────────────  │ Scan with your…  │
│ Tomorrow ☁ 10°/5°  Saturday… │ Password  …      │
└──────────────────────────────┴──────────────────┘
```

| File | What |
|------|------|
| `guest-eink.yaml` | The ESPHome device: Welcome and Message pages plus an alignment test pattern, all text and entities |
| `weather_helpers.h` | HA weather condition → MDI glyph, Wi-Fi QR escaping, empty-state check |
| `i18n.h` | English / Deutsch / Français / Italiano strings, weekday names, weather labels |
| [`../packages/guest_wifi.yaml`](../packages/guest_wifi.yaml) | `rest_command`s for the UniFi OS API on the UDR7 |
| [`../scripts/rotate_guest_wifi_password.yaml`](../scripts/rotate_guest_wifi_password.yaml) | Generates a password, sets it on SchmatzGuest, then on the display |
| [`../automations/guest_wifi_on_guest_name_change.yaml`](../automations/guest_wifi_on_guest_name_change.yaml) | Guest name changes → rotate; cleared → network off, set → network on |

## How it fits together

Home Assistant owns the decisions; the display only renders.

- **Device entities** (on the display's HA device page, kept across reboots):
  Page (Welcome / Message), Guest name, Greeting (empty = the language's
  default), Language, Message, Wi-Fi name, Wi-Fi password, Alignment test
  pattern, Refresh now.
- **Message page:** free text, word-wrapped and centred in the largest of four
  sizes that fits; `|` forces a line break. It stays up until the Page select
  goes back to Welcome. Each page only redraws for changes it shows, so a new
  guest name or a forecast update doesn't cost a refresh while the message is up.
- **Guest name drives everything.** Empty → idle card. Any change → the
  automation switches the display back to the Welcome page, then rotates the
  password; cleared also switches SchmatzGuest off, set
  switches it on *after* the new password is in place. If the rotation fails,
  the script stops with an error and the network stays off, never up with a
  stale password.
- **Rotation** logs into UniFi OS (`/api/auth/login`), takes the `TOKEN` cookie
  and `X-Csrf-Token` header from the response, and `PUT`s only
  `{"x_passphrase": …}` to the WLAN's `wlanconf` entry. The display's Wi-Fi
  password entity is set only once the router answers `meta.rc: ok`.
- **Weather** comes from `weather.altdorf_ur`: current state via `homeassistant`
  sensors, the next two days via `weather.get_forecasts` with
  `capture_response` (the device needs "Allow the device to perform Home
  Assistant actions" in its HA device options).

## Deploying

ESPHome dashboard: `guest-eink.yaml` in `/config/esphome/`, the two headers in
`/config/esphome/guest-eink/`, so the live copy's `includes:` carry a
`guest-eink/` prefix. ESPHome `secrets.yaml` needs `wifi_ssid`, `wifi_password`,
`guest_eink_encryption` and `guest_eink_ap_password`.

Home Assistant: `packages/guest_wifi.yaml` into `/config/packages/`, the script
into `scripts.yaml`, the automation into `automations.yaml`. HA `secrets.yaml`
needs `unifi_login_payload` (the whole JSON login body, see the package header).

## Decision log

- **`epaper_spi`, not `waveshare_epaper`.** The panel says V3, and
  `waveshare_epaper`'s `7.50in-bV3-bwr` allocates one 96 KB buffer that the
  classic ESP32 heap can't give it: null-pointer crash on boot, OTA rollback.
  `epaper_spi`'s `Waveshare-7.5in-bV2-BWR` drives the V3 panel and splits its
  buffer. BUSY is active-low on the UC8179, hence `inverted: true`.
- **"No sign of life" was the ribbon**, inserted contacts-away from the
  connector springs. Not the driver, not the busy polarity.
- **Every update is a full ~19 s refresh.** The 3-colour panel has no partial
  mode, so updates are coalesced (`queue_refresh`, 3 s) and the weather redraws
  only every 30 min and only when a guest is shown.
- **`glyphs:` replaces the default charset**, so every text font names a
  glyphset (`GF_Latin_Core`, for the four languages) and `glyphs:` only adds
  extras like `°`.
- **Weekday names come from a table**, not `strftime`: ESPHome's C library only
  has the C locale.
- **QR at fixed 10 px modules, version 3.** SSID + password must stay within 53
  bytes of payload; the script's word lists are sized for that and
  `tests/test_guest_wifi.py` checks the worst case.
- **UniFi session login, not an API key.** The local Network Integrations key
  was refused (401) on both the internal and the integration API paths; the
  existing `homeass` router user works. It is a Super Admin today; a
  Network-only role would be enough.
- **Rotate on any name change**, including a typo fix: deliberate, and it kicks
  the current guest off the Wi-Fi.

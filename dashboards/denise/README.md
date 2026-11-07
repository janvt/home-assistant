# Denise's dashboard

The **Denise** dashboard (`/dashboard-denise/home`) is the default for
Denise's login. She lives in Altdorf, not here, and isn't into the technical
side, so it's in German and says things in plain sentences instead of sensors
and graphs. There are no controls for any room. It isn't in the sidebar; she
gets it as her default (her **Profile → Appearance → Dashboard**, set while
logged in as her, not **Set as default** in Settings → Dashboards, which
changes it for everyone on Auto). Set her profile's **Language** to Deutsch
too: the forecast cards follow it.

It's full screen: kiosk-mode (HACS) hides the header and the sidebar
(`KIOSK` in `build.py`). Open it with `?disable_km` on the URL to edit it in
the UI or get the sidebar back.

- **Greeting:** "Guten Abend, Denise", the weather now and today in one line,
  and whether the Axenstrasse is open. Under it, her alerts (Hinweise) as
  icons with their names, only while one is on; otherwise "Keine Hinweise:
  alles ruhig". Tapping one opens the **Hinweise** page with a line on each.
- **Wetter in Altdorf:** a MeteoSwiss warning while there is one, then the
  daily and the hourly forecast.
- **Föhn:** one sentence (blowing, a little, coming, strong föhn coming, or
  none), wind and gusts, and what föhn is.
- **Axenstrasse:** open, or closed and until when; how the traffic is moving
  (flüssig, zähflüssig, Stau, from the speeds counted at Sisikon) and how many
  vehicles an hour each way; and the closures announced, with FEDRO's own
  German for what's closed. The integration's calendar titles are English,
  so the list comes from the next-closure sensor instead of a calendar card.

| File | What |
|------|------|
| [`build.py`](build.py) | Builds the whole dashboard config, with entity names from the Weather, Infrastructure and Mobile alerts builders. Pure functions. |
| [`sync.py`](sync.py) | Creates the dashboard if needed (not in the sidebar) and pushes it. |

## Her alerts

They're the integration's own `binary_sensor.pill_<key>`, the ones on the
Mobile dashboard, picked by key; there's no second set of sensors. Their
German names and lines are in `DE` in `build.py` (pills.py stays English), and
`DE` is also the list of which pills she gets. So:

- a pill switched off in the integration's options (Choose alerts) is gone
  from her dashboard too;
- dismissing is shared, so her cards have no hold action, and a pill Jan
  dismissed still shows for her;
- her row has one chip per pill, not the Mobile row's fixed slots. With a
  short list, few are on at once; with many, the chips wrap.

To change her set, add or remove an entry in `DE` and sync. A key that isn't
in `pills.py` fails the tests, and so does a sentence that stops rendering.

```bash
.venv-test/bin/python dashboards/denise/sync.py            # dry run
.venv-test/bin/python dashboards/denise/sync.py --apply
```

It uses the same `dashboards/.env` as the other dashboards. **The script owns
this dashboard:** a card added in the HA UI is gone after the next `--apply`.

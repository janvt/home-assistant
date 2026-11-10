# Health dashboard

The **Health** dashboard (`/dashboard-health/score`) shows the
[Global Health Score](https://github.com/HA-Pulse/home-assistant-global-health-score)
(HAGHS, installed through HACS) with the integration's own **Pro** card: the
score and its formula, the Advisor's recommendations, repairs and failed
integrations (each linked), pending updates, recorder and database, stale and
zombie entities, dead and empty devices. Next to it: 30 days of the score, and
the hardware and application sub-scores.

It isn't in the sidebar. The **HA health low** pill on the Mobile dashboard
opens it (below 85 %): tap its card on the Alerts page.

| File | What |
|------|------|
| [`pro.yaml`](pro.yaml) | HAGHS's Pro card, copied unchanged from its `docs/cards/pro.yaml` at the installed release. |
| [`build.py`](build.py) | Builds the whole dashboard config around it. `LINK` is the path the pill uses; `PRO_CARD_RELEASE` the release `pro.yaml` comes from. |
| [`sync.py`](sync.py) | Creates the dashboard if needed (not in the sidebar) and pushes it. |

```bash
task sync:health              # dry run
task sync:health -- --apply   # create and save
```

When HACS updates HAGHS, copy the new release's `docs/cards/pro.yaml` over
`pro.yaml`, bump `PRO_CARD_RELEASE`, run the tests and sync.

# Denise's dashboard: the VPN section

Denise's dashboard (`/dashboard-denise/home`) is edited in the HA UI and isn't
kept here, except for one section: **VPN**, at the end of the first view, in
German like the rest. It shows:

- a banner for the month's free AWS egress: green, then blue from 50 %,
  yellow from 80 %, red once the free 100 GB are used up (with how far over);
- the allowance gauge, with the VPN dashboard's colours;
- her own traffic ("Du, diesen Monat", her WireGuard peer) and everyone's
  ("Alle zusammen");
- the pace to the end of the month, and 30 days of history.

| File | What |
|------|------|
| [`build.py`](build.py) | The section, and `apply()`, which swaps it into the dashboard. Entities, the free allowance and the colour steps come from [`../vpn/build.py`](../vpn/build.py). |
| [`sync.py`](sync.py) | Reads the dashboard from HA, swaps the section in, saves it. |

```bash
task sync:denise              # dry run
task sync:denise -- --apply   # save
```

`apply()` finds the section by its heading, **VPN**. It replaces the section
where it is, so it stays put if you move it in the UI, and adds it at the end
of the first view when it's missing. Every other section, the Hinweise view
and the kiosk mode settings are saved back exactly as HA had them. Don't edit
the VPN section in the UI: the next sync puts it back. Renaming its heading
makes the sync add a second one.

The old config goes to `backups/` (ignored by git) before each save.

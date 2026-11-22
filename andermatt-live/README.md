# Andermatt Live

A Home Assistant integration for the lifts, slopes, snow and car parks of
**Andermatt+Sedrun+Disentis**, read from the resort's
[A+S+D Live Dashboard](https://beta.andermatt-sedrun-disentis.ch).

Not affiliated with Andermatt-Sedrun Sport AG. The dashboard has no API: its
pages are read the way a browser gets them, three per sector every 10 minutes.
The site is a beta and can change; the live checks (below) notice when it does.

## Entities

One device per sector (Gemsstock, Andermatt-Oberalppass, Oberalppass-Dieni,
Sedrun, Disentis), with:

| Entity | What |
|---|---|
| *Open* | On while at least one of the sector's lifts runs |
| A binary sensor per lift, e.g. *15 Gemsstock-Bahn* | Open or closed, with `number`, `kind`, `status`, `first_ride` and `last_ride` |
| A binary sensor per slope, e.g. *70 Sonnenpiste* | Off by default (up to 30 per sector); open or closed, with `difficulty` (blue, red, black, freeride) and `length` in m |
| *Lifts open*, *Slopes open* | Counts, with the `total` |
| *Slopes open length* | In km, with the `total` |
| *Snow depth*, *New snow 24 h* | cm, as the resort reports them |
| A sensor per car park, e.g. *PP Gemsstock/Nordic* | `free` or `full` (full or closed), with the site's `text` |

Whether something is open comes from the status class of its row on the site,
not from its German label. A lift or slope the site stops listing becomes
unavailable; one it adds appears after a reload. When the site can't be read,
everything is unavailable rather than closed.

## Setup

Choose the sectors when adding the integration (Gemsstock and
Andermatt-Oberalppass are suggested); change them later under *Configure*.

## Installing

HACS installs only Alert Pills from this repository (`custom_components/` at
its root), so this one is copied over SSH: `scripts/deploy.sh` (settings in
`.deploy.env`, from `.deploy.env.example`) copies it to Home Assistant, checks
the configuration before swapping the files in, and offers to restart.

## Development

From the repository root:

```bash
task test:andermatt-live        # against saved pages, in its own venv
task test:andermatt-live:live   # against the real site
```

`tests/fixtures` holds pages saved from the site on 22 November 2026, when only
Gemsstock was open. The *Andermatt Live checks* workflow runs `tests_live`
twice a day and opens an issue (label `andermatt-live-checks`) when it fails.

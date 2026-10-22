"""Push the Trains debug dashboard to Home Assistant.

    python sync.py            show what would change, change nothing
    python sync.py --apply    create the dashboard if needed, enable the
                              Frigate diagnostics it uses, create the
                              timetable helpers, push the matching
                              automation, save the dashboard

The timetable boards themselves are REST sensors, pasted into HA's
configuration once from ha-timetable.yaml: the sync only warns when they're
missing. The helpers it creates keep the values set in HA.

The old config goes to backups/ first. Like the Weather sync, it refuses to
save a dashboard naming an entity HA doesn't have (`--allow-missing` overrides).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
from pathlib import Path

import build
import timetable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ha_client import HA, load_env, save_dashboard, states  # noqa: E402

ENTITY = re.compile(r"\b(?:sensor|binary_sensor|camera|image|switch|number|update|input_number|input_text)"
                    r"\.[a-z0-9_]+")


def referenced(config: dict) -> set[str]:
    return set(ENTITY.findall(json.dumps(config)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="change Home Assistant (default: dry run)")
    parser.add_argument("--allow-missing", action="store_true", help="save even if entities are missing")
    args = parser.parse_args()
    ha = HA(load_env())

    if not any(d["url_path"] == build.DASHBOARD for d in ha.call({"type": "lovelace/dashboards/list"})):
        print(f"create {build.DASHBOARD} ({build.TITLE})")
        if not args.apply:
            print("Run with --apply to create and save it.")
            return
        ha.call({"type": "lovelace/dashboards/create", "url_path": build.DASHBOARD, "title": build.TITLE,
                 "icon": build.ICON, "mode": "storage", "require_admin": True, "show_in_sidebar": True})

    # Enabled entities only get a state once HA reloads the Frigate entry, about
    # 30 s later, so count them as present.
    enable = [e["entity_id"] for e in ha.call({"type": "config/entity_registry/list"})
              if e["entity_id"] in build.DISABLED_BY_DEFAULT and e.get("disabled_by")]
    for entity in enable:
        print(f"enable {entity}")
        if args.apply:
            ha.call({"type": "config/entity_registry/update", "entity_id": entity, "disabled_by": None})

    have = set(states(ha))
    missing_boards = [b for b in timetable.BOARDS + [timetable.PAST] if b not in have]
    if missing_boards:
        print("timetable sensors missing (paste ha-timetable.yaml into HA's configuration, restart):\n  "
              + "\n  ".join(missing_boards))
    for number in timetable.NUMBERS:
        if number["entity"] not in have:
            print(f"create {number['entity']}")
            if args.apply:
                ha.call({"type": "input_number/create", **{k: v for k, v in number.items() if k != "entity"}})
    for text in timetable.TEXTS:
        if text["entity"] not in have:
            print(f"create {text['entity']}")
            if args.apply:
                ha.call({"type": "input_text/create", **{k: v for k, v in text.items() if k != "entity"}})
    path = f"/api/config/automation/config/{timetable.AUTOMATION_ID}"
    try:
        current = ha.rest("GET", path)
    except urllib.error.HTTPError:
        current = None
    if current != timetable.automation():
        print(f"{'update' if current else 'create'} automation {timetable.AUTOMATION_ID}")
        if args.apply:
            ha.rest("POST", path, timetable.automation())
    # Created a moment ago: count them as present.
    created = {h["entity"] for h in timetable.NUMBERS + timetable.TEXTS}

    new = build.build()
    missing = sorted(referenced(new) - set(states(ha)) - set(enable) - created - set(missing_boards))
    if missing:
        print("entities the dashboard uses but Home Assistant doesn't have:\n  " + "\n  ".join(missing))
        if args.apply and not args.allow_missing:
            sys.exit("not saved: fix build.py, or pass --allow-missing")

    try:
        old = ha.call({"type": "lovelace/config", "url_path": build.DASHBOARD, "force": True})
    except RuntimeError:  # created a moment ago, never saved
        old = {}
    if new == old:
        print(f"{build.DASHBOARD} already matches build.py")
    elif args.apply:
        save_dashboard(ha, build.DASHBOARD, old, new, HERE / "backups")
        print(f"saved {build.DASHBOARD}")
    else:
        print(f"{build.DASHBOARD} would change. Run with --apply to save it.")


if __name__ == "__main__":
    main()

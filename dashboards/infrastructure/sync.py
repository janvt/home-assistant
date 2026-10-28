"""Push the Infrastructure dashboard to Home Assistant.

    python sync.py            show what would change, change nothing
    python sync.py --apply    create the dashboard if needed, save it

The old config goes to backups/ first. Like the other syncs, it refuses to
save a dashboard naming an entity HA doesn't have (`--allow-missing` overrides).
It also refuses to drop a view made in the HA UI, which build.py doesn't make
(`--drop-views` overrides): put it in build.py first, as passes.json is.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import build

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ha_client import HA, load_env, save_dashboard, states  # noqa: E402

ENTITY = re.compile(r"\b(?:sensor|binary_sensor|camera|update|calendar)\.[a-z0-9_]+")


def dropped_views(old: dict, new: dict) -> list[str]:
    """The views HA has that the new config doesn't: made in the UI, and lost
    on saving."""
    keep = {view.get("path") for view in new.get("views", [])}
    return [view.get("path") or view.get("title", "?") for view in old.get("views", [])
            if view.get("path") not in keep]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="change Home Assistant (default: dry run)")
    parser.add_argument("--allow-missing", action="store_true", help="save even if entities are missing")
    parser.add_argument("--drop-views", action="store_true", help="save even if it drops views made in the UI")
    args = parser.parse_args()
    ha = HA(load_env())

    if not any(d["url_path"] == build.DASHBOARD for d in ha.call({"type": "lovelace/dashboards/list"})):
        print(f"create {build.DASHBOARD} ({build.TITLE})")
        if not args.apply:
            print("Run with --apply to create and save it.")
            return
        ha.call({"type": "lovelace/dashboards/create", "url_path": build.DASHBOARD, "title": build.TITLE,
                 "icon": build.ICON, "mode": "storage", "require_admin": False, "show_in_sidebar": True})

    new = build.build()
    missing = sorted(set(ENTITY.findall(json.dumps(new))) - set(states(ha)))
    if missing:
        print("entities the dashboard uses but Home Assistant doesn't have:\n  " + "\n  ".join(missing))
        if args.apply and not args.allow_missing:
            sys.exit("not saved: fix build.py, or pass --allow-missing")

    try:
        old = ha.call({"type": "lovelace/config", "url_path": build.DASHBOARD, "force": True})
    except RuntimeError:  # created a moment ago, never saved
        old = {}
    if dropped := dropped_views(old, new):
        print("views in Home Assistant that build.py doesn't make (made in the UI?):\n  " + "\n  ".join(dropped))
        if args.apply and not args.drop_views:
            sys.exit("not saved: add them to build.py first, or pass --drop-views")
    if new == old:
        print(f"{build.DASHBOARD} already matches build.py")
    elif args.apply:
        save_dashboard(ha, build.DASHBOARD, old, new, HERE / "backups")
        print(f"saved {build.DASHBOARD}")
    else:
        print(f"{build.DASHBOARD} would change. Run with --apply to save it.")


if __name__ == "__main__":
    main()

"""Push the Weather dashboard to Home Assistant.

    python sync.py            show whether it would change, change nothing
    python sync.py --apply    save it (the old config goes to backups/ first)

River sensors are renamed to their stable ids first (see RIVERS in
locations.py). Refuses to save a dashboard that names an entity Home Assistant doesn't have:
a renamed sensor would otherwise just leave an "Entity not available" card.
`--allow-missing` overrides that, e.g. for a station that is down for good.
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

ENTITY = re.compile(r"\b(?:sensor|binary_sensor|weather|camera|image)\.[a-z0-9_]+")


def referenced(config: dict) -> set[str]:
    return set(ENTITY.findall(json.dumps(config)))


def river_renames(ha: HA) -> list[tuple[str, str]]:
    """(current, wanted) entity ids of river sensors that don't have their
    stable name yet. HA gives them "<river>_<condition>[_2]" in load order."""
    wanted = {f"{r['station']}_{c}": build.river_entity(r, c) for r in build.RIVERS for c in r["conditions"]}
    return [(e["entity_id"], wanted[e["unique_id"]])
            for e in ha.call({"type": "config/entity_registry/list"})
            if e["platform"] == "swiss_hydrological_data" and e.get("unique_id") in wanted
            and e["entity_id"] != wanted[e["unique_id"]]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="change Home Assistant (default: dry run)")
    parser.add_argument("--allow-missing", action="store_true", help="save even if entities are missing")
    args = parser.parse_args()
    ha = HA(load_env())

    for current, wanted in river_renames(ha):
        print(f"rename {current} -> {wanted}")
        if args.apply:
            ha.call({"type": "config/entity_registry/update", "entity_id": current, "new_entity_id": wanted})

    new = build.build()
    missing = sorted(referenced(new) - set(states(ha)))
    if missing:
        print("entities the dashboard uses but Home Assistant doesn't have:\n  " + "\n  ".join(missing))
        if args.apply and not args.allow_missing:
            sys.exit("not saved: fix locations.py, or pass --allow-missing")

    old = ha.call({"type": "lovelace/config", "url_path": build.DASHBOARD, "force": True})
    if new == old:
        print(f"{build.DASHBOARD} already matches build.py")
    elif args.apply:
        save_dashboard(ha, build.DASHBOARD, old, new, HERE / "backups")
        print(f"saved {build.DASHBOARD}")
    else:
        print(f"{build.DASHBOARD} would change. Run with --apply to save it.")


if __name__ == "__main__":
    main()

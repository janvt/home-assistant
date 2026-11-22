"""Push the VPN section of Denise's dashboard to Home Assistant.

    python sync.py            show what would change, change nothing
    python sync.py --apply    save it

Only the VPN section changes; the rest of the dashboard is edited in the UI.
The old config goes to backups/ first. Like the other syncs, it refuses to
save a section naming an entity HA doesn't have (`--allow-missing` overrides).
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

ENTITY = re.compile(r"\b(?:sensor|input_number|input_select|automation)\.[a-z0-9_]+")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="change Home Assistant (default: dry run)")
    parser.add_argument("--allow-missing", action="store_true", help="save even if entities are missing")
    args = parser.parse_args()
    ha = HA(load_env())

    missing = sorted(set(ENTITY.findall(json.dumps(build.section()))) - set(states(ha)))
    if missing:
        print("entities the section uses but Home Assistant doesn't have:\n  " + "\n  ".join(missing))
        if args.apply and not args.allow_missing:
            sys.exit("not saved: fix build.py, or pass --allow-missing")

    old = ha.call({"type": "lovelace/config", "url_path": build.DASHBOARD, "force": True})
    new = build.apply(old)
    if new == old:
        print(f"{build.DASHBOARD} already matches build.py")
    elif args.apply:
        save_dashboard(ha, build.DASHBOARD, old, new, HERE / "backups")
        print(f"saved {build.DASHBOARD}")
    else:
        verb = "change" if any(build.is_ours(s) for s in old["views"][0].get("sections", [])) else "add"
        print(f"would {verb} the {build.HEADING} section of {build.DASHBOARD}. Run with --apply to save it.")


if __name__ == "__main__":
    main()

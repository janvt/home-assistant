"""Push `pills.py` to Home Assistant: the pill helpers and the Mobile dashboard.

    python sync.py            show what would change, change nothing
    python sync.py --apply    create or update helpers, then save the dashboard

Connection settings come from `dashboards/.env` (see `ha_client.py`).

Helpers are UI template helpers, so they are config entries: a missing pill is
created through the template config flow, an existing one is updated through
its options flow when its template differs. Before the dashboard is saved, the
config HA had is written to `backups/` (git-ignored).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import build

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ha_client import HA, load_env, save_dashboard  # noqa: E402

HERE = Path(__file__).resolve().parent
COUNT_TEMPLATE = ("{{ states.binary_sensor | selectattr('entity_id','match','binary_sensor\\\\.pill_')"
                  " | selectattr('state','eq','on') | list | count }}")


def helper_title(key: str) -> str:
    """A title HA slugifies back to `pill_<key>`, so the entity id is predictable."""
    return "Pill " + key.replace("_", " ")


def current_template(ha: HA, entry_id: str) -> tuple[str, str]:
    """(flow id, template) of an open options flow on a template helper."""
    flow = ha.rest("POST", "/api/config/config_entries/options/flow", {"handler": entry_id})
    field = next(f for f in flow["data_schema"] if f["name"] == "state")
    return flow["flow_id"], (field.get("description") or {}).get("suggested_value", "")


def sync_helper(ha: HA, entry_id: str | None, kind: str, title: str, template: str,
                extra: dict[str, Any], apply: bool) -> str:
    if entry_id is None:
        if apply:
            flow = ha.rest("POST", "/api/config/config_entries/flow", {"handler": "template"})
            ha.rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", {"next_step_id": kind})
            ha.rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}",
                    {"name": title, "state": template, **extra})
        return "create"
    flow_id, now = current_template(ha, entry_id)
    if now == template:
        ha.rest("DELETE", f"/api/config/config_entries/options/flow/{flow_id}")
        return "same"
    if apply:
        ha.rest("POST", f"/api/config/config_entries/options/flow/{flow_id}", {"state": template, **extra})
    else:
        ha.rest("DELETE", f"/api/config/config_entries/options/flow/{flow_id}")
    return "update"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="change Home Assistant (default: dry run)")
    args = parser.parse_args()
    ha = HA(load_env())

    registry = {e["entity_id"]: e.get("config_entry_id") for e in ha.call({"type": "config/entity_registry/list"})}
    changes = []
    for pill in build.ALERTS:
        what = sync_helper(ha, registry.get(build.entity(pill)), "binary_sensor", helper_title(pill["key"]),
                           pill["tmpl"], {}, args.apply)
        if what != "same":
            changes.append(f"{what} {build.entity(pill)}")
    what = sync_helper(ha, registry.get(build.COUNT), "sensor", "Weather alerts active", COUNT_TEMPLATE,
                       {"state_class": "measurement"}, args.apply)
    if what != "same":
        changes.append(f"{what} {build.COUNT}")

    if args.apply:
        # A just-created helper's entity id is HA's slug of its title: check it.
        registry = {e["entity_id"] for e in ha.call({"type": "config/entity_registry/list"})}
        missing = [build.entity(p) for p in build.ALERTS if build.entity(p) not in registry]
        if missing:
            sys.exit(f"created helpers did not get the expected entity ids: {missing}")

    old = ha.call({"type": "lovelace/config", "url_path": build.DASHBOARD, "force": True})
    new = build.apply(old)
    if new != old:
        changes.append(f"save {build.DASHBOARD}")
        if args.apply:
            save_dashboard(ha, build.DASHBOARD, old, new, HERE / "backups")

    print("\n".join(changes) if changes else "everything already matches pills.py")
    if changes and not args.apply:
        print("dry run: nothing changed. Run with --apply to make these changes.")


if __name__ == "__main__":
    main()

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
import urllib.error
from pathlib import Path
from typing import Any

import build

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ha_client import HA, load_env, save_dashboard  # noqa: E402

HERE = Path(__file__).resolve().parent
# The count helper counts shown pills: on, and not dismissed (see build.SHOWN).


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
    for helper in build.TEMPLATES:
        what = sync_helper(ha, registry.get(helper["entity"]), helper["kind"], helper["name"], helper["tmpl"],
                           helper.get("extra", {}), args.apply)
        if what != "same":
            changes.append(f"{what} {helper['entity']}")
    what = sync_helper(ha, registry.get(build.COUNT), "sensor", "Weather alerts active", build.COUNT_TEMPLATE,
                       {"state_class": "measurement"}, args.apply)
    if what != "same":
        changes.append(f"{what} {build.COUNT}")

    have = {s["entity_id"] for s in ha.call({"type": "get_states"})}
    for number in build.NUMBERS:
        if number["entity"] not in have:
            changes.append(f"create {number['entity']}")
            if args.apply:
                fields = {k: v for k, v in number.items() if k != "entity"}
                ha.call({"type": "input_number/create", **fields})

    for pill in build.ALERTS:
        d = build.dismissed_entity(pill)
        if build.dismissable(pill) and d not in have:
            changes.append(f"create {d}")
            if args.apply:
                ha.call({"type": "input_datetime/create", "name": f"Pill {pill['key'].replace('_', ' ')} dismissed",
                         "has_date": True, "has_time": True, "icon": "mdi:bell-off-outline"})
                # A new helper starts at today 00:00, which would count a pill that
                # has been on since before midnight as dismissed. Start at "never".
                ha.call({"type": "call_service", "domain": "input_datetime", "service": "set_datetime",
                         "target": {"entity_id": d}, "service_data": {"timestamp": 0}})

    try:
        current = ha.rest("GET", f"/api/config/script/config/{build.TOGGLE_SCRIPT}")
    except urllib.error.HTTPError:
        current = None
    if current != build.SCRIPT:
        changes.append(f"{'update' if current else 'create'} script.{build.TOGGLE_SCRIPT}")
        if args.apply:
            ha.rest("POST", f"/api/config/script/config/{build.TOGGLE_SCRIPT}", build.SCRIPT)

    for stat in build.STATISTICS:
        if stat["entity"] not in have:
            changes.append(f"create {stat['entity']}")
            if args.apply:
                flow = ha.rest("POST", "/api/config/config_entries/flow", {"handler": "statistics"})
                url = f"/api/config/config_entries/flow/{flow['flow_id']}"
                ha.rest("POST", url, {"name": stat["name"], "entity_id": stat["source"]})
                ha.rest("POST", url, {"state_characteristic": stat["characteristic"]})
                ha.rest("POST", url, {"entity_id": stat["source"], "state_characteristic": stat["characteristic"],
                                      "sampling_size": stat["sampling_size"], "max_age": stat["max_age"],
                                      "keep_last_sample": False, "precision": stat["precision"]})

    for stat in build.HISTORY_STATS:
        period = {"start": stat["start"], "end": stat["end"], "state_class": stat["state_class"]}
        if stat["entity"] not in have:
            changes.append(f"create {stat['entity']}")
            if args.apply:
                flow = ha.rest("POST", "/api/config/config_entries/flow", {"handler": "history_stats"})
                url = f"/api/config/config_entries/flow/{flow['flow_id']}"
                ha.rest("POST", url, {"name": stat["name"], "entity_id": stat["source"], "type": stat["type"]})
                ha.rest("POST", url, {"state": stat["state"]})
                ha.rest("POST", url, period)
            continue
        flow = ha.rest("POST", "/api/config/config_entries/options/flow", {"handler": registry[stat["entity"]]})
        url = f"/api/config/config_entries/options/flow/{flow['flow_id']}"
        now = {f["name"]: (f.get("description") or {}).get("suggested_value") for f in flow["data_schema"]}
        if all(now.get(k) == v for k, v in period.items()):
            ha.rest("DELETE", url)
            continue
        changes.append(f"update {stat['entity']}")
        if args.apply:
            ha.rest("POST", url, {"state": stat["state"], "type": stat["type"], **period})
        else:
            ha.rest("DELETE", url)

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

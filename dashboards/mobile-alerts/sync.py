"""Push `pills.py` to Home Assistant: the pills, their helpers and the Mobile dashboard.

    python sync.py            show what would change, change nothing
    python sync.py --apply    load the pills, create or update helpers, then save the dashboard

Connection settings come from `dashboards/.env` (see `ha_client.py`).

The pills go to the `alert_pills` integration (installed through HACS from this
repo) with its `alert_pills.load` service. The few helpers some pills read are
UI helpers, so they are config entries: a missing one is created through its
config flow, an existing template helper is updated through its options flow
when its template differs. Before the dashboard is saved, the config HA had is
written to `backups/` (git-ignored).

The "No alert pills" label (`IGNORE_LABEL` in pills.py) is created on the first
`--apply`, with the phones in it. After that the sync leaves it alone: who has
it is set in HA.

The pills used to be template helpers with an `input_datetime` and a script for
dismissing; the first `--apply` removes those so the integration's entities get
the same entity ids.
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
OLD_SCRIPT = "pill_toggle_dismiss"
INSTALL = ("the alert_pills integration isn't installed: in HACS, add https://github.com/janvt/home-assistant "
           "as a custom repository (type Integration), download Alert Pills and restart Home Assistant")


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


def ensure_entry(ha: HA, apply: bool) -> bool:
    """Whether the integration has its config entry, creating it on --apply."""
    if ha.call({"type": "config_entries/get", "domain": build.DOMAIN}):
        return True
    if not apply:
        return False
    try:
        ha.rest("POST", "/api/config/config_entries/flow", {"handler": build.DOMAIN})
    except urllib.error.HTTPError:
        sys.exit(INSTALL)
    return True


def remove_old_helpers(ha: HA, registry: list[dict[str, Any]], apply: bool) -> list[str]:
    """The template helpers, dismiss helpers and script the integration replaces."""
    changes = []
    pills = {build.entity(p) for p in build.ALERTS} | {build.COUNT}
    for e in registry:
        if e["entity_id"] in pills and e["platform"] == "template":
            changes.append(f"remove template helper {e['entity_id']}")
            if apply:
                ha.rest("DELETE", f"/api/config/config_entries/entry/{e['config_entry_id']}")
        elif (e["platform"] == "input_datetime" and e["entity_id"].startswith("input_datetime.pill_")
              and e["entity_id"].endswith("_dismissed")):
            changes.append(f"remove {e['entity_id']}")
            if apply:
                ha.call({"type": "input_datetime/delete", "input_datetime_id": e["unique_id"]})
    try:
        ha.rest("GET", f"/api/config/script/config/{OLD_SCRIPT}")
    except urllib.error.HTTPError:
        pass
    else:
        changes.append(f"remove script.{OLD_SCRIPT}")
        if apply:
            ha.rest("DELETE", f"/api/config/script/config/{OLD_SCRIPT}")
    return changes


def load_pills(ha: HA, apply: bool) -> list[str]:
    reply = ha.call({"type": "call_service", "domain": build.DOMAIN, "service": "load",
                     "service_data": {**build.definitions(), "dry_run": not apply}, "return_response": True})
    diff = reply["response"]
    changes = [f"{what} pill {key}" for what in ("added", "removed", "changed") for key in diff[what]]
    if diff["order_changed"] and not changes:
        changes.append("reorder pills")
    return changes


def ensure_ignore_label(ha: HA, registry: list[dict[str, Any]], apply: bool) -> list[str]:
    """Create the "No alert pills" label once, with the phones in it.

    Only when the label is missing: after that, who has it is set in HA (on
    the phone), and a sync must not undo that."""
    if any(label["label_id"] == build.IGNORE_LABEL for label in ha.call({"type": "config/label_registry/list"})):
        return []
    changes = [f"create label {build.IGNORE_LABEL_NAME!r}"]
    labels = {e["entity_id"]: e.get("labels", []) for e in registry}
    tagged = [e for e in build.IGNORED_AT_FIRST if e in labels]
    changes += [f"label {e} {build.IGNORE_LABEL_NAME!r}" for e in tagged]
    if apply:
        made = ha.call({"type": "config/label_registry/create", "name": build.IGNORE_LABEL_NAME,
                        "icon": "mdi:bell-off-outline"})
        if made["label_id"] != build.IGNORE_LABEL:
            sys.exit(f"HA named the label {made['label_id']!r}, the pills look for {build.IGNORE_LABEL!r}")
        for e in tagged:
            ha.call({"type": "config/entity_registry/update", "entity_id": e,
                     "labels": [*labels[e], build.IGNORE_LABEL]})
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="change Home Assistant (default: dry run)")
    args = parser.parse_args()
    ha = HA(load_env())

    has_entry = ensure_entry(ha, args.apply)
    registry_list = ha.call({"type": "config/entity_registry/list"})
    changes = remove_old_helpers(ha, registry_list, args.apply)
    changes += ensure_ignore_label(ha, registry_list, args.apply)
    if has_entry:
        changes += load_pills(ha, args.apply)
    else:
        changes.append(f"set up {build.DOMAIN} and load {len(build.ALERTS)} pills")

    registry = {e["entity_id"]: e.get("config_entry_id") for e in registry_list}
    for helper in build.TEMPLATES:
        what = sync_helper(ha, registry.get(helper["entity"]), helper["kind"], helper["name"], helper["tmpl"],
                           helper.get("extra", {}), args.apply)
        if what != "same":
            changes.append(f"{what} {helper['entity']}")

    have = {s["entity_id"] for s in ha.call({"type": "get_states"})}
    for number in build.NUMBERS:
        if number["entity"] not in have:
            changes.append(f"create {number['entity']}")
            if args.apply:
                fields = {k: v for k, v in number.items() if k != "entity"}
                ha.call({"type": "input_number/create", **fields})
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
        # The pills must have taken over the old helpers' entity ids.
        mine = {e["entity_id"] for e in ha.call({"type": "config/entity_registry/list"})
                if e["platform"] == build.DOMAIN}
        missing = [build.entity(p) for p in build.ALERTS if build.entity(p) not in mine]
        if missing or build.COUNT not in mine:
            sys.exit(f"the pills did not get the expected entity ids: {missing or [build.COUNT]}")

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

"""Push `pills.py` to Home Assistant: the pill helpers and the Mobile dashboard.

    python sync.py            show what would change, change nothing
    python sync.py --apply    create or update helpers, then save the dashboard

Reads HASS_HOST, WEBSOCKET_PROTOCOL and HASS_TOKEN from `.env` next to this
file (copy `.env.example`), the same three settings the Stream Decks use.

Helpers are UI template helpers, so they are config entries: a missing pill is
created through the template config flow, an existing one is updated through
its options flow when its template differs. Before the dashboard is saved, the
config HA had is written to `backups/` (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from websockets.sync.client import connect

import build

HERE = Path(__file__).resolve().parent
COUNT_TEMPLATE = ("{{ states.binary_sensor | selectattr('entity_id','match','binary_sensor\\\\.pill_')"
                  " | selectattr('state','eq','on') | list | count }}")


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        sys.exit(f"{path} is missing: copy .env.example and fill in the token")
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def helper_title(key: str) -> str:
    """A title HA slugifies back to `pill_<key>`, so the entity id is predictable."""
    return "Pill " + key.replace("_", " ")


class HA:
    def __init__(self, env: dict[str, str]) -> None:
        ws = env.get("WEBSOCKET_PROTOCOL", "ws")
        host = env["HASS_HOST"]
        self.base = f"{'https' if ws == 'wss' else 'http'}://{host}"
        self.headers = {"Authorization": f"Bearer {env['HASS_TOKEN']}", "Content-Type": "application/json"}
        self.ws = connect(f"{ws}://{host}/api/websocket", max_size=None)
        self.ws.recv()
        self.ws.send(json.dumps({"type": "auth", "access_token": env["HASS_TOKEN"]}))
        if json.loads(self.ws.recv()).get("type") != "auth_ok":
            sys.exit("Home Assistant rejected the token")
        self._id = 0

    def call(self, msg: dict[str, Any]) -> Any:
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, **msg}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self._id:
                if not reply.get("success"):
                    raise RuntimeError(f"{msg['type']}: {reply.get('error')}")
                return reply.get("result")

    def rest(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        req = urllib.request.Request(self.base + path, method=method, headers=self.headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode()
        return json.loads(text) if text else None


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
    ha = HA(load_env(HERE / ".env"))

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
            backups = HERE / "backups"
            backups.mkdir(exist_ok=True)
            (backups / f"{build.DASHBOARD}-{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(
                json.dumps(old, indent=1, ensure_ascii=False))
            ha.call({"type": "lovelace/config/save", "url_path": build.DASHBOARD, "config": new})

    print("\n".join(changes) if changes else "everything already matches pills.py")
    if changes and not args.apply:
        print("dry run: nothing changed. Run with --apply to make these changes.")


if __name__ == "__main__":
    main()

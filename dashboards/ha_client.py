"""Talking to Home Assistant, shared by the dashboard sync scripts.

Settings come from `dashboards/.env` (copy `.env.example`): HASS_HOST,
WEBSOCKET_PROTOCOL and HASS_TOKEN, the same three the Stream Decks use. The
websocket carries dashboards and registries; config and options flows only
exist over REST, so `rest()` uses http/https to match the websocket.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from websockets.sync.client import connect

ENV = Path(__file__).resolve().parent / ".env"


def load_env(path: Path = ENV) -> dict[str, str]:
    if not path.exists():
        sys.exit(f"{path} is missing: copy .env.example and fill in the token")
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


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


def save_dashboard(ha: HA, url_path: str, old: dict[str, Any], new: dict[str, Any], backups: Path) -> None:
    """Save `new`, after writing the config HA had (`old`) to `backups/`."""
    backups.mkdir(exist_ok=True)
    (backups / f"{url_path}-{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(
        json.dumps(old, indent=1, ensure_ascii=False))
    ha.call({"type": "lovelace/config/save", "url_path": url_path, "config": new})


def states(ha: HA) -> dict[str, dict[str, Any]]:
    return {s["entity_id"]: s for s in ha.call({"type": "get_states"})}

"""Install the wrappers. This is the only place that touches upstream.

Three module-level functions are replaced by reassignment. Python resolves
module globals at call time, so every in-module caller picks these up — no
source edit, no import-order subtlety.

    call_service    every action path (button, long press, dial turn) funnels
                    here, so one wrapper captures them all.
    get_states      called once per connection session to build `complete_state`;
                    the natural place to seed synthetic entities, to wait out a
                    Home Assistant that is still starting, and to make a
                    missing entity read as `unavailable` instead of a KeyError.
    handle_changes  owns the app's long-lived asyncio tasks; we run the poller
                    for the lifetime of the session and cancel it on teardown,
                    so a reconnect gets a fresh one.

One method is wrapped too: `Dial.update_attributes`, which calls `float()` on
the entity state and so raises on `unavailable`/`unknown` — see
`_tolerant_update_attributes`.

Why the last three matter: upstream's `run()` retries only websocket/OS errors.
Any other exception — a KeyError from a half-loaded HA, a ValueError from an
`unavailable` dial — "breaks" out of the retry loop, resets the deck and exits
0, which launchd does not restart. That is how an HA restart used to leave the
deck dead until someone noticed. `ext/run.py` is the last-resort backstop for
anything still getting through.

`install()` verifies each symbol exists and is a coroutine function before
touching anything, and warns when the installed app version differs from the one
this was written against. If upstream renames something we fail loudly at
startup rather than silently losing local actions.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import time
from typing import Any

from . import actions, state

# The version this was developed and tested against. A mismatch is a warning,
# not an error — the symbol checks below are the real safety net.
TESTED_VERSION = "2026.5.3.dev2+g6226f780d"

WRAPPED = ("call_service", "get_states", "handle_changes")

# How long to wait for a starting Home Assistant before rendering whatever it
# has. HA accepts websocket connections well before its integrations have loaded
# their entities (~40s here after an upgrade), and `get_states` then returns a
# partial set. Past the timeout we carry on: missing entities render as
# `unavailable` and fill in as HA's own state_changed events arrive.
STARTUP_TIMEOUT = 300.0
STARTUP_POLL = 2.0

UNAVAILABLE = "unavailable"

_installed = False
_originals: dict[str, Any] = {}


def install() -> None:
    """Wrap the app's globals. Idempotent — a second call is a no-op.

    That matters: wrapping an already-wrapped function would nest the wrappers,
    and each layer would re-dispatch.
    """
    global _installed  # noqa: PLW0603
    if _installed:
        return

    import home_assistant_streamdeck_yaml as app

    _check(app)

    orig_call_service = app.call_service
    orig_get_states = app.get_states
    orig_handle_changes = app.handle_changes
    _originals.update({name: getattr(app, name) for name in WRAPPED})

    async def call_service(
        websocket: Any,
        service: str,
        data: dict[str, Any],
        target: dict[str, Any] | None = None,
    ) -> None:
        """Intercept the reserved local domain; pass everything else to HA."""
        if actions.handles(service):
            await actions.dispatch(service, data)
            return
        await orig_call_service(websocket, service, data, target)

    async def get_states(websocket: Any) -> dict[str, Any]:
        """Seed synthetic `mac.*` entities alongside the real HA state.

        Must happen here rather than lazily: the app indexes
        `complete_state[dial.entity_id]` while drawing the initial dial frames,
        and a missing key is a KeyError.
        """
        await _wait_until_running(websocket)
        complete_state = await orig_get_states(websocket)
        complete_state.update(state.snapshot())
        return TolerantState(complete_state)

    async def handle_changes(
        websocket: Any,
        complete_state: dict[str, Any],
        deck: Any,
        config: Any,
    ) -> None:
        # Bind before starting anything: an action handler needs these to
        # publish its result (and so redraw the keys that render it). The
        # websocket goes in too, so the poller can drop a connection that did
        # not survive a sleep — see state._reconnect_if_woken.
        state.bind(complete_state, config, deck, websocket)
        stop = state.run_poller(complete_state, config, deck)
        try:
            await orig_handle_changes(websocket, complete_state, deck, config)
        finally:
            await stop()
            state.unbind()

    app.call_service = call_service
    app.get_states = get_states
    app.handle_changes = handle_changes
    _originals["Dial.update_attributes"] = app.Dial.update_attributes
    app.Dial.update_attributes = _tolerant_update_attributes(app.Dial.update_attributes)

    if app.__version__ != TESTED_VERSION:
        app.console.log(
            f"[yellow]ext: app version {app.__version__} != tested "
            f"{TESTED_VERSION}; local actions still installed, but re-check "
            f"ext/wrap.py if behaviour is odd.[/]",
        )
    app.console.log(
        f"ext: local actions installed ({', '.join(sorted(actions.ACTIONS))})",
    )
    _installed = True


def uninstall() -> None:
    """Restore the app's own functions. Used by the tests; harmless in prod."""
    global _installed  # noqa: PLW0603
    if not _installed:
        return
    import home_assistant_streamdeck_yaml as app

    for name, fn in _originals.items():
        if name == "Dial.update_attributes":
            app.Dial.update_attributes = fn
        else:
            setattr(app, name, fn)
    _originals.clear()
    _installed = False


def _check(app: Any) -> None:
    """Fail loudly if the seams we rely on have moved."""
    expected = {
        "call_service": ("websocket", "service", "data", "target"),
        "get_states": ("websocket",),
        "handle_changes": ("websocket", "complete_state", "deck", "config"),
        # not wrapped, but state.publish() calls it directly
        "_update_state": ("complete_state", "data", "config", "deck"),
        # not wrapped, but _wait_until_running() numbers its request with it
        "_next_id": (),
        "Dial.update_attributes": ("self", "data"),
    }
    sync = {"_update_state", "_next_id", "Dial.update_attributes"}
    problems = []
    for name, params in expected.items():
        fn = app
        for part in name.split("."):
            fn = getattr(fn, part, None)
        if fn is None:
            problems.append(f"{name}: missing")
            continue
        if name not in sync and not asyncio.iscoroutinefunction(fn):
            problems.append(f"{name}: not a coroutine function")
        got = tuple(inspect.signature(fn).parameters)
        if got[: len(params)] != params:
            problems.append(f"{name}: signature is {got}, expected to start {params}")
    if problems:
        raise RuntimeError(
            "ext: home_assistant_streamdeck_yaml no longer matches the seams "
            "this extension wraps. Review ext/wrap.py against the installed "
            "version.\n  " + "\n  ".join(problems),
        )


class TolerantState(dict):
    """`complete_state` that answers a missing entity with `unavailable`.

    Upstream indexes `complete_state[entity_id]` directly while drawing dials,
    so one entity HA has not loaded yet (or that was renamed) is a KeyError that
    ends the app. A placeholder renders as an unavailable entity instead, and the
    real state replaces it when HA announces the entity. Nothing is inserted, so
    `entity_id in complete_state` stays honest and buttons keep their own
    "no state" path.
    """

    def __missing__(self, entity_id: str) -> dict[str, Any]:
        _log_once(f"missing:{entity_id}", f"[yellow]ext: {entity_id} is not in "
                  f"Home Assistant (yet); showing it as unavailable[/]")
        return {"entity_id": entity_id, "state": UNAVAILABLE, "attributes": {}}


def _tolerant_update_attributes(orig: Any) -> Any:
    """Keep a dial's last value when its entity's state is not a number.

    With no `state_attribute`, upstream does `float(data["state"])`, so an
    entity going `unavailable` — routine while HA restarts — raises inside the
    state_changed handler and ends the session.
    """

    def update_attributes(self: Any, data: dict[str, Any]) -> None:
        try:
            orig(self, data)
        except (ValueError, TypeError):
            # orig assigns _attributes before converting, so it is always set;
            # keep the previous value, or start at the bottom of the range.
            attrs = self._attributes  # noqa: SLF001
            attrs.setdefault("state", attrs.get("min", 0))
            _log_once(f"nan:{self.entity_id}", f"[yellow]ext: {self.entity_id} "
                      f"state {data.get('state')!r} is not a number; dial keeps "
                      f"its last value[/]")

    return update_attributes


async def _wait_until_running(websocket: Any) -> None:
    """Hold the session until Home Assistant reports it has finished starting.

    Called before `get_states`, so no subscription exists yet and the only
    messages on the socket are replies to our own requests. Gives up after
    STARTUP_TIMEOUT and lets the session start anyway. If HA is stopping
    instead, the socket closes under us and run()'s retry loop takes over.
    """
    import home_assistant_streamdeck_yaml as app

    deadline = time.monotonic() + STARTUP_TIMEOUT
    announced = False
    while True:
        req = app._next_id()  # noqa: SLF001
        await websocket.send(json.dumps({"id": req, "type": "get_config"}))
        while True:
            reply = json.loads(await websocket.recv())
            if reply.get("type") == "result" and reply.get("id") == req:
                break
        hass_state = (reply.get("result") or {}).get("state")
        # None: an HA too old to report it; nothing to wait for.
        if hass_state in ("RUNNING", None):
            return
        if time.monotonic() >= deadline:
            app.console.log(f"[yellow]ext: Home Assistant still {hass_state} after "
                            f"{STARTUP_TIMEOUT:.0f}s; starting anyway[/]")
            return
        if not announced:
            app.console.log(f"ext: Home Assistant is {hass_state}; waiting for "
                            f"it to finish starting before drawing the deck")
            announced = True
        await asyncio.sleep(STARTUP_POLL)


_logged: set[str] = set()


def _log_once(key: str, msg: str) -> None:
    """Log each distinct warning once per process — these fire on every redraw."""
    if key in _logged:
        return
    _logged.add(key)
    import home_assistant_streamdeck_yaml as app

    app.console.log(msg)

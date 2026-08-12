"""Install the wrappers. This is the only place that touches upstream.

Three module-level functions are replaced by reassignment. Python resolves
module globals at call time, so every in-module caller picks these up — no
source edit, no import-order subtlety.

    call_service    every action path (button, long press, dial turn) funnels
                    here, so one wrapper captures them all.
    get_states      called once per connection session to build `complete_state`;
                    the natural place to seed synthetic entities.
    handle_changes  owns the app's long-lived asyncio tasks; we run the poller
                    for the lifetime of the session and cancel it on teardown,
                    so a reconnect gets a fresh one.

`install()` verifies each symbol exists and is a coroutine function before
touching anything, and warns when the installed app version differs from the one
this was written against. If upstream renames something we fail loudly at
startup rather than silently losing local actions.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

from . import actions, state

# The version this was developed and tested against. A mismatch is a warning,
# not an error — the symbol checks below are the real safety net.
TESTED_VERSION = "2026.5.3.dev2+g6226f780d"

WRAPPED = ("call_service", "get_states", "handle_changes")

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
        complete_state = await orig_get_states(websocket)
        complete_state.update(state.snapshot())
        return complete_state

    async def handle_changes(
        websocket: Any,
        complete_state: dict[str, Any],
        deck: Any,
        config: Any,
    ) -> None:
        # Bind before starting anything: an action handler needs these to
        # publish its result (and so redraw the keys that render it).
        state.bind(complete_state, config, deck)
        stop = state.run_poller(complete_state, config, deck)
        try:
            await orig_handle_changes(websocket, complete_state, deck, config)
        finally:
            await stop()
            state.unbind()

    app.call_service = call_service
    app.get_states = get_states
    app.handle_changes = handle_changes

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
    }
    problems = []
    for name, params in expected.items():
        fn = getattr(app, name, None)
        if fn is None:
            problems.append(f"{name}: missing")
            continue
        if name != "_update_state" and not asyncio.iscoroutinefunction(fn):
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

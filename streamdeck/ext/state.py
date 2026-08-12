"""Synthetic `mac.*` entities, and the poller that keeps them fresh.

A provider produces a Home-Assistant-shaped state dict:

    {"state": "44", "attributes": {"level": 44, "muted": False}}

which we drop straight into the app's `complete_state`. From there the app
cannot tell it apart from a real HA entity, so dial rendering, `state_attr()`
templates and the eager local redraw all work with no further help.

To push a change we fabricate the same websocket payload HA would have sent and
hand it to the app's own `_update_state()`. That reuses the real code path —
including `_keys()` matching and `Dial.update_attributes()` — rather than
reimplementing rendering.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Any, Callable

from . import mac

if TYPE_CHECKING:
    from home_assistant_streamdeck_yaml import Config, StreamDeck

StateDict = dict[str, dict[str, Any]]

POLL_INTERVAL = 1.0

# After we ourselves write a value, ignore polls for this long. Without it a
# poll landing mid-turn would read a stale level and yank the dial back under
# the user's finger.
SETTLE = 1.5


class Provider:
    """One synthetic entity."""

    entity_id: str

    def read(self) -> dict[str, Any]:
        """Return a HA-shaped state dict. May raise; the poller logs and skips."""
        raise NotImplementedError


class Volume(Provider):
    """macOS output volume as `mac.volume`.

    `state` is the level so a dial can use it directly; `level` is also exposed
    as an attribute so configs can be explicit via `state_attribute: level`.
    """

    entity_id = "mac.volume"

    def read(self) -> dict[str, Any]:
        level, muted = mac.read_volume()
        return {
            "state": str(level),
            "attributes": {"level": level, "muted": muted},
        }


PROVIDERS: list[Provider] = [Volume()]

# entity_id -> monotonic deadline before which polls are ignored
_settle_until: dict[str, float] = {}
# entity_id -> last state dict we published, to suppress no-op redraws
_last: StateDict = {}
# The live session, bound for the lifetime of a connection so an action handler
# can publish its result without threading these three through every call.
_session: tuple[StateDict, Any, Any] | None = None


def bind(complete_state: StateDict, config: Config, deck: StreamDeck) -> None:
    global _session  # noqa: PLW0603
    _session = (complete_state, config, deck)


def unbind() -> None:
    global _session  # noqa: PLW0603
    _session = None


def publish_now(entity_id: str, new_state: dict[str, Any]) -> None:
    """Publish a state we just caused ourselves.

    MUST be called from the event loop thread — it ends up writing to the deck.
    Without this, a local write is invisible to the app: the optimistic cache
    update makes the poller compare equal, so nothing is ever published and any
    *button* rendering that entity stays stale (a dial hides the problem because
    it redraws eagerly on turn).
    """
    if _session is None:
        # Only reachable if a key is pressed between callback registration and
        # handle_changes() starting. The poller will pick it up shortly.
        _log(f"[yellow]{entity_id}: no session bound; redraw deferred to the poller[/]")
        _last.pop(entity_id, None)  # force the next poll to see a change
        return
    complete_state, config, deck = _session
    publish(entity_id, new_state, complete_state, config, deck)


def settle(entity_id: str, seconds: float = SETTLE) -> None:
    """Suppress polling for an entity we just wrote to."""
    _settle_until[entity_id] = time.monotonic() + seconds


def snapshot() -> StateDict:
    """Read every provider once. Used to seed `complete_state` at startup.

    A provider that fails here yields an `unavailable` entity rather than
    breaking startup — the app would raise KeyError on a missing entity_id.
    """
    out: StateDict = {}
    for p in PROVIDERS:
        try:
            out[p.entity_id] = p.read()
        except Exception as e:  # noqa: BLE001
            _log(f"[yellow]{p.entity_id}: initial read failed: {e}[/]")
            out[p.entity_id] = {"state": "unavailable", "attributes": {}}
    _last.update(out)
    return out


def publish(
    entity_id: str,
    new_state: dict[str, Any],
    complete_state: StateDict,
    config: Config,
    deck: StreamDeck,
) -> None:
    """Inject a state change through the app's own update path."""
    import home_assistant_streamdeck_yaml as app

    _last[entity_id] = new_state
    app._update_state(  # noqa: SLF001
        complete_state,
        {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {"entity_id": entity_id, "new_state": new_state},
            },
        },
        config,
        deck,
    )


async def poll_loop(
    complete_state: StateDict,
    config: Config,
    deck: StreamDeck,
) -> None:
    """Poll providers forever, publishing only genuine changes.

    Runs each read in a thread: osascript takes ~150ms and must not stall the
    deck's event loop. Never dies on a transient failure — a raising provider
    would otherwise take the poller down for the rest of the session.
    """
    loop = asyncio.get_running_loop()
    _log(f"local state poller started ({', '.join(p.entity_id for p in PROVIDERS)})")
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        now = time.monotonic()
        for p in PROVIDERS:
            if _settle_until.get(p.entity_id, 0.0) > now:
                continue
            try:
                new = await loop.run_in_executor(None, p.read)
            except Exception as e:  # noqa: BLE001
                _log(f"[yellow]{p.entity_id}: poll failed: {e}[/]")
                continue
            if new != _last.get(p.entity_id):
                publish(p.entity_id, new, complete_state, config, deck)


def run_poller(
    complete_state: StateDict,
    config: Config,
    deck: StreamDeck,
) -> Callable[[], Any]:
    """Start the poller as a task and return an async shutdown callable."""
    task = asyncio.create_task(poll_loop(complete_state, config, deck))

    async def stop() -> None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    return stop


def _log(msg: str) -> None:
    import home_assistant_streamdeck_yaml as app

    app.console.log(msg)

"""Local action registry — the `mac.*` "services".

Addressed through the app's existing `service:` field, because `Button`/`Dial`
are `extra="forbid"` pydantic models and cannot gain new YAML fields without
patching upstream source:

    - service: mac.volume_set
      service_data: {level: '{{ dial_value() | int }}'}

Handlers are sync and run in a thread (see `dispatch`), so a slow osascript
cannot stall the deck's event loop.

Note on `service_data`: the app injects `entity_id` into it — unconditionally
for dials, and for buttons when no `service_data` was given. Handlers therefore
take **kwargs and ignore what they don't recognise. Values arriving from a
template are STRINGS, so coerce.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from . import mac, state

DOMAIN = "mac"

# A handler may return (entity_id, new_state) so `dispatch` can publish the
# result on the event loop — see `_volume_hint`. None means "nothing to render".
Hint = tuple[str, dict[str, Any]] | None

Handler = Callable[..., Hint]
ACTIONS: dict[str, Handler] = {}


def action(name: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        ACTIONS[name] = fn
        return fn

    return register


def handles(service: str) -> bool:
    return service.split(".", 1)[0] == DOMAIN


# ── volume ──────────────────────────────────────────────────────────────────
@action("mac.volume_set")
def volume_set(level: Any = None, **_: Any) -> Hint:
    """Set output volume 0-100."""
    if level is None:
        raise ValueError("mac.volume_set needs a `level`")
    lvl = max(0, min(100, int(float(level))))
    mac.set_volume(lvl)
    return _volume_hint(level=lvl)


@action("mac.volume_mute")
def volume_mute(muted: Any = None, **_: Any) -> Hint:
    """Toggle mute, or set it explicitly when `muted` is given."""
    if muted is None:
        new = mac.toggle_muted()
    else:
        new = str(muted).strip().lower() in ("1", "true", "yes", "on")
        mac.set_muted(new)
    return _volume_hint(muted=new)


# ── applications ────────────────────────────────────────────────────────────
@action("mac.open_app")
def open_app(app: Any = None, **_: Any) -> Hint:
    """Launch or focus an app: `service_data: {app: 1Password}`.

    Returns no hint — there is nothing rendered from this, and asking macOS
    whether an app is frontmost needs Automation approval (Tier 1).
    """
    if not app:
        raise ValueError("mac.open_app needs an `app`")
    mac.open_app(str(app))
    return None


def _volume_hint(level: int | None = None, muted: bool | None = None) -> Hint:
    """Build the post-write state for `mac.volume` and hold the poller off.

    Returned rather than published here because handlers run in a worker thread
    and publishing writes to the deck — `dispatch` publishes it on the loop.

    The settle window matters for a different reason: without it, a poll landing
    mid-turn would read a stale level and yank the dial back under the user's
    finger.
    """
    prev = state._last.get("mac.volume", {})  # noqa: SLF001
    attrs = dict(prev.get("attributes", {}))
    if level is not None:
        attrs["level"] = level
    if muted is not None:
        attrs["muted"] = muted
    state.settle("mac.volume")
    return "mac.volume", {
        "state": str(attrs.get("level", prev.get("state", "0"))),
        "attributes": attrs,
    }


# ── dispatch ────────────────────────────────────────────────────────────────
async def dispatch(service: str, data: dict[str, Any] | None) -> None:
    """Run a local action. Errors are logged, never raised into the deck loop."""
    import home_assistant_streamdeck_yaml as app

    handler = ACTIONS.get(service)
    if handler is None:
        app.console.log(
            f"[red]Unknown local action {service!r}[/] "
            f"(known: {', '.join(sorted(ACTIONS))})",
        )
        return

    kwargs = dict(data or {})
    kwargs.pop("entity_id", None)  # injected by the app; not a handler argument
    app.console.log(f"Running local action {service} with {kwargs}")
    loop = asyncio.get_running_loop()
    try:
        hint = await loop.run_in_executor(None, lambda: handler(**kwargs))
    except Exception as e:  # noqa: BLE001
        app.console.log(f"[red]{service} failed: {type(e).__name__}: {e}[/]")
        return
    # Publish on the loop thread: this redraws keys/dials, and deck I/O must not
    # happen from the executor. Without it, buttons rendering this entity would
    # stay stale until the next poll noticed a difference — and the optimistic
    # cache means it never would.
    if hint is not None:
        state.publish_now(*hint)

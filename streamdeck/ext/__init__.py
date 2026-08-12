"""Local-machine extensions for home-assistant-streamdeck-yaml.

The upstream app is a pure Home Assistant client: every button press and dial
turn becomes a websocket `call_service`, and there is no way to run anything on
the machine the deck is plugged into. This package adds that, WITHOUT editing
upstream source — it wraps four module-level functions by reassignment:

    call_service    -> intercept the reserved `mac.` domain and run it locally.
                       This is the single chokepoint for *every* action path:
                       button press, long press, and dial turn all funnel here.
    get_states      -> inject synthetic `mac.*` entities into `complete_state`.
    handle_changes  -> run a poller alongside the app's own asyncio tasks.

The synthetic-entity trick is what makes this cheap. Once `complete_state`
contains a `mac.volume` entity, the app's entire existing pipeline works on it
unmodified: `is_state()` / `state_attr()` templates, `Dial.update_attributes()`,
`render_lcd_image()`, the eager local redraw on dial turn, everything. The
poller fabricates `state_changed` events and hands them to the app's own
`_update_state()`, so an external change (pressing the Mac's volume keys) redraws
the dial by exactly the same path an HA state change would.

Why reassignment and not a source patch: Python resolves module globals at call
time, so reassigning `app.call_service` is picked up by every in-module caller.
That means our code lives in this repo as ordinary reviewable Python instead of
regex surgery on a site-packages file, and it survives `task xl:install`
recreating the venv. See `wrap.install()` for the version guard.

Actions are addressed through the existing `service:` field under a reserved
domain, because `Button`/`Dial` are pydantic models with `extra="forbid"` and so
cannot gain new YAML fields without patching source:

    - service: mac.volume_set
      service_data: {level: 40}

Entry point is `python -m ext.run` (see run.py), which installs the wrappers and
then defers to the upstream `main()` for all CLI/env/reconnect handling.
"""

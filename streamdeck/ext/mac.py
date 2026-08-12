"""The macOS bridge — every OS call this package makes lives here.

Deliberately thin and subprocess-based. `osascript` costs ~150ms wall / ~70ms
CPU per invocation, so reads are BATCHED into one call (see `read_volume`) and
the poller runs at 1Hz. If that ever becomes a bottleneck, the replacement is
PyObjC + CoreAudio for volume, which is instant but adds a dependency.

PERMISSIONS (TCC). Everything here is deliberately Tier 0 — no permission
prompts at all:
  * `set volume` / `get volume settings` are Standard Additions, executed by
    osascript itself, NOT Apple events sent to another app.
Anything that talks to another application (System Events for keystrokes,
Spotify for transport) is an Apple event and needs Automation and/or
Accessibility approval, which for a LaunchAgent attaches to the responsible
binary and cannot be granted non-interactively. Those land in a later phase
behind `task xl:perms`; keep this module Tier 0 so Phase 1 works unattended.
"""
from __future__ import annotations

import subprocess

TIMEOUT = 5.0


class MacError(RuntimeError):
    """An osascript call failed."""


def _osascript(*lines: str) -> str:
    """Run an AppleScript as a series of -e lines and return stdout stripped."""
    proc = subprocess.run(  # noqa: S603
        ["/usr/bin/osascript", *[a for line in lines for a in ("-e", line)]],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise MacError((proc.stderr or proc.stdout).strip() or "osascript failed")
    return proc.stdout.strip()


# ── output volume ───────────────────────────────────────────────────────────
def read_volume() -> tuple[int, bool]:
    """Return (output volume 0-100, muted). One osascript call, not two."""
    out = _osascript(
        "set v to (get volume settings)",
        'return ((output volume of v) as text) & " " & ((output muted of v) as text)',
    )
    level, muted = out.split()
    return int(float(level)), muted == "true"


def set_volume(level: int) -> None:
    """Set the output volume (0-100). Does not change the mute flag."""
    level = max(0, min(100, int(level)))
    _osascript(f"set volume output volume {level}")


def set_muted(muted: bool) -> None:  # noqa: FBT001
    # Explicit boolean form; `set volume with/without output muted` also works.
    _osascript(f"set volume output muted {'true' if muted else 'false'}")


def toggle_muted() -> bool:
    """Flip the mute flag and return the new value."""
    _, muted = read_volume()
    set_muted(not muted)
    return not muted


# ── applications ────────────────────────────────────────────────────────────
def open_app(name: str) -> None:
    """Launch an app, or bring it to the front if already running.

    `open -a` needs no TCC approval, unlike activating an app via System Events.
    `name` is what Finder shows (e.g. "1Password"), a bundle id, or a full path.
    """
    proc = subprocess.run(  # noqa: S603
        ["/usr/bin/open", "-a", name],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise MacError((proc.stderr or proc.stdout).strip() or f"could not open {name!r}")

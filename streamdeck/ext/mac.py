"""The macOS bridge — every OS call this package makes lives here.

Deliberately thin and subprocess-based. `osascript` costs ~150ms wall / ~70ms
CPU per invocation, so reads are BATCHED into one call (see `read_volume`) and
the poller runs at 1Hz. If that ever becomes a bottleneck, the replacement is
PyObjC + CoreAudio for volume, which is instant but adds a dependency.

PERMISSIONS (TCC). Everything here is deliberately Tier 0 — no permission
prompts at all:
  * `set volume` / `get volume settings` are Standard Additions, executed by
    osascript itself, NOT Apple events sent to another app.
  * `open` (an app by name, or a URL scheme) is dispatched by LaunchServices.
    It reaches another application without an Apple event, which is why
    launching apps and driving KeepingYouAwake stay Tier 0 — the distinction
    is the MECHANISM, not whether another app ends up involved.
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


# ── keep-awake (KeepingYouAwake.app) ────────────────────────────────────────
# Driven through KeepingYouAwake rather than by spawning our own `caffeinate`,
# so the deck key and KYA's menu bar icon are the SAME state — toggle it either
# way and both agree. KYA is free/MIT (brew install --cask keepingyouawake).
# Still Tier 0: its URL scheme is handled by LaunchServices, so no Automation
# or Accessibility grant is involved. (macOS's own Caffeine.app alternative is
# not scriptable at all — no AppleScript, no URL scheme, no hotkey.)
KYA_APP = "KeepingYouAwake"


def _pgrep(*args: str) -> list[str]:
    """Return matching PIDs as strings; empty when nothing matched."""
    proc = subprocess.run(  # noqa: S603
        ["/usr/bin/pgrep", *args],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    return proc.stdout.split() if proc.returncode == 0 else []


def caffeinate_running() -> bool:
    """True if KeepingYouAwake is currently keeping this Mac awake.

    KYA implements keep-awake by spawning `/usr/bin/caffeinate -di -w <its
    pid>`, so its state reads straight off the process table — no Apple event,
    no TCC prompt, and a toggle from KYA's own menu bar icon reaches the deck
    within one poll.

    Deliberately scoped to KYA's OWN children: a bare `pgrep -x caffeinate`
    would also match an unrelated caffeinate (one started in a Terminal, or a
    leftover from an older build of this repo), and the key would then claim
    to be on while the off press — which only talks to KYA — could not turn it
    off, leaving the button visibly stuck.
    """
    kya = _pgrep("-x", KYA_APP)
    if not kya:
        return False  # not running, so nothing of KYA's is holding sleep off
    return bool(_pgrep("-P", ",".join(kya), "-x", "caffeinate"))


def set_caffeinate(on: bool) -> None:  # noqa: FBT001
    """Activate or deactivate KeepingYouAwake via its URL scheme.

    `open -g <url>` is dispatched by LaunchServices, which needs no permission
    grant (Tier 0) — driving the app by AppleScript would be an Apple event and
    would need Automation approval, which a LaunchAgent cannot arrange
    non-interactively. `-g` keeps KYA in the background so a deck press never
    steals focus. LaunchServices starts KYA if it is not already running.

    Uses explicit activate/deactivate rather than KYA's own `toggle`, so this
    is idempotent and an explicit `on:` in service_data means what it says
    (the deck's own press sends no `on:` and toggles in the handler instead).

    NOTE: `activate` runs for KYA's *configured default duration*, which is
    indefinite unless changed in its preferences — deliberately its setting to
    own, not something this repo overrides.
    """
    action = "activate" if on else "deactivate"
    proc = subprocess.run(  # noqa: S603
        ["/usr/bin/open", "-g", f"keepingyouawake:///{action}"],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise MacError(
            (proc.stderr or proc.stdout).strip()
            or f"could not {action} {KYA_APP} — is it installed?",
        )


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

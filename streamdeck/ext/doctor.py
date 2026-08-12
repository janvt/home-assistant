"""`python -m ext.doctor` — report what local control can actually do here.

macOS gates capabilities behind TCC, and for a LaunchAgent the grant attaches to
the responsible binary rather than to a script, so it cannot be arranged
non-interactively. Rather than guess, probe and print the truth.

Tier 0  no permission needed        — what Phase 1 uses
Tier 1  Automation, per target app  — AppleScript to Spotify/Music/etc.
Tier 2  Accessibility               — keystrokes, hotkeys, media keys, UI scripting

Probes are read-only: nothing is muted, launched or typed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys

from . import mac


def _probe(label: str, fn) -> bool:  # noqa: ANN001
    try:
        detail = fn()
    except Exception as e:  # noqa: BLE001
        msg = str(e).replace("\n", " ")[:96]
        print(f"  [ FAIL ] {label}\n           {msg}")
        return False
    print(f"  [  OK  ] {label}" + (f" — {detail}" if detail else ""))
    return True


def _apple_event() -> str:
    """Send a harmless Apple event to System Events (no UI interaction)."""
    out = mac._osascript(  # noqa: SLF001
        'tell application "System Events" to return name of current user',
    )
    return f"System Events reachable (user {out})"


def _accessibility() -> str:
    out = mac._osascript(  # noqa: SLF001
        'tell application "System Events" to return UI elements enabled',
    )
    if out.strip().lower() != "true":
        raise RuntimeError("UI elements not enabled")
    return "UI scripting enabled"


def main() -> int:
    print(f"python     {sys.version.split()[0]}  ({sys.executable})")
    try:
        ver = subprocess.run(  # noqa: S603
            ["/usr/bin/sw_vers", "-productVersion"],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        print(f"macOS      {ver}")
    except OSError:
        pass

    print("\nTier 0 — no permission required")
    t0 = [
        _probe("read output volume", lambda: "level={} muted={}".format(*mac.read_volume())),
        _probe("write output volume (re-set to current value)",
               lambda: mac.set_volume(mac.read_volume()[0]) or "no audible change"),
        _probe("open(1) present", lambda: shutil.which("open") or _missing("open")),
        _probe("shortcuts(1) present", lambda: shutil.which("shortcuts") or _missing("shortcuts")),
        _probe("pmset(1) present", lambda: shutil.which("pmset") or _missing("pmset")),
    ]

    print("\nTier 1 — Automation (Apple events to other apps)")
    t1 = [_probe("send Apple event to System Events", _apple_event)]

    print("\nTier 2 — Accessibility (keystrokes, hotkeys, UI scripting)")
    t2 = [_probe("UI scripting / keystroke injection", _accessibility)]

    print(f"\nsummary: tier0 {sum(t0)}/{len(t0)}   "
          f"tier1 {sum(t1)}/{len(t1)}   tier2 {sum(t2)}/{len(t2)}")
    if not all(t0):
        print("\nTier 0 failures are real bugs — Phase 1 (volume dial) needs these.")
        return 1
    if not all(t1) or not all(t2):
        print(
            "\nTier 1/2 are NOT needed for the volume dial. To enable them later:\n"
            "  Automation:    System Settings > Privacy & Security > Automation\n"
            "  Accessibility: System Settings > Privacy & Security > Accessibility\n"
            f"  Grant the responsible binary, which for the LaunchAgent is\n"
            f"    {sys.executable}\n"
            "  Prompts only appear for a process in your GUI login session, so run\n"
            "  `task xl:run` in a terminal (not the service) when approving.",
        )
    return 0


def _missing(name: str) -> str:
    raise RuntimeError(f"{name} not found on PATH")


if __name__ == "__main__":
    raise SystemExit(main())

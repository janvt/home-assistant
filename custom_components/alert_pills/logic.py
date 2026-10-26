"""Which pills show, and where. Pure functions, no Home Assistant imports, so the
repo's plain test suite can check them next to the dashboard they feed.
"""
from __future__ import annotations

from collections.abc import Iterable


def enabled(pill: dict, disabled: Iterable[str], disabled_groups: Iterable[str]) -> bool:
    """Switched on in the options: neither the pill nor its group is off."""
    return pill["key"] not in set(disabled) and pill["group"] not in set(disabled_groups)


def dismissed(on_since: float | None, dismissed_at: float | None) -> bool:
    """Dismissed while on: a pill that turns off and on again is back by itself."""
    return on_since is not None and dismissed_at is not None and dismissed_at >= on_since


def row(shown: list[str], card_only: Iterable[str], places: int) -> tuple[list[str], int]:
    """The pills that get a place in the row, and how many didn't ("+N").

    `shown` is in priority order. Up to `places` pills fit; with more, the last
    place turns into "+N" so the row never grows past one line.
    """
    skip = set(card_only)
    eligible = [k for k in shown if k not in skip]
    if len(eligible) <= places:
        return eligible, 0
    return eligible[:places - 1], len(eligible) - (places - 1)

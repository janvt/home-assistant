"""Checks against the real Live Dashboard that the sectors are still read.

Not run with the other tests: see the Live workflow.
"""

import aiohttp
import pytest

from custom_components.andermatt_live.const import USER_AGENT
from custom_components.andermatt_live.live import (
    CLOSED,
    OPEN,
    SECTORS,
    AndermattLiveClient,
)


@pytest.mark.parametrize("slug", list(SECTORS))
async def test_the_sector_is_read(slug):
    async with aiohttp.ClientSession() as session:
        sector = await AndermattLiveClient(session, USER_AGENT).async_sector(slug)

    # Every sector has lifts all year; a status other than open or closed
    # would be a new one, to look at.
    assert sector.lifts, slug
    for lift in sector.lifts.values():
        assert lift.status in (OPEN, CLOSED), lift
        assert lift.kind, lift
    for slope in sector.slopes.values():
        assert slope.status in (OPEN, CLOSED), slope
        assert slope.difficulty is not None, slope
    # A fun park has no length on the site; most slopes have one.
    if sector.slopes:
        with_length = [s for s in sector.slopes.values() if s.length]
        assert len(with_length) >= len(sector.slopes) / 2, slug
    assert sector.snow_depth is not None
    assert sector.new_snow is not None

"""Shared fixtures."""

from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.andermatt_live.const import DOMAIN
from custom_components.andermatt_live.live import PAGE_URL

FIXTURES = Path(__file__).parent / "fixtures"
# Pages saved from the site on 22 November 2026, a Sunday when only Gemsstock
# was open.
SAVED_SECTORS = ("gemsstock", "andermatt-oberalppass", "disentis")
PAGES = {"start": "start", "anlagen": "anlagen", "pisten": "pisten"}


def page(name: str, sector: str) -> str:
    return (FIXTURES / f"{name}_{sector}.html").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/andermatt_live."""


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """Try the site again at once, rather than after RETRY_DELAY."""
    monkeypatch.setattr("custom_components.andermatt_live.live.RETRY_DELAY", 0)


@pytest.fixture
def site(aioclient_mock):
    """The site, serving the saved pages."""
    for sector in SAVED_SECTORS:
        for name in PAGES:
            aioclient_mock.get(
                PAGE_URL.format(page=name, sector=sector), text=page(name, sector)
            )
    return aioclient_mock


def responses(*answers):
    """A side effect for aioclient_mock: each request gets the next answer,
    an exception to raise or a (status, text) pair."""
    remaining = list(answers)

    async def answer(method, url, data):
        result = remaining.pop(0)
        if isinstance(result, BaseException):
            raise result
        status, text = result
        return AiohttpClientMockResponse(method, url, status=status, text=text)

    return answer


@pytest.fixture
def entry_data():
    return {"sectors": ["gemsstock", "andermatt-oberalppass"]}


@pytest.fixture
def entry(hass, entry_data):
    entry = MockConfigEntry(
        domain=DOMAIN, data=entry_data, title="Andermatt+Sedrun+Disentis"
    )
    entry.add_to_hass(hass)
    return entry

"""Keeps every page the live checks read, when ANDERMATT_LIVE_PAGES names a
folder: the workflow uploads it when they fail, to show what the site served.
The files are named as tests/fixtures names them."""

import os
from pathlib import Path

import pytest

from custom_components.andermatt_live.live import AndermattLiveClient


@pytest.fixture(autouse=True)
def _keep_the_pages(monkeypatch):
    if not (folder := os.environ.get("ANDERMATT_LIVE_PAGES")):
        return
    pages = Path(folder)
    pages.mkdir(parents=True, exist_ok=True)
    get = AndermattLiveClient._get

    async def get_and_keep(self, page: str, sector: str) -> str:
        html = await get(self, page, sector)
        (pages / f"{page}_{sector}.html").write_text(html, encoding="utf-8")
        return html

    monkeypatch.setattr(AndermattLiveClient, "_get", get_and_keep)

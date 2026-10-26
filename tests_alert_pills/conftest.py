"""The alert_pills integration, run inside a real Home Assistant.

Needs `pytest-homeassistant-custom-component` (and the Python HA requires),
which the repo's main venv doesn't have, so it is its own suite:

    pip install pytest-homeassistant-custom-component
    pytest -o asyncio_mode=auto tests_alert_pills
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

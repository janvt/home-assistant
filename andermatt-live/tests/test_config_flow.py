"""Choosing the sectors, when setting up and in the options."""

from homeassistant.data_entry_flow import FlowResultType

from custom_components.andermatt_live.const import DOMAIN
from custom_components.andermatt_live.live import PAGE_URL


async def start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def test_gemsstock_and_andermatt_are_suggested(hass):
    result = await start(hass)

    assert result["type"] is FlowResultType.FORM
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults == {"sectors": ["gemsstock", "andermatt-oberalppass"]}


async def test_set_up(hass, site):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sectors": ["gemsstock"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"sectors": ["gemsstock"]}


async def test_at_least_one_sector(hass):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sectors": []}
    )

    assert result["errors"] == {"sectors": "no_sectors"}


async def test_the_site_down(hass, aioclient_mock):
    aioclient_mock.get(PAGE_URL.format(page="start", sector="gemsstock"), status=503)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sectors": ["gemsstock"]}
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_change_the_sectors(hass, entry, site):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"sectors": ["disentis"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"sectors": ["disentis"]}

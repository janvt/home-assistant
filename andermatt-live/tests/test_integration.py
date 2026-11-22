"""The integration in Home Assistant: entities, updates and failures."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.andermatt_live.const import DOMAIN
from custom_components.andermatt_live.live import PAGE_URL

from .conftest import page


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def entity_id(hass, platform, unique_id):
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)


def state(hass, platform, unique_id):
    return hass.states.get(entity_id(hass, platform, unique_id))


async def test_a_device_per_sector(hass, entry, site):
    await setup(hass, entry)

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert sorted(d.name for d in devices) == ["Andermatt-Oberalppass", "Gemsstock"]


async def test_the_sector_counts(hass, entry, site):
    await setup(hass, entry)

    lifts = state(hass, "sensor", "gemsstock_lifts_open")
    assert lifts.state == "3"
    assert lifts.attributes["total"] == 4
    assert lifts.attributes["friendly_name"] == "Gemsstock Lifts open"
    assert state(hass, "sensor", "gemsstock_slopes_open").state == "6"
    length = state(hass, "sensor", "gemsstock_slopes_open_length")
    assert length.attributes["unit_of_measurement"] == "km"
    assert float(length.state) == 11.472
    assert state(hass, "sensor", "gemsstock_snow_depth").state == "40.0"
    assert state(hass, "sensor", "andermatt-oberalppass_lifts_open").state == "0"


async def test_open_is_any_lift(hass, entry, site):
    """The sector's own binary sensor, for "can I ski there now?"."""
    await setup(hass, entry)

    assert state(hass, "binary_sensor", "gemsstock_open").state == "on"
    assert state(hass, "binary_sensor", "andermatt-oberalppass_open").state == "off"


async def test_a_lift(hass, entry, site):
    await setup(hass, entry)

    lift = state(hass, "binary_sensor", "gemsstock_lift_15_gemsstock_bahn")
    assert lift.state == "on"
    assert lift.attributes["friendly_name"] == "Gemsstock 15 Gemsstock-Bahn"
    assert lift.attributes["first_ride"] == "08:40"
    assert lift.attributes["last_ride"] == "15:55"
    closed = state(hass, "binary_sensor", "gemsstock_lift_17_lutersee_lift")
    assert closed.state == "off"


async def test_a_slope(hass, entry, site):
    await setup(hass, entry)

    slope = state(hass, "binary_sensor", "gemsstock_slope_70_sonnenpiste")
    assert slope.state == "on"
    assert slope.attributes["difficulty"] == "red"
    assert slope.attributes["length"] == 6400
    closed = state(hass, "binary_sensor", "gemsstock_slope_75_lutersee")
    assert closed.state == "off"


async def test_car_parks(hass, entry, site):
    await setup(hass, entry)

    assert (
        state(hass, "sensor", "andermatt-oberalppass_car_park_pp_rossstall").state
        == "full"
    )
    assert (
        state(hass, "sensor", "gemsstock_car_park_pp_gemsstock_nordic").state == "free"
    )


async def test_a_lift_closing(hass, entry, site, aioclient_mock):
    await setup(hass, entry)
    url = PAGE_URL.format(page="anlagen", sector="gemsstock")
    aioclient_mock.clear_requests()
    for sector in ("gemsstock", "andermatt-oberalppass"):
        for name in ("start", "anlagen", "pisten"):
            html = page(name, sector)
            if PAGE_URL.format(page=name, sector=sector) == url:
                html = html.replace("status-2", "status-1")
            aioclient_mock.get(PAGE_URL.format(page=name, sector=sector), text=html)

    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert state(hass, "binary_sensor", "gemsstock_open").state == "off"
    assert state(hass, "sensor", "gemsstock_lifts_open").state == "0"


async def test_the_site_down_at_setup(hass, entry, aioclient_mock):
    aioclient_mock.get(PAGE_URL.format(page="start", sector="gemsstock"), status=503)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_the_site_down_later(hass, entry, site, aioclient_mock):
    """Unavailable rather than closed: a lift whose state is not known."""
    await setup(hass, entry)
    aioclient_mock.clear_requests()
    aioclient_mock.get(PAGE_URL.format(page="start", sector="gemsstock"), status=503)

    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert state(hass, "binary_sensor", "gemsstock_open").state == "unavailable"


async def test_a_sector_taken_out_loses_its_device(hass, entry, site):
    await setup(hass, entry)

    hass.config_entries.async_update_entry(entry, options={"sectors": ["gemsstock"]})
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [d.name for d in devices] == ["Gemsstock"]

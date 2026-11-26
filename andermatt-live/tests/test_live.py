"""Reading the Live Dashboard's pages, saved on 22 November 2026."""

import aiohttp
import pytest

from custom_components.andermatt_live.live import (
    CLOSED,
    OPEN,
    PAGE_URL,
    PREPARING,
    AndermattLiveBlockedError,
    AndermattLiveClient,
    AndermattLiveError,
    parse_lifts,
    parse_slopes,
    parse_start,
    slugify,
)

from .conftest import page, responses


class TestLifts:
    def test_gemsstock(self):
        lifts = parse_lifts(page("anlagen", "gemsstock"))

        assert list(lifts) == [
            "14_gurschen_bahn",
            "15_gemsstock_bahn",
            "16_gurschen_flyer",
            "17_lutersee_lift",
        ]
        bahn = lifts["15_gemsstock_bahn"]
        assert bahn.name == "15 Gemsstock-Bahn"
        assert bahn.number == "15"
        assert bahn.kind == "Pendelbahn"
        assert bahn.status == OPEN and bahn.is_open
        assert (bahn.first_ride, bahn.last_ride) == ("08:40", "15:55")
        assert lifts["17_lutersee_lift"].status == CLOSED

    def test_a_commented_out_label_is_not_read(self):
        """Each card keeps an old status label in a comment; the status comes
        from the row's class, whatever the comment says."""
        html = page("anlagen", "gemsstock").replace(
            "anlagen-overview-row status-2", "anlagen-overview-row status-1", 1
        )

        assert not parse_lifts(html)["14_gurschen_bahn"].is_open

    def test_lifts_without_a_number_or_rides(self):
        lifts = parse_lifts(page("anlagen", "disentis"))

        band = lifts["caischavedra_forderband"]
        assert band.number is None
        assert band.kind == "Förderband"
        kids = lifts["skischullift_und_snowly_kinderland"]
        # "–" on the site: no rides that day.
        assert (kids.first_ride, kids.last_ride) == (None, None)

    def test_a_lift_in_preparation(self):
        """"Vorbereitung" on the site: a status of its own, not open, as the
        site doesn't count it as open either."""
        html = page("anlagen", "gemsstock").replace(
            "anlagen-overview-row status-2", "anlagen-overview-row status-3", 1
        )

        lift = parse_lifts(html)["14_gurschen_bahn"]
        assert lift.status == PREPARING
        assert not lift.is_open

    def test_an_unknown_status_is_kept_but_not_open(self):
        html = page("anlagen", "gemsstock").replace(
            "anlagen-overview-row status-2", "anlagen-overview-row status-7", 1
        )

        lift = parse_lifts(html)["14_gurschen_bahn"]
        assert lift.status == "status_7"
        assert not lift.is_open

    def test_a_row_without_a_name_is_an_error(self):
        """Rather than a lift with an empty name: the page has changed."""
        html = (
            '<article class="anlagen-overview-row status-2">'
            '<span class="anlagen-overview-title"></span></article>'
        )

        with pytest.raises(AndermattLiveError):
            parse_lifts(html)


class TestSlopes:
    def test_gemsstock(self):
        slopes = parse_slopes(page("pisten", "gemsstock"))

        assert len(slopes) == 17
        assert sum(s.is_open for s in slopes.values()) == 6
        sonnenpiste = slopes["70_sonnenpiste"]
        assert sonnenpiste.number == "70"
        assert sonnenpiste.difficulty == "red"
        assert sonnenpiste.length == 6400
        assert slopes["70a_gurschengratli"].difficulty == "blue"
        assert slopes["74a_osterreicherloch"].difficulty == "black"
        assert slopes["72_gurschenstock_abfahrt"].difficulty == "freeride"

    def test_a_slope_in_preparation(self):
        html = page("pisten", "gemsstock").replace(
            "anlagen-overview-row status-2", "anlagen-overview-row status-3", 1
        )

        slopes = parse_slopes(html)
        preparing = [s for s in slopes.values() if s.status == PREPARING]
        assert len(preparing) == 1
        assert not preparing[0].is_open
        assert sum(s.is_open for s in slopes.values()) == 5


class TestStart:
    def test_snow_and_car_parks(self):
        start = parse_start(page("start", "andermatt-oberalppass"))

        assert start.snow_depth == 9
        assert start.new_snow == 0
        assert {k: (p.name, p.free) for k, p in start.car_parks.items()} == {
            "pp_andermatt": ("PP Andermatt", True),
            "pp_rossstall": ("PP Rossstall", False),
            "pp_reuss": ("PP Reuss", True),
        }

    def test_a_sector_without_car_parks(self):
        start = parse_start(page("start", "disentis"))

        assert start.car_parks == {}
        assert start.snow_depth == 0


def test_slugify():
    assert slugify("1 Gütsch-Express 1. Sektion") == "1_gutsch_express_1_sektion"


@pytest.fixture
async def client(aioclient_mock, hass):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    return AndermattLiveClient(async_get_clientsession(hass), "test")


async def test_a_sector_is_read_from_its_three_pages(client, site):
    sector = await client.async_sector("gemsstock")

    assert sector.name == "Gemsstock"
    assert (sector.lifts_open, len(sector.lifts)) == (3, 4)
    assert (sector.slopes_open, len(sector.slopes)) == (6, 17)
    assert sector.slopes_open_length == 6400 + 640 + 592 + 2080 + 560 + 1200
    assert sector.snow_depth == 40
    assert sector.url == "https://beta.andermatt-sedrun-disentis.ch/start/gemsstock"
    assert len(site.mock_calls) == 3


async def test_a_hiccup_is_tried_again(client, aioclient_mock):
    url = PAGE_URL.format(page="start", sector="gemsstock")
    aioclient_mock.get(
        url,
        side_effect=responses(aiohttp.ClientError("reset"), (200, "<html></html>")),
    )

    assert await client._get("start", "gemsstock") == "<html></html>"


async def test_a_refusal_is_not_tried_again(client, aioclient_mock):
    url = PAGE_URL.format(page="start", sector="gemsstock")
    aioclient_mock.get(url, status=403)

    with pytest.raises(AndermattLiveBlockedError):
        await client._get("start", "gemsstock")
    assert len(aioclient_mock.mock_calls) == 1


async def test_two_failures_are_an_error(client, aioclient_mock):
    url = PAGE_URL.format(page="start", sector="gemsstock")
    aioclient_mock.get(url, status=502)

    with pytest.raises(AndermattLiveError):
        await client._get("start", "gemsstock")
    assert len(aioclient_mock.mock_calls) == 2

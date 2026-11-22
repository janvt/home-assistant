"""Lifts, slopes, snow and car parks of Andermatt+Sedrun+Disentis, read from
the resort's A+S+D Live Dashboard.

The dashboard has no API: its pages are rendered on the server, one set per
sector (Teilgebiet), and read here.  For each sector three pages are read:

- ``/start/<sector>``: the snow depth, the new snow and the car parks.
- ``/anlagen/<sector>``: every lift, open or closed, with its first and last
  ride of the day.
- ``/pisten/<sector>``: every slope, open or closed, with its colour and length.

Whether a lift or slope is open is read from the status class of its row
(``status-2`` open, ``status-1`` closed) rather than from its German label.

Source: Andermatt-Sedrun Sport AG, https://beta.andermatt-sedrun-disentis.ch
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://beta.andermatt-sedrun-disentis.ch"
PAGE_URL = BASE_URL + "/{page}/{sector}"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
# One more try after this long when the site does not answer, rather than the
# sector being unavailable until the next update.
RETRY_DELAY = 10
# The site refusing the request, rather than failing to answer it.
BLOCKED_STATUSES = (403, 429)

# The sectors (Teilgebiete), by their slug on the site, in the site's order.
SECTORS = {
    "gemsstock": "Gemsstock",
    "andermatt-oberalppass": "Andermatt-Oberalppass",
    "oberalppass-dieni": "Oberalppass-Dieni",
    "sedrun": "Sedrun",
    "disentis": "Disentis",
}

OPEN = "open"
CLOSED = "closed"
# The status classes of a row, "status-<n>".  Any other number is kept as the
# row's status, but is not taken as open.
STATUSES = {"1": CLOSED, "2": OPEN}

# A slope's colour, from the start of its German label ("Rote Piste").
DIFFICULTIES = {
    "blau": "blue",
    "rot": "red",
    "schwarz": "black",
    "gelb": "freeride",
}

_LENGTH = re.compile(r"(\d+(?:[.,]\d+)?)\s*m\b")
_CENTIMETRES = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*cm\b")
_TIME = re.compile(r"^\d{1,2}:\d{2}$")
# The number at the start of a name: "14 Gurschen-Bahn", "70a Gurschengrätli".
_NUMBER = re.compile(r"^(\d+[a-z]?)\s+")


class AndermattLiveError(Exception):
    """The live data could not be obtained."""


class AndermattLiveBlockedError(AndermattLiveError):
    """The site refused the request."""


@dataclass(frozen=True)
class Lift:
    key: str
    name: str
    number: str | None
    kind: str | None
    status: str
    first_ride: str | None
    last_ride: str | None

    @property
    def is_open(self) -> bool:
        return self.status == OPEN


@dataclass(frozen=True)
class Slope:
    key: str
    name: str
    number: str | None
    status: str
    difficulty: str | None
    length: int | None

    @property
    def is_open(self) -> bool:
        return self.status == OPEN


@dataclass(frozen=True)
class CarPark:
    key: str
    name: str
    # The class of its badge: "frei" (free) or "besetzt" (full or closed).
    free: bool | None
    text: str


@dataclass(frozen=True)
class Sector:
    slug: str
    name: str
    lifts: dict[str, Lift] = field(default_factory=dict)
    slopes: dict[str, Slope] = field(default_factory=dict)
    car_parks: dict[str, CarPark] = field(default_factory=dict)
    snow_depth: float | None = None
    new_snow: float | None = None

    @property
    def url(self) -> str:
        return PAGE_URL.format(page="start", sector=self.slug)

    @property
    def lifts_open(self) -> int:
        return sum(lift.is_open for lift in self.lifts.values())

    @property
    def slopes_open(self) -> int:
        return sum(slope.is_open for slope in self.slopes.values())

    @property
    def slopes_open_length(self) -> int:
        """In metres; slopes without a length count for nothing."""
        return sum(s.length or 0 for s in self.slopes.values() if s.is_open)


def slugify(text: str) -> str:
    """A stable key from a name: "Gütsch-Express 1. Sektion" ->
    "gutsch_express_1_sektion"."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


@dataclass
class _Node:
    tag: str
    classes: frozenset[str]
    children: list[_Node | str] = field(default_factory=list)

    def text(self) -> str:
        """The text of the node, with runs of whitespace as one space."""
        parts = [c if isinstance(c, str) else c.text() for c in self.children]
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    def find_all(self, tag: str | None = None, cls: str | None = None) -> list[_Node]:
        found = []
        for child in self.children:
            if isinstance(child, str):
                continue
            if (tag is None or child.tag == tag) and (
                cls is None or cls in child.classes
            ):
                found.append(child)
            found.extend(child.find_all(tag, cls))
        return found

    def find(self, tag: str | None = None, cls: str | None = None) -> _Node | None:
        found = self.find_all(tag, cls)
        return found[0] if found else None

    def own_texts(self, tag: str) -> list[str]:
        """The texts of the direct children with this tag."""
        return [
            c.text() for c in self.children if isinstance(c, _Node) and c.tag == tag
        ]


# Elements that never have children.
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


class _TreeBuilder(HTMLParser):
    """A forgiving tree of the page's elements, without scripts and styles.

    Comments are dropped: the site keeps old markup in them (a commented-out
    status label in each lift card), which must not be read.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", frozenset())
        self._stack = [self.root]
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        classes = frozenset((dict(attrs).get("class") or "").split())
        node = _Node(tag, classes)
        self._stack[-1].children.append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip or tag in _VOID:
            return
        # Close up to the matching element; a stray end tag is ignored.
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._stack[-1].children.append(data)


def _tree(html: str) -> _Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


def _status(row: _Node) -> str:
    for cls in row.classes:
        if cls.startswith("status-"):
            number = cls.removeprefix("status-")
            return STATUSES.get(number, f"status_{number}")
    return "unknown"


def _number(name: str) -> str | None:
    match = _NUMBER.match(name)
    return match.group(1) if match else None


def _time(text: str | None) -> str | None:
    """ "08:30", or None for the site's "–" (no rides that day)."""
    return text if text and _TIME.match(text) else None


def _rows(tree: _Node) -> list[_Node]:
    """The rows of the details list: one per lift or slope."""
    return tree.find_all("article", "anlagen-overview-row")


def _title(row: _Node) -> tuple[str, str | None]:
    """The name of the row, and the text after it (a lift's kind)."""
    title = row.find("span", "anlagen-overview-title")
    if title is None:
        raise AndermattLiveError("A row without a title")
    names = title.own_texts("strong")
    if not names or not names[0]:
        raise AndermattLiveError("A row without a name")
    rest = title.own_texts("span")
    return names[0], (rest[0] if rest and rest[0] else None)


def _details(row: _Node) -> list[str]:
    """The strong texts of the row's details: times, colour, length."""
    return [
        detail.own_texts("strong")[0] if detail.own_texts("strong") else ""
        for detail in row.find_all("div", "anlagen-overview-time")
    ]


def parse_lifts(html: str) -> dict[str, Lift]:
    lifts: dict[str, Lift] = {}
    for row in _rows(_tree(html)):
        name, kind = _title(row)
        details = _details(row)
        key = slugify(name)
        lifts[key] = Lift(
            key=key,
            name=name,
            number=_number(name),
            kind=kind,
            status=_status(row),
            first_ride=_time(details[0] if details else None),
            last_ride=_time(details[1] if len(details) > 1 else None),
        )
    return lifts


def _difficulty(text: str) -> str | None:
    word = text.lower()
    for german, difficulty in DIFFICULTIES.items():
        if word.startswith(german):
            return difficulty
    return None


def _length(texts: list[str]) -> int | None:
    for text in texts:
        if match := _LENGTH.fullmatch(text.strip()):
            return round(float(match.group(1).replace(",", ".")))
    return None


def parse_slopes(html: str) -> dict[str, Slope]:
    slopes: dict[str, Slope] = {}
    for row in _rows(_tree(html)):
        name, _ = _title(row)
        details = _details(row)
        key = slugify(name)
        slopes[key] = Slope(
            key=key,
            name=name,
            number=_number(name),
            status=_status(row),
            difficulty=next(
                (d for d in map(_difficulty, details) if d is not None), None
            ),
            length=_length(details),
        )
    return slopes


def _centimetres(text: str) -> float | None:
    match = _CENTIMETRES.search(text)
    return float(match.group(1).replace(",", ".")) if match else None


@dataclass(frozen=True)
class StartPage:
    snow_depth: float | None
    new_snow: float | None
    car_parks: dict[str, CarPark]


def parse_start(html: str) -> StartPage:
    tree = _tree(html)
    snow_depth = new_snow = None
    for label in tree.find_all("div", "weather-detail-label"):
        caption = " ".join(label.own_texts("span")).lower()
        value = _centimetres(label.text())
        if caption.startswith("schneehöhe"):
            snow_depth = value
        elif caption.startswith("neuschnee"):
            new_snow = value

    car_parks: dict[str, CarPark] = {}
    for card in tree.find_all("div", "card"):
        header = card.find("div", "header-content")
        badge = card.find("div", "parkplatz-map")
        if header is None or badge is None:
            continue
        names = header.own_texts("h3")
        spans = badge.own_texts("span")
        if not names or not spans:
            continue
        status = next(
            (c for c in badge.children if isinstance(c, _Node) and c.tag == "span"),
            None,
        )
        classes = status.classes if status else frozenset()
        free = True if "frei" in classes else False if "besetzt" in classes else None
        key = slugify(names[0])
        car_parks[key] = CarPark(key=key, name=names[0], free=free, text=spans[0])
    return StartPage(snow_depth=snow_depth, new_snow=new_snow, car_parks=car_parks)


class AndermattLiveClient:
    def __init__(self, session: aiohttp.ClientSession, user_agent: str) -> None:
        self._session = session
        self._headers = {"User-Agent": user_agent}

    async def _get(self, page: str, sector: str) -> str:
        url = PAGE_URL.format(page=page, sector=sector)
        for attempt in range(2):
            try:
                async with self._session.get(
                    url, headers=self._headers, timeout=REQUEST_TIMEOUT
                ) as response:
                    if response.status in BLOCKED_STATUSES:
                        raise AndermattLiveBlockedError(
                            f"{url} refused the request: HTTP {response.status}"
                        )
                    response.raise_for_status()
                    return await response.text()
            except AndermattLiveBlockedError:
                raise
            except (aiohttp.ClientError, TimeoutError) as err:
                if attempt:
                    raise AndermattLiveError(f"{url}: {err!r}") from err
                _LOGGER.debug("%s did not answer (%r); trying again", url, err)
                await asyncio.sleep(RETRY_DELAY)
        raise AssertionError("unreachable")

    async def async_sector(self, slug: str) -> Sector:
        """A sector, from its three pages."""
        start, lifts, slopes = [
            await self._get(page, slug) for page in ("start", "anlagen", "pisten")
        ]
        try:
            start_page = parse_start(start)
            return Sector(
                slug=slug,
                name=SECTORS.get(slug, slug),
                lifts=parse_lifts(lifts),
                slopes=parse_slopes(slopes),
                car_parks=start_page.car_parks,
                snow_depth=start_page.snow_depth,
                new_snow=start_page.new_snow,
            )
        except AndermattLiveError as err:
            raise AndermattLiveError(f"{slug}: {err}") from err

    async def async_sectors(self, slugs: list[str]) -> dict[str, Sector]:
        """The sectors, one after the other to go easy on the site."""
        return {slug: await self.async_sector(slug) for slug in slugs}

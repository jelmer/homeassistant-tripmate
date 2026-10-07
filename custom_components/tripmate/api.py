"""Client for tripmate's JSON API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from http import HTTPStatus
from typing import Any

import aiohttp
from yarl import URL

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class TripmateError(Exception):
    """Base class for errors talking to tripmate."""


class TripmateConnectionError(TripmateError):
    """Raised when tripmate could not be reached."""


class TripmateAuthError(TripmateError):
    """Raised when whatever guards tripmate does not accept our credentials."""


class TripmateResponseError(TripmateError):
    """Raised when the answer is not what tripmate's API promises."""


@dataclass(frozen=True)
class Trip:
    """A trip as stored by tripmate and listed by `/api/v1/trips`."""

    id: str
    # Only set for a trip that was named by hand.
    name: str | None
    destinations: list[str]
    start: date
    end: date

    @property
    def title(self) -> str:
        """What to call the trip: its name, or else where it goes.

        tripmate's own pages collapse several stops in one country into
        "Trip to the US". The API does not say what country a destination is
        in, so here the destinations are always listed.
        """
        if self.name is not None and self.name.strip():
            return self.name
        if not self.destinations:
            return self.id
        return f"Trip to {_join_and(self.destinations)}"


@dataclass(frozen=True)
class Coord:
    """Where a place is."""

    lat: float
    lon: float


@dataclass(frozen=True)
class Place:
    """An airport, station, hotel or venue on a reservation."""

    # What tripmate's timeline prints: the code, name or locality.
    label: str
    name: str | None
    code: str | None
    locality: str | None
    coord: Coord | None


@dataclass(frozen=True)
class Reservation:
    """One leg or stay, as listed by `/api/v1/reservations`."""

    # `flight`, `train`, `bus`, `boat`, `lodging`, `event` or `food`.
    kind: str
    # The id of the trip this was grouped into.
    trip: str
    summary: str
    provider: str | None
    reservation_number: str | None
    # The wall-clock time where it happens, which is all tripmate reports: a
    # datetime here is naive. A booking for a day rather than a time has a date.
    start: date | datetime
    end: date | datetime | None
    # Where a leg departs from, or where a stay or event is.
    origin: Place | None
    destination: Place | None


@dataclass(frozen=True)
class Travelled:
    """Journeys of one kind of travel, and how far they went."""

    journeys: int
    # Journeys tripmate could not place both ends of. While this is not
    # zero the distance is a lower bound.
    unknown_route: int
    distance_km: int


@dataclass(frozen=True)
class Stats:
    """Totals over every trip tripmate knows, past and future."""

    trips: int
    nights: int
    flights: Travelled
    trains: Travelled
    # Flights, trains, buses and ferries together.
    travel: Travelled
    # ISO 3166-1 alpha-2 codes of the countries any reservation touched.
    countries: list[str]


def _join_and(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _parse_moment(raw: str) -> date | datetime:
    """Parse `2026-05-14` or `2026-05-14 07:25`."""
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return datetime.fromisoformat(raw)


def _optional[T](parse: Callable[[Any], T], raw: Any) -> T | None:
    return None if raw is None else parse(raw)


def _parse_trip(raw: dict[str, Any]) -> Trip:
    return Trip(
        id=raw["id"],
        # tripmate leaves out what a trip does not have.
        name=raw.get("name"),
        destinations=list(raw.get("destinations", [])),
        start=date.fromisoformat(raw["start"]),
        end=date.fromisoformat(raw["end"]),
    )


def _parse_coord(raw: dict[str, Any]) -> Coord:
    return Coord(lat=float(raw["lat"]), lon=float(raw["lon"]))


def _parse_place(raw: dict[str, Any]) -> Place:
    return Place(
        label=raw["label"],
        name=raw.get("name"),
        code=raw.get("code"),
        locality=raw.get("locality"),
        coord=_optional(_parse_coord, raw.get("coord")),
    )


def _parse_reservation(raw: dict[str, Any]) -> Reservation:
    return Reservation(
        kind=raw["kind"],
        trip=raw["trip"],
        summary=raw["summary"],
        provider=raw.get("provider"),
        reservation_number=raw.get("reservation_number"),
        start=_parse_moment(raw["start"]),
        end=_optional(_parse_moment, raw.get("end")),
        origin=_optional(_parse_place, raw.get("origin")),
        destination=_optional(_parse_place, raw.get("destination")),
    )


def _parse_travelled(raw: dict[str, Any]) -> Travelled:
    return Travelled(
        journeys=raw["journeys"],
        unknown_route=raw["unknown_route"],
        distance_km=raw["distance_km"],
    )


def _parse_stats(raw: dict[str, Any]) -> Stats:
    return Stats(
        trips=raw["trips"],
        nights=raw["nights"],
        flights=_parse_travelled(raw["flights"]),
        trains=_parse_travelled(raw["trains"]),
        travel=_parse_travelled(raw["travel"]),
        countries=list(raw["countries"]),
    )


def _parse_list[T](parse: Callable[[dict[str, Any]], T]) -> Callable[[Any], list[T]]:
    def parse_all(raw: Any) -> list[T]:
        if not isinstance(raw, list):
            raise TypeError(f"expected a list, not {type(raw).__name__}")
        return [parse(item) for item in raw]

    return parse_all


async def _error_message(response: aiohttp.ClientResponse) -> str | None:
    """Return what tripmate says went wrong, if this is tripmate saying so.

    tripmate reports its own errors as `{"error": "..."}`.
    """
    try:
        body = await response.json()
    except (aiohttp.ContentTypeError, ValueError):
        return None
    if not isinstance(body, dict) or not isinstance(body.get("error"), str):
        return None
    return body["error"]


class TripmateClient:
    """Client for a tripmate instance."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Create a client.

        tripmate has no authentication of its own. `username` and `password`
        are for a reverse proxy in front of it that asks for HTTP basic auth.
        """
        self._session = session
        self._base = URL(url)
        self._headers = (
            {}
            if username is None
            else {"Authorization": aiohttp.encode_basic_auth(username, password or "")}
        )

    async def trips(self) -> list[Trip]:
        """Fetch the trips tripmate has stored.

        tripmate files newly inferred trips while it answers `reservations`
        or `stats`, not this, so ask one of those first to see the trips that
        bookings which just arrived belong to.
        """
        url = self._base.joinpath("api", "v1", "trips")
        return await self._fetch(url, _parse_list(_parse_trip))

    async def reservations(
        self, start: date | None = None, end: date | None = None
    ) -> list[Reservation]:
        """Fetch the reservations that overlap a range of dates, both inclusive."""
        query = {}
        if start is not None:
            query["from"] = start.isoformat()
        if end is not None:
            query["to"] = end.isoformat()
        url = self._base.joinpath("api", "v1", "reservations").with_query(query)
        return await self._fetch(url, _parse_list(_parse_reservation))

    async def stats(self) -> Stats:
        """Fetch the totals over every trip."""
        url = self._base.joinpath("api", "v1", "stats")
        return await self._fetch(url, _parse_stats)

    async def _fetch[T](self, url: URL, parse: Callable[[Any], T]) -> T:
        body = await self._get(url)
        try:
            return parse(body)
        except (KeyError, TypeError, ValueError) as err:
            raise TripmateResponseError(
                f"{url} returned an unexpected document: {err!r}"
            ) from err

    async def _get(self, url: URL) -> Any:
        try:
            async with self._session.get(
                url, headers=self._headers, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status == HTTPStatus.OK:
                    return await response.json()
                reason = await _error_message(response)
                # tripmate itself answers 403 when it has nowhere to store
                # trips, which no other credentials would fix.
                if response.status == HTTPStatus.UNAUTHORIZED or (
                    response.status == HTTPStatus.FORBIDDEN and reason is None
                ):
                    raise TripmateAuthError(
                        f"{url} refused the credentials (HTTP {response.status})"
                    )
                message = f"{url} returned HTTP {response.status}"
                if reason is not None:
                    message = f"{message}: {reason}"
                raise TripmateResponseError(message)
        except aiohttp.ClientResponseError as err:
            raise TripmateResponseError(f"{url} did not return JSON: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TripmateConnectionError(f"Unable to reach {url}: {err}") from err
        except ValueError as err:
            raise TripmateResponseError(f"{url} returned invalid JSON: {err}") from err

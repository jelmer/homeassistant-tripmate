"""Tests for the tripmate API client."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date, datetime
from typing import Any

import aiohttp
import pytest
from aiohttp import test_utils, web
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from yarl import URL

from custom_components.tripmate.api import (
    Coord,
    Place,
    Reservation,
    Stats,
    Trip,
    TripmateAuthError,
    TripmateClient,
    TripmateConnectionError,
    TripmateResponseError,
)

from . import (
    BASE_URL,
    FLIGHT_TO_TOKYO,
    HOTEL_IN_KYOTO,
    JAPAN,
    LISBON,
    STATS,
    mock_api,
)

EXPECTED_STATS = Stats(
    trips=4,
    nights=18,
    flights=3,
    distance_km=13284,
    countries=["GB", "JP", "NL", "PT"],
)


@pytest.fixture
async def client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> TripmateClient:
    # Depends on the mocker so the session is created after it is in place.
    return TripmateClient(async_get_clientsession(hass), BASE_URL)


async def test_trips(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_api(aioclient_mock, trips=[LISBON, JAPAN])

    assert await client.trips() == [
        Trip(
            id="2026-05-lisbon",
            name=None,
            destinations=["Lisbon"],
            start=date(2026, 5, 14),
            end=date(2026, 5, 17),
        ),
        Trip(
            id="2026-09-japan",
            name="Autumn in Japan",
            destinations=["Japan"],
            start=date(2026, 9, 28),
            end=date(2026, 10, 9),
        ),
    ]


async def test_a_trip_without_destinations(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    # What tripmate stores for a trip created empty.
    trip = {
        "id": "2027-01-japan",
        "start": "2027-01-10",
        "end": "2027-01-24",
        "reservations": [],
    }
    mock_api(aioclient_mock, trips=[trip])

    assert await client.trips() == [
        Trip(
            id="2027-01-japan",
            name=None,
            destinations=[],
            start=date(2027, 1, 10),
            end=date(2027, 1, 24),
        )
    ]


@pytest.mark.parametrize(
    ("name", "destinations", "title"),
    [
        ("RustWeek", ["Netherlands"], "RustWeek"),
        (None, ["Lisbon"], "Trip to Lisbon"),
        (None, ["Berlin", "Prague"], "Trip to Berlin and Prague"),
        (None, ["Boston", "Chicago", "Denver"], "Trip to Boston, Chicago and Denver"),
        (" ", ["Lisbon"], "Trip to Lisbon"),
        (None, [], "2026-05-lisbon"),
    ],
)
def test_trip_title(name: str | None, destinations: list[str], title: str) -> None:
    trip = Trip(
        id="2026-05-lisbon",
        name=name,
        destinations=destinations,
        start=date(2026, 5, 14),
        end=date(2026, 5, 17),
    )

    assert trip.title == title


async def test_reservations(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_api(aioclient_mock, reservations=[FLIGHT_TO_TOKYO, HOTEL_IN_KYOTO])

    assert await client.reservations() == [
        Reservation(
            kind="flight",
            trip="2026-09-japan",
            summary="NH212: LHR to HND",
            provider="ANA",
            reservation_number="J7K2LM",
            # Without a time zone, as tripmate only reports the local time.
            start=datetime(2026, 9, 28, 19, 0),  # noqa: DTZ001
            end=datetime(2026, 9, 29, 15, 50),  # noqa: DTZ001
            origin=Place(label="LHR", name=None, code="LHR", locality=None, coord=None),
            destination=Place(
                label="HND", name=None, code="HND", locality=None, coord=None
            ),
        ),
        Reservation(
            kind="lodging",
            trip="2026-09-japan",
            summary="Stay at Hotel Granvia Kyoto",
            provider="Hotel Granvia Kyoto",
            reservation_number="88341",
            start=date(2026, 9, 30),
            end=date(2026, 10, 8),
            origin=Place(
                label="Hotel Granvia Kyoto",
                name="Hotel Granvia Kyoto",
                code=None,
                locality="Kyoto",
                coord=Coord(lat=34.9858, lon=135.7588),
            ),
            destination=None,
        ),
    ]


@pytest.mark.parametrize(
    ("start", "end", "query"),
    [
        (None, None, ""),
        (date(2026, 9, 28), None, "?from=2026-09-28"),
        (None, date(2026, 11, 2), "?to=2026-11-02"),
        (date(2026, 9, 28), date(2026, 11, 2), "?from=2026-09-28&to=2026-11-02"),
    ],
)
async def test_reservations_are_asked_for_by_date(
    client: TripmateClient,
    aioclient_mock: AiohttpClientMocker,
    start: date | None,
    end: date | None,
    query: str,
) -> None:
    mock_api(aioclient_mock)

    await client.reservations(start=start, end=end)

    [(method, url, _data, _headers)] = aioclient_mock.mock_calls
    assert (method, url) == ("GET", URL(f"{BASE_URL}/api/v1/reservations{query}"))


async def test_stats(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_api(aioclient_mock)

    assert await client.stats() == EXPECTED_STATS


@pytest.mark.parametrize(
    "base_url", ["http://tripmate.test/tripmate", "http://tripmate.test/tripmate/"]
)
async def test_base_path_is_kept(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, base_url: str
) -> None:
    mock_api(aioclient_mock, base_url="http://tripmate.test/tripmate")
    client = TripmateClient(async_get_clientsession(hass), base_url)

    assert await client.stats() == EXPECTED_STATS


@pytest.mark.parametrize(
    "document",
    [
        # A trip missing a field.
        [{"id": "2026-05-lisbon", "start": "2026-05-14"}],
        [{**LISBON, "start": "in May"}],
        [{**LISBON, "end": None}],
        ["2026-05-lisbon"],
        {"trips": [LISBON]},
    ],
)
async def test_unexpected_trips_are_an_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker, document: Any
) -> None:
    mock_api(aioclient_mock, trips=document)

    with pytest.raises(TripmateResponseError):
        await client.trips()


@pytest.mark.parametrize(
    "document",
    [
        [{"source": "2026/eurostar-m2grpc.json", "kind": "train"}],
        [{**FLIGHT_TO_TOKYO, "start": "19:00"}],
        [{**FLIGHT_TO_TOKYO, "end": "later"}],
        [{**HOTEL_IN_KYOTO, "origin": {"name": "Hotel Granvia Kyoto"}}],
        [{**HOTEL_IN_KYOTO, "origin": {"label": "Hotel", "coord": {"lat": 34.9}}}],
        {"reservations": []},
    ],
)
async def test_unexpected_reservations_are_an_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker, document: Any
) -> None:
    mock_api(aioclient_mock, reservations=document)

    with pytest.raises(TripmateResponseError):
        await client.reservations()


@pytest.mark.parametrize(
    "document",
    [
        {"trips": 4, "nights": 18, "flights": 3},
        {**STATS, "countries": None},
        [STATS],
    ],
)
async def test_unexpected_stats_are_an_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker, document: Any
) -> None:
    mock_api(aioclient_mock, stats=document)

    with pytest.raises(TripmateResponseError):
        await client.stats()


async def test_an_http_error_is_an_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{BASE_URL}/api/v1/stats", status=502, text="Bad Gateway")

    with pytest.raises(
        TripmateResponseError, match=r"^http://\S+/api/v1/stats returned HTTP 502$"
    ):
        await client.stats()


async def test_what_tripmate_says_went_wrong_is_passed_on(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        f"{BASE_URL}/api/v1/stats",
        status=500,
        json={"error": "reading trips: permission denied"},
    )

    with pytest.raises(
        TripmateResponseError, match="HTTP 500: reading trips: permission denied$"
    ):
        await client.stats()


async def test_a_body_that_is_not_json_is_an_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{BASE_URL}/api/v1/stats", text="<html>hello</html>")

    with pytest.raises(TripmateResponseError):
        await client.stats()


@pytest.mark.parametrize(
    "error", [aiohttp.ClientConnectionError("refused"), TimeoutError()]
)
async def test_failing_to_connect_is_a_connection_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker, error: Exception
) -> None:
    aioclient_mock.get(f"{BASE_URL}/api/v1/trips", exc=error)

    with pytest.raises(TripmateConnectionError):
        await client.trips()


@pytest.mark.parametrize("status", [401, 403])
async def test_refused_credentials_are_an_auth_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    aioclient_mock.get(f"{BASE_URL}/api/v1/stats", status=status)

    with pytest.raises(TripmateAuthError, match=f"HTTP {status}"):
        await client.stats()


async def test_tripmate_refusing_for_its_own_reasons_is_not_an_auth_error(
    client: TripmateClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        f"{BASE_URL}/api/v1/trips",
        status=403,
        json={"error": "no trips directory configured"},
    )

    with pytest.raises(
        TripmateResponseError, match="HTTP 403: no trips directory configured$"
    ) as raised:
        await client.trips()

    assert not isinstance(raised.value, TripmateAuthError)


@pytest.fixture
async def guarded_tripmate(
    socket_enabled: None,
) -> AsyncGenerator[test_utils.TestServer]:
    """A real server that only answers `someone` with the password `secret`."""

    async def stats(request: web.Request) -> web.Response:
        expected = aiohttp.encode_basic_auth("someone", "secret")
        if request.headers.get("Authorization") != expected:
            return web.Response(status=401, headers={"WWW-Authenticate": "Basic"})
        return web.json_response(STATS)

    app = web.Application()
    app.router.add_get("/api/v1/stats", stats)
    server = test_utils.TestServer(app)
    await server.start_server()
    try:
        yield server
    finally:
        await server.close()


@pytest.mark.parametrize(
    ("username", "password"),
    [(None, None), ("someone", None), ("someone", "wrong"), ("other", "secret")],
)
async def test_basic_auth_is_needed_where_a_proxy_asks_for_it(
    guarded_tripmate: test_utils.TestServer, username: str | None, password: str | None
) -> None:
    async with aiohttp.ClientSession() as session:
        client = TripmateClient(
            session, str(guarded_tripmate.make_url("")), username, password
        )

        with pytest.raises(TripmateAuthError):
            await client.stats()


async def test_basic_auth_is_sent(guarded_tripmate: test_utils.TestServer) -> None:
    async with aiohttp.ClientSession() as session:
        client = TripmateClient(
            session, str(guarded_tripmate.make_url("")), "someone", "secret"
        )

        assert await client.stats() == EXPECTED_STATS

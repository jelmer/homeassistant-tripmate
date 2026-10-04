"""Tests for what the tripmate coordinator asks for."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from yarl import URL

from . import BASE_URL, LISBON, mock_api


def _requests(aioclient_mock: AiohttpClientMocker) -> list[tuple[str, URL]]:
    return [(method, url) for method, url, _data, _headers in aioclient_mock.mock_calls]


async def test_a_poll_asks_for_the_stats_before_the_trips(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    # The reservations are asked for from the start of the trip under way.
    assert _requests(aioclient_mock) == [
        ("GET", URL(f"{BASE_URL}/api/v1/stats")),
        ("GET", URL(f"{BASE_URL}/api/v1/trips")),
        ("GET", URL(f"{BASE_URL}/api/v1/reservations?from=2026-09-28")),
    ]


async def test_reservations_are_not_asked_for_when_every_trip_is_over(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    mock_api(aioclient_mock, trips=[LISBON])
    aioclient_mock.mock_calls.clear()

    await tick()

    assert _requests(aioclient_mock) == [
        ("GET", URL(f"{BASE_URL}/api/v1/stats")),
        ("GET", URL(f"{BASE_URL}/api/v1/trips")),
    ]

"""Tests for the tripmate calendar."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from . import BASE_URL, LISBON, mock_api

ENTITY_ID = "calendar.tripmate_trips"

LISBON_EVENT = {
    "start": "2026-05-14",
    "end": "2026-05-18",
    "summary": "Trip to Lisbon",
    "description": f"{BASE_URL}/trip/2026-05-lisbon",
    "location": "Lisbon",
}
JAPAN_EVENT = {
    "start": "2026-09-28",
    "end": "2026-10-10",
    "summary": "Autumn in Japan",
    "description": f"{BASE_URL}/trip/2026-09-japan",
    "location": "Japan",
}
ROTTERDAM_EVENT = {
    "start": "2026-11-02",
    "end": "2026-11-03",
    "summary": "Trip to Rotterdam",
    "description": f"{BASE_URL}/trip/2026-11-rotterdam",
    "location": "Rotterdam",
}
BERLIN_EVENT = {
    "start": "2027-01-10",
    "end": "2027-01-15",
    "summary": "Trip to Berlin and Prague",
    "description": f"{BASE_URL}/trip/2027-01-berlin",
    "location": "Berlin, Prague",
}


def _state(hass: HomeAssistant) -> tuple[str, dict[str, Any]]:
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    attributes = dict(state.attributes)
    del attributes["friendly_name"]
    return state.state, attributes


async def _events(hass: HomeAssistant, start: str, end: str) -> Any:
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": ENTITY_ID, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    calendar: Any = response[ENTITY_ID]
    return calendar["events"]


async def test_the_calendar_is_on_during_a_trip(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert _state(hass) == (
        STATE_ON,
        {
            "message": "Autumn in Japan",
            "all_day": True,
            "start_time": "2026-09-28 00:00:00",
            "end_time": "2026-10-10 00:00:00",
            "location": "Japan",
            "description": f"{BASE_URL}/trip/2026-09-japan",
        },
    )


async def test_between_trips_the_calendar_shows_the_next_one(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    freezer.move_to("2026-10-10 12:00:00+00:00")
    await tick()

    assert _state(hass) == (
        STATE_OFF,
        {
            "message": "Trip to Rotterdam",
            "all_day": True,
            "start_time": "2026-11-02 00:00:00",
            "end_time": "2026-11-03 00:00:00",
            "location": "Rotterdam",
            "description": f"{BASE_URL}/trip/2026-11-rotterdam",
        },
    )


async def test_with_nothing_booked_the_calendar_shows_no_event(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    mock_api(aioclient_mock, trips=[LISBON])

    await tick()

    assert _state(hass) == (STATE_OFF, {})


@pytest.mark.parametrize(
    ("start", "end", "events"),
    [
        (
            "2026-01-01 00:00:00",
            "2028-01-01 00:00:00",
            [LISBON_EVENT, JAPAN_EVENT, ROTTERDAM_EVENT, BERLIN_EVENT],
        ),
        ("2026-10-01 00:00:00", "2026-12-01 00:00:00", [JAPAN_EVENT, ROTTERDAM_EVENT]),
        # A trip takes up the whole of its last day, and none of the next.
        ("2026-10-09 23:00:00", "2026-10-09 23:30:00", [JAPAN_EVENT]),
        ("2026-10-10 00:00:00", "2026-11-02 00:00:00", []),
        ("2026-11-02 00:00:00", "2026-11-02 01:00:00", [ROTTERDAM_EVENT]),
    ],
)
async def test_events_are_the_trips_that_overlap_the_range(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    start: str,
    end: str,
    events: list[dict[str, Any]],
) -> None:
    assert await _events(hass, start, end) == events


async def test_a_trip_without_destinations_has_no_location(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    empty = {
        "id": "2027-03-somewhere",
        "start": "2027-03-01",
        "end": "2027-03-03",
        "reservations": [],
    }
    mock_api(aioclient_mock, trips=[empty])

    await tick()

    assert await _events(hass, "2027-03-01 00:00:00", "2027-03-02 00:00:00") == [
        {
            "start": "2027-03-01",
            "end": "2027-03-04",
            "summary": "2027-03-somewhere",
            "description": f"{BASE_URL}/trip/2027-03-somewhere",
        }
    ]

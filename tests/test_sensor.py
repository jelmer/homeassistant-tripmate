"""Tests for the tripmate sensors."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from . import (
    BASE_URL,
    BERLIN,
    FLIGHT_TO_TOKYO,
    JAPAN,
    LISBON,
    ROTTERDAM,
    TRAIN_TO_ROTTERDAM,
    mock_api,
)

JAPAN_ATTRIBUTES = {
    "id": "2026-09-japan",
    "name": "Autumn in Japan",
    "destinations": ["Japan"],
    "start": "2026-09-28",
    "end": "2026-10-09",
    "url": f"{BASE_URL}/trip/2026-09-japan",
}
ROTTERDAM_ATTRIBUTES = {
    "id": "2026-11-rotterdam",
    "name": "Trip to Rotterdam",
    "destinations": ["Rotterdam"],
    "start": "2026-11-02",
    "end": "2026-11-02",
    "url": f"{BASE_URL}/trip/2026-11-rotterdam",
}
BERLIN_ATTRIBUTES = {
    "id": "2027-01-berlin",
    "name": "Trip to Berlin and Prague",
    "destinations": ["Berlin", "Prague"],
    "start": "2027-01-10",
    "end": "2027-01-14",
    "url": f"{BASE_URL}/trip/2027-01-berlin",
}


def _place(label: str, **fields: Any) -> dict[str, Any]:
    return {
        "label": label,
        "name": None,
        "code": None,
        "locality": None,
        "latitude": None,
        "longitude": None,
        **fields,
    }


FLIGHT_ATTRIBUTES = {
    "kind": "flight",
    "summary": "NH212: LHR to HND",
    "provider": "ANA",
    "reservation_number": "J7K2LM",
    "start": "2026-09-28T19:00:00",
    "end": "2026-09-29T15:50:00",
    "origin": _place("LHR", code="LHR"),
    "destination": _place("HND", code="HND"),
}
HOTEL_ATTRIBUTES = {
    "kind": "lodging",
    "summary": "Stay at Hotel Granvia Kyoto",
    "provider": "Hotel Granvia Kyoto",
    "reservation_number": "88341",
    "start": "2026-09-30",
    "end": "2026-10-08",
    "origin": _place(
        "Hotel Granvia Kyoto",
        name="Hotel Granvia Kyoto",
        locality="Kyoto",
        latitude=34.9858,
        longitude=135.7588,
    ),
    "destination": None,
}
TRAIN_ATTRIBUTES = {
    "kind": "train",
    "summary": "9114: London St Pancras Int'l to Rotterdam Centraal",
    "provider": "Eurostar",
    "reservation_number": "M2GRPC",
    "start": "2026-11-02T08:16:00",
    "end": "2026-11-02T12:32:00",
    "origin": _place("London St Pancras Int'l", name="London St Pancras Int'l"),
    "destination": _place("Rotterdam Centraal", name="Rotterdam Centraal"),
}


def _state(hass: HomeAssistant, entity_id: str) -> tuple[str, dict[str, Any]]:
    """Return an entity's state and attributes, without its name."""
    state = hass.states.get(entity_id)
    assert state is not None
    attributes = dict(state.attributes)
    del attributes["friendly_name"]
    return state.state, attributes


async def test_current_trip(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    assert _state(hass, "sensor.tripmate_current_trip") == (
        "Autumn in Japan",
        {**JAPAN_ATTRIBUTES, "reservations": [FLIGHT_ATTRIBUTES, HOTEL_ATTRIBUTES]},
    )
    assert _state(hass, "sensor.tripmate_current_trip_end") == (
        "2026-10-09",
        {"device_class": "date"},
    )


async def test_next_trip(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    assert _state(hass, "sensor.tripmate_next_trip") == (
        "Trip to Rotterdam",
        {**ROTTERDAM_ATTRIBUTES, "reservations": [TRAIN_ATTRIBUTES]},
    )
    assert _state(hass, "sensor.tripmate_next_trip_start") == (
        "2026-11-02",
        {"device_class": "date"},
    )


async def test_upcoming_trips(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert _state(hass, "sensor.tripmate_upcoming_trips") == (
        "2",
        {
            "trips": [ROTTERDAM_ATTRIBUTES, BERLIN_ATTRIBUTES],
            "state_class": "measurement",
            "unit_of_measurement": "trips",
        },
    )


@pytest.mark.parametrize(
    ("entity_id", "value", "attributes"),
    [
        ("sensor.tripmate_total_trips", "4", {"unit_of_measurement": "trips"}),
        ("sensor.tripmate_nights_away", "18", {"unit_of_measurement": "nights"}),
        ("sensor.tripmate_flights", "3", {"unit_of_measurement": "flights"}),
        (
            "sensor.tripmate_distance_flown",
            "13284",
            {"unit_of_measurement": "km", "device_class": "distance"},
        ),
        (
            "sensor.tripmate_countries",
            "4",
            {
                "unit_of_measurement": "countries",
                "countries": ["GB", "JP", "NL", "PT"],
            },
        ),
    ],
)
async def test_stats_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    value: str,
    attributes: dict[str, Any],
) -> None:
    assert _state(hass, entity_id) == (value, {**attributes, "state_class": "total"})


async def test_between_trips_there_is_no_current_trip(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    mock_api(aioclient_mock, trips=[LISBON, ROTTERDAM])

    await tick()

    assert _state(hass, "sensor.tripmate_current_trip") == (STATE_UNKNOWN, {})
    assert _state(hass, "sensor.tripmate_current_trip_end") == (
        STATE_UNKNOWN,
        {"device_class": "date"},
    )
    assert _state(hass, "sensor.tripmate_next_trip")[0] == "Trip to Rotterdam"


async def test_with_nothing_booked_there_is_no_next_trip(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    mock_api(aioclient_mock, trips=[LISBON, JAPAN])

    await tick()

    assert _state(hass, "sensor.tripmate_next_trip") == (STATE_UNKNOWN, {})
    assert _state(hass, "sensor.tripmate_next_trip_start") == (
        STATE_UNKNOWN,
        {"device_class": "date"},
    )
    assert _state(hass, "sensor.tripmate_upcoming_trips") == (
        "0",
        {"trips": [], "state_class": "measurement", "unit_of_measurement": "trips"},
    )


async def test_a_trip_ends_after_its_last_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    freezer.move_to("2026-10-09 22:00:00+00:00")
    await tick()

    assert _state(hass, "sensor.tripmate_current_trip")[0] == "Autumn in Japan"

    freezer.move_to("2026-10-10 12:00:00+00:00")
    await tick()

    assert _state(hass, "sensor.tripmate_current_trip") == (STATE_UNKNOWN, {})


async def test_a_trip_starts_on_its_first_day_in_the_configured_time_zone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    # Still the 1st in UTC, but already the 2nd in Amsterdam.
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-01 23:30:00+00:00")

    await tick()

    assert _state(hass, "sensor.tripmate_current_trip") == (
        "Trip to Rotterdam",
        {**ROTTERDAM_ATTRIBUTES, "reservations": [TRAIN_ATTRIBUTES]},
    )
    assert _state(hass, "sensor.tripmate_next_trip")[0] == "Trip to Berlin and Prague"


async def test_of_overlapping_trips_the_one_begun_last_is_current(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    side_trip = {
        "id": "2026-10-osaka",
        "destinations": ["Osaka"],
        "start": "2026-10-04",
        "end": "2026-10-06",
        "reservations": [],
    }
    mock_api(aioclient_mock, trips=[side_trip, JAPAN])

    await tick()

    state, attributes = _state(hass, "sensor.tripmate_current_trip")
    assert (state, attributes["reservations"]) == ("Trip to Osaka", [])


async def test_a_reservation_of_a_trip_that_is_over_is_left_out(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    # The range of dates asked for can catch one.
    stray = {**TRAIN_TO_ROTTERDAM, "trip": "2026-05-lisbon"}
    mock_api(aioclient_mock, reservations=[FLIGHT_TO_TOKYO, stray])

    await tick()

    _, attributes = _state(hass, "sensor.tripmate_current_trip")
    assert attributes["reservations"] == [FLIGHT_ATTRIBUTES]
    _, attributes = _state(hass, "sensor.tripmate_next_trip")
    assert attributes["reservations"] == []


async def test_sensors_follow_tripmate(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    mock_api(aioclient_mock, trips=[JAPAN, BERLIN])

    await tick()

    assert _state(hass, "sensor.tripmate_next_trip")[0] == "Trip to Berlin and Prague"
    assert _state(hass, "sensor.tripmate_upcoming_trips")[0] == "1"


async def test_sensors_are_unavailable_while_tripmate_is_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE_URL}/api/v1/stats", status=500)

    await tick()

    assert _state(hass, "sensor.tripmate_current_trip")[0] == STATE_UNAVAILABLE

    mock_api(aioclient_mock)
    await tick()

    assert _state(hass, "sensor.tripmate_current_trip")[0] == "Autumn in Japan"

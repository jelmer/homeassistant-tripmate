"""Tests for the tripmate binary sensor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from . import BASE_URL

ENTITY_ID = "binary_sensor.tripmate_travelling"


def _state(hass: HomeAssistant) -> str:
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    return state.state


async def test_travelling_is_on_during_a_trip(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert _state(hass) == STATE_ON


async def test_travelling_is_off_between_trips(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    freezer.move_to("2026-10-10 12:00:00+00:00")
    await tick()

    assert _state(hass) == STATE_OFF

    # The day of the trip to Rotterdam.
    freezer.move_to("2026-11-02 12:00:00+00:00")
    await tick()

    assert _state(hass) == STATE_ON


async def test_travelling_is_unavailable_while_tripmate_is_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tick: Callable[[], Awaitable[None]],
    config_entry: MockConfigEntry,
) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE_URL}/api/v1/stats", status=500)

    await tick()

    assert _state(hass) == STATE_UNAVAILABLE

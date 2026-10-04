"""Tests for setting the tripmate integration up and tearing it down."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_URL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.tripmate.const import DOMAIN

from . import BASE_URL


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert config_entry.state is ConfigEntryState.LOADED
    [device] = dr.async_entries_for_config_entry(
        dr.async_get(hass), config_entry.entry_id
    )
    assert device.identifiers == {(DOMAIN, config_entry.entry_id)}
    assert device.name == "Tripmate"
    assert device.configuration_url == BASE_URL

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get("sensor.tripmate_upcoming_trips")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_setup_is_retried_while_tripmate_is_unreachable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    error = aiohttp.ClientConnectionError("refused")
    aioclient_mock.get(f"{BASE_URL}/api/v1/stats", exc=error)
    entry = MockConfigEntry(domain=DOMAIN, title="Tripmate", data={CONF_URL: BASE_URL})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_with_refused_credentials_asks_for_new_ones(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{BASE_URL}/api/v1/stats", status=401)
    entry = MockConfigEntry(domain=DOMAIN, title="Tripmate", data={CONF_URL: BASE_URL})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    [flow] = hass.config_entries.flow.async_progress()
    assert flow["context"]["source"] == SOURCE_REAUTH

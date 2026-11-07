"""The wayfare integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WayfareClient
from .coordinator import WayfareConfigEntry, WayfareCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: WayfareConfigEntry) -> bool:
    """Set up wayfare from a config entry."""
    client = WayfareClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )
    coordinator = WayfareCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WayfareConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

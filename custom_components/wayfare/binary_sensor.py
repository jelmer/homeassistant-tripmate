"""Binary sensor platform for wayfare."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import WayfareConfigEntry, WayfareCoordinator
from .entity import WayfareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WayfareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up wayfare binary sensor entities."""
    async_add_entities([TravellingSensor(entry.runtime_data, entry)])


class TravellingSensor(WayfareEntity, BinarySensorEntity):
    """Whether a trip is under way."""

    def __init__(
        self, coordinator: WayfareCoordinator, entry: WayfareConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "travelling")

    @property
    def is_on(self) -> bool:
        """Return whether today falls within a trip."""
        return self.coordinator.data.current_trip(dt_util.now().date()) is not None

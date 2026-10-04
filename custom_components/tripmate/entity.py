"""Base entity for the tripmate integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from yarl import URL

from .api import Place, Reservation, Trip
from .const import DOMAIN
from .coordinator import TripmateConfigEntry, TripmateCoordinator


class TripmateEntity(CoordinatorEntity[TripmateCoordinator]):
    """An entity backed by a tripmate instance."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TripmateCoordinator, entry: TripmateConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._base_url = URL(entry.data[CONF_URL])
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data[CONF_URL],
        )

    def _trip_url(self, trip: Trip) -> str:
        """Return the address of the trip's page in tripmate."""
        return str(self._base_url.joinpath("trip", trip.id))

    def _trip_attributes(self, trip: Trip) -> dict[str, Any]:
        """Describe a trip in a form that fits in state attributes."""
        return {
            "id": trip.id,
            "name": trip.title,
            "destinations": trip.destinations,
            "start": trip.start.isoformat(),
            "end": trip.end.isoformat(),
            "url": self._trip_url(trip),
        }


def _place_attributes(place: Place | None) -> dict[str, Any] | None:
    if place is None:
        return None
    return {
        "label": place.label,
        "name": place.name,
        "code": place.code,
        "locality": place.locality,
        "latitude": None if place.coord is None else place.coord.lat,
        "longitude": None if place.coord is None else place.coord.lon,
    }


def reservation_attributes(reservation: Reservation) -> dict[str, Any]:
    """Describe a reservation in a form that fits in state attributes."""
    return {
        "kind": reservation.kind,
        "summary": reservation.summary,
        "provider": reservation.provider,
        "reservation_number": reservation.reservation_number,
        "start": reservation.start.isoformat(),
        "end": None if reservation.end is None else reservation.end.isoformat(),
        "origin": _place_attributes(reservation.origin),
        "destination": _place_attributes(reservation.destination),
    }

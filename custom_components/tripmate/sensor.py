"""Sensor platform for tripmate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Stats, Trip
from .coordinator import TripmateConfigEntry, TripmateCoordinator, TripmateData
from .entity import TripmateEntity, reservation_attributes

UNIT_TRIPS = "trips"


@dataclass(frozen=True, kw_only=True)
class TripSensorDescription(SensorEntityDescription):
    """A sensor about one trip: the one under way, or the next one."""

    trip_fn: Callable[[TripmateData, date], Trip | None]
    value_fn: Callable[[Trip], str | date]
    # Whether the attributes describe the trip and list its reservations.
    detailed: bool = False


@dataclass(frozen=True, kw_only=True)
class StatsSensorDescription(SensorEntityDescription):
    """A sensor reporting one of tripmate's totals."""

    value_fn: Callable[[Stats], int]
    attributes_fn: Callable[[Stats], dict[str, Any]] | None = None


TRIP_SENSORS = (
    TripSensorDescription(
        key="current_trip",
        trip_fn=TripmateData.current_trip,
        value_fn=lambda trip: trip.title,
        detailed=True,
    ),
    TripSensorDescription(
        key="current_trip_end",
        device_class=SensorDeviceClass.DATE,
        trip_fn=TripmateData.current_trip,
        value_fn=lambda trip: trip.end,
    ),
    TripSensorDescription(
        key="next_trip",
        trip_fn=TripmateData.next_trip,
        value_fn=lambda trip: trip.title,
        detailed=True,
    ),
    TripSensorDescription(
        key="next_trip_start",
        device_class=SensorDeviceClass.DATE,
        trip_fn=TripmateData.next_trip,
        value_fn=lambda trip: trip.start,
    ),
)

STATS_SENSORS = (
    StatsSensorDescription(
        key="trips",
        native_unit_of_measurement=UNIT_TRIPS,
        value_fn=lambda stats: stats.trips,
    ),
    StatsSensorDescription(
        key="nights",
        native_unit_of_measurement="nights",
        value_fn=lambda stats: stats.nights,
    ),
    StatsSensorDescription(
        key="flights",
        native_unit_of_measurement="flights",
        value_fn=lambda stats: stats.flights,
    ),
    StatsSensorDescription(
        key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda stats: stats.distance_km,
    ),
    StatsSensorDescription(
        key="countries",
        native_unit_of_measurement="countries",
        value_fn=lambda stats: len(stats.countries),
        attributes_fn=lambda stats: {"countries": stats.countries},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TripmateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tripmate sensor entities."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        TripSensor(coordinator, entry, description) for description in TRIP_SENSORS
    ]
    entities.append(UpcomingTripsSensor(coordinator, entry))
    entities.extend(
        StatsSensor(coordinator, entry, description) for description in STATS_SENSORS
    )
    async_add_entities(entities)


class TripSensor(TripmateEntity, SensorEntity):
    """Something about the trip under way or the next one, if there is one."""

    entity_description: TripSensorDescription
    # The list grows with the trip and would bloat the recorder.
    _unrecorded_attributes = frozenset({"reservations"})

    def __init__(
        self,
        coordinator: TripmateCoordinator,
        entry: TripmateConfigEntry,
        description: TripSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def _trip(self) -> Trip | None:
        return self.entity_description.trip_fn(
            self.coordinator.data, dt_util.now().date()
        )

    @property
    def native_value(self) -> str | date | None:
        """Return the value for the trip, or nothing without a trip."""
        trip = self._trip
        return None if trip is None else self.entity_description.value_fn(trip)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the trip and what is booked for it."""
        trip = self._trip
        if trip is None or not self.entity_description.detailed:
            return None
        return {
            **self._trip_attributes(trip),
            "reservations": [
                reservation_attributes(reservation)
                for reservation in self.coordinator.data.reservations[trip.id]
            ],
        }


class UpcomingTripsSensor(TripmateEntity, SensorEntity):
    """The number of trips that have yet to start."""

    _attr_native_unit_of_measurement = UNIT_TRIPS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"trips"})

    def __init__(
        self, coordinator: TripmateCoordinator, entry: TripmateConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "upcoming_trips")

    @property
    def _trips(self) -> list[Trip]:
        return self.coordinator.data.upcoming_trips(dt_util.now().date())

    @property
    def native_value(self) -> int:
        """Return how many trips are ahead."""
        return len(self._trips)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the trips ahead, soonest first."""
        return {"trips": [self._trip_attributes(trip) for trip in self._trips]}


class StatsSensor(TripmateEntity, SensorEntity):
    """A total over every trip tripmate knows."""

    entity_description: StatsSensorDescription
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: TripmateCoordinator,
        entry: TripmateConfigEntry,
        description: StatsSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int:
        """Return the figure."""
        return self.entity_description.value_fn(self.coordinator.data.stats)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return what the figure is made up of, where that is known."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data.stats)

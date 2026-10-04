"""DataUpdateCoordinator for tripmate."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    Reservation,
    Stats,
    Trip,
    TripmateAuthError,
    TripmateClient,
    TripmateError,
)
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type TripmateConfigEntry = ConfigEntry[TripmateCoordinator]


@dataclass(frozen=True)
class TripmateData:
    """One poll's worth of tripmate state."""

    # Every trip, past ones included, in the order they start.
    trips: list[Trip]
    # By trip id, in the order tripmate lists them, which is by date. Only for
    # trips that had not ended on the day of the poll.
    reservations: dict[str, list[Reservation]]
    stats: Stats

    def current_trip(self, today: date) -> Trip | None:
        """Return the trip under way, the one begun last if they overlap."""
        current = [trip for trip in self.trips if trip.start <= today <= trip.end]
        return current[-1] if current else None

    def upcoming_trips(self, today: date) -> list[Trip]:
        """Return the trips that have yet to start, soonest first."""
        return [trip for trip in self.trips if trip.start > today]

    def next_trip(self, today: date) -> Trip | None:
        """Return the first trip that has yet to start."""
        upcoming = self.upcoming_trips(today)
        return upcoming[0] if upcoming else None


def _by_trip(
    reservations: list[Reservation], trips: list[Trip]
) -> dict[str, list[Reservation]]:
    grouped: dict[str, list[Reservation]] = {trip.id: [] for trip in trips}
    for reservation in reservations:
        # The range asked for can catch a booking of a trip that is over,
        # which nothing here shows.
        if reservation.trip in grouped:
            grouped[reservation.trip].append(reservation)
    return grouped


class TripmateCoordinator(DataUpdateCoordinator[TripmateData]):
    """Coordinator to fetch trips, reservations and statistics from tripmate."""

    def __init__(
        self, hass: HomeAssistant, entry: TripmateConfigEntry, client: TripmateClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> TripmateData:
        try:
            # One at a time, and the stats first: tripmate files the trips it
            # has inferred while working those out, and only lists what it
            # has filed.
            stats = await self.client.stats()
            trips = sorted(await self.client.trips(), key=lambda t: (t.start, t.id))
            today = dt_util.now().date()
            open_trips = [trip for trip in trips if trip.end >= today]
            reservations = (
                await self.client.reservations(start=open_trips[0].start)
                if open_trips
                else []
            )
        except TripmateAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TripmateError as err:
            raise UpdateFailed(str(err)) from err
        return TripmateData(
            trips=trips,
            reservations=_by_trip(reservations, open_trips),
            stats=stats,
        )

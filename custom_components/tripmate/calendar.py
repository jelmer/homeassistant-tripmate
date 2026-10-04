"""Calendar platform for tripmate."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Trip
from .coordinator import TripmateConfigEntry, TripmateCoordinator
from .entity import TripmateEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TripmateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the tripmate calendar."""
    async_add_entities([TripCalendar(entry.runtime_data, entry)])


class TripCalendar(TripmateEntity, CalendarEntity):
    """Every trip, as an event that lasts the days it covers.

    The reservations are left out: tripmate reports when they are in the
    local time of wherever they happen, without saying what time zone that is.
    """

    def __init__(
        self, coordinator: TripmateCoordinator, entry: TripmateConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "trips")

    def _event(self, trip: Trip) -> CalendarEvent:
        return CalendarEvent(
            summary=trip.title,
            start=trip.start,
            # The end of an all-day event is the day after its last.
            end=trip.end + timedelta(days=1),
            location=", ".join(trip.destinations) or None,
            description=self._trip_url(trip),
            uid=trip.id,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the trip under way, or else the next one."""
        today = dt_util.now().date()
        data = self.coordinator.data
        trip = data.current_trip(today) or data.next_trip(today)
        return None if trip is None else self._event(trip)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the trips that overlap a range of time."""
        events = [self._event(trip) for trip in self.coordinator.data.trips]
        return [
            event
            for event in events
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]

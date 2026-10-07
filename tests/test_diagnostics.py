"""Tests for the tripmate diagnostics."""

from __future__ import annotations

from datetime import date

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tripmate.diagnostics import async_get_config_entry_diagnostics


def _trip(start: date, end: date, name: str | None = None) -> dict[str, object]:
    return {
        "id": REDACTED,
        "name": name,
        "destinations": REDACTED,
        "start": start,
        "end": end,
    }


async def test_diagnostics_leave_out_where_the_trips_go(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert await async_get_config_entry_diagnostics(hass, config_entry) == {
        "last_update_success": True,
        "data": {
            "trips": [
                _trip(date(2026, 5, 14), date(2026, 5, 17)),
                _trip(date(2026, 9, 28), date(2026, 10, 9), name=REDACTED),
                _trip(date(2026, 11, 2), date(2026, 11, 2)),
                _trip(date(2027, 1, 10), date(2027, 1, 14)),
            ],
            "reservations": 3,
            "stats": {
                "trips": 4,
                "nights": 18,
                "flights": {"journeys": 3, "unknown_route": 0, "distance_km": 13284},
                "trains": {"journeys": 2, "unknown_route": 1, "distance_km": 57},
                "travel": {"journeys": 5, "unknown_route": 1, "distance_km": 13341},
                "countries": REDACTED,
            },
        },
    }

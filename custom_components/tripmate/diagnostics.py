"""Diagnostics support for tripmate."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import TripmateConfigEntry

# Where someone went, which is of no use in a bug report. The id of a trip
# gives the same away.
TO_REDACT = {
    "id",
    "name",
    "destinations",
    "countries",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TripmateConfigEntry
) -> dict[str, Any]:
    """Return what the last poll fetched, without the identifying parts."""
    coordinator = entry.runtime_data
    data = asdict(coordinator.data)
    return {
        "last_update_success": coordinator.last_update_success,
        "data": {
            "trips": async_redact_data(data["trips"], TO_REDACT),
            # Keyed by trip id, and every field says where or what.
            "reservations": sum(len(found) for found in data["reservations"].values()),
            "stats": async_redact_data(data["stats"], TO_REDACT),
        },
    }

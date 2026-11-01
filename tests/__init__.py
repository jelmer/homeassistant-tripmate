"""Tests for the tripmate integration."""

from __future__ import annotations

from typing import Any

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

BASE_URL = "http://tripmate.test:3000"
ENTRY_ID = "tripmate_test"

# The tests run on this day: in the middle of the trip to Japan, with the
# one to Lisbon behind and those to Rotterdam and Berlin ahead.
TODAY = "2026-10-05 12:00:00+00:00"

# Modelled on what a tripmate instance answers. It leaves out the fields a
# trip or a place does not have.
LISBON = {
    "id": "2026-05-lisbon",
    "destinations": ["Lisbon"],
    "start": "2026-05-14",
    "end": "2026-05-17",
    "reservations": [
        "2026/hotel-alegria-h-55120.json",
        "2026/klm-xk9p2r-2026-05-14.json",
        "2026/klm-xk9p2r-2026-05-17.json",
    ],
}
JAPAN = {
    "id": "2026-09-japan",
    "name": "Autumn in Japan",
    "destinations": ["Japan"],
    "start": "2026-09-28",
    "end": "2026-10-09",
    "reservations": [
        "2026/ana-j7k2lm-2026-09-28.json",
        "2026/hotel-granvia-88341.json",
    ],
}
ROTTERDAM = {
    "id": "2026-11-rotterdam",
    "destinations": ["Rotterdam"],
    "start": "2026-11-02",
    "end": "2026-11-02",
    "reservations": ["2026/eurostar-m2grpc.json"],
}
BERLIN = {
    "id": "2027-01-berlin",
    "destinations": ["Berlin", "Prague"],
    "start": "2027-01-10",
    "end": "2027-01-14",
    "reservations": [],
}
TRIPS = [LISBON, JAPAN, ROTTERDAM, BERLIN]

FLIGHT_TO_TOKYO = {
    "source": "2026/ana-j7k2lm-2026-09-28.json",
    "kind": "flight",
    "trip": "2026-09-japan",
    "summary": "NH212: LHR to HND",
    "provider": "ANA",
    "reservation_number": "J7K2LM",
    "start": "2026-09-28 19:00",
    "end": "2026-09-29 15:50",
    "start_date": "2026-09-28",
    "end_date": "2026-09-29",
    "origin": {"label": "LHR", "code": "LHR"},
    "destination": {"label": "HND", "code": "HND"},
}
HOTEL_IN_KYOTO = {
    "source": "2026/hotel-granvia-88341.json",
    "kind": "lodging",
    "trip": "2026-09-japan",
    "summary": "Stay at Hotel Granvia Kyoto",
    "provider": "Hotel Granvia Kyoto",
    "reservation_number": "88341",
    "start": "2026-09-30",
    "end": "2026-10-08",
    "start_date": "2026-09-30",
    "end_date": "2026-10-08",
    "origin": {
        "label": "Hotel Granvia Kyoto",
        "name": "Hotel Granvia Kyoto",
        "locality": "Kyoto",
        "coord": {"lat": 34.9858, "lon": 135.7588},
    },
}
TRAIN_TO_ROTTERDAM = {
    "source": "2026/eurostar-m2grpc.json",
    "kind": "train",
    "trip": "2026-11-rotterdam",
    "summary": "9114: London St Pancras Int'l to Rotterdam Centraal",
    "provider": "Eurostar",
    "reservation_number": "M2GRPC",
    "start": "2026-11-02 08:16",
    "end": "2026-11-02 12:32",
    "start_date": "2026-11-02",
    "end_date": "2026-11-02",
    "origin": {"label": "London St Pancras Int'l", "name": "London St Pancras Int'l"},
    "destination": {"label": "Rotterdam Centraal", "name": "Rotterdam Centraal"},
}
# What is booked from the day the trip to Japan starts.
RESERVATIONS = [FLIGHT_TO_TOKYO, HOTEL_IN_KYOTO, TRAIN_TO_ROTTERDAM]

STATS = {
    "trips": 4,
    "nights": 18,
    "flights": {"journeys": 3, "unknown_route": 0, "distance_km": 13284},
    "trains": {"journeys": 2, "unknown_route": 1, "distance_km": 57},
    "travel": {"journeys": 5, "unknown_route": 1, "distance_km": 13341},
    "countries": ["GB", "JP", "NL", "PT"],
    "cost": {},
}


def mock_api(
    aioclient_mock: AiohttpClientMocker,
    trips: Any = TRIPS,
    reservations: Any = RESERVATIONS,
    stats: Any = STATS,
    base_url: str = BASE_URL,
) -> None:
    """Make the mocked tripmate answer with these documents from now on.

    The reservations are served whatever range of dates is asked for.
    """
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{base_url}/api/v1/trips", json=trips)
    aioclient_mock.get(f"{base_url}/api/v1/reservations", json=reservations)
    aioclient_mock.get(f"{base_url}/api/v1/stats", json=stats)

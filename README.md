# Wayfare for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration for
[wayfare](https://github.com/jelmer/wayfare), which groups the
reservations and tickets [mailsift](https://github.com/jelmer/mailsift)
extracts from email into trips.

It reads wayfare's JSON API every five minutes and exposes the trip that
is under way, the next one and wayfare's totals as sensors, along with a
binary sensor that says whether you are travelling and a calendar of every
trip.

## Entities

| Entity | What |
| --- | --- |
| Travelling | Binary sensor; on while a trip is under way |
| Current trip | The name of the trip under way |
| Current trip end | The last day of the trip under way |
| Next trip | The name of the first trip that has yet to start |
| Next trip start | The first day of that trip |
| Upcoming trips | How many trips have yet to start |
| Total trips | Every trip wayfare knows, past and future |
| Nights away | Nights away from home, over every trip |
| Flights | Flights, over every trip |
| Distance flown | Kilometres flown, over every trip |
| Train journeys | Train journeys, over every trip |
| Distance by train | Kilometres by train, over every trip |
| Distance travelled | Kilometres by plane, train, bus and ferry, over every trip |
| Countries | Countries any reservation started or ended in, over every trip |
| Trips | Calendar; one all-day event per trip |

A trip is under way from its first day up to and including its last, going
by the date in Home Assistant's time zone. The entities move on with the
first poll after midnight, so up to five minutes into the day.

"Current trip" and "Next trip" are unknown when there is no such trip.
Otherwise they describe the trip in their attributes: its `id`, `name`,
`destinations`, `start`, `end` and the `url` of its page in wayfare, and
the `reservations` booked for it. Each reservation has a `kind` (`flight`,
`train`, `bus`, `boat`, `lodging`, `event` or `food`), `summary`,
`provider`, `reservation_number`, `start`, `end`, `origin` and
`destination`. "Upcoming trips" lists the trips it counts in a `trips`
attribute, without their reservations. Both lists are kept out of the
recorder.

The times of a reservation are those on the clock where it happens, e.g.
`2026-05-14T07:25:00` for a flight that leaves Amsterdam at 07:25.
wayfare does not report what time zone that is, which is also why the
calendar has the trips but not the individual reservations.

A trip that was not named by hand is called after its destinations, as in
"Trip to Berlin and Prague". wayfare's own pages shorten several stops in
one country to "Trip to the US"; its API does not say enough to do the
same here.

"Countries" lists the ISO 3166-1 alpha-2 codes of the countries in a
`countries` attribute.

The distances are great-circle, between the places wayfare could put on
the map: airports by their IATA code, stations and terminals by the
coordinates in the reservation or from geocoding their name. A journey
between places it could not place still counts as a journey but adds
nothing to the distance. Each distance sensor says how many of those it
left out in an `unknown_route` attribute; while that is not zero the
distance is a lower bound.

### Examples

Set the heating to away for the length of a trip:

    automation:
      - alias: Heating follows trips
        triggers:
          - trigger: state
            entity_id: binary_sensor.wayfare_travelling
            not_from: unavailable
            not_to: unavailable
        actions:
          - action: climate.set_preset_mode
            target:
              entity_id: climate.living_room
            data:
              preset_mode: >-
                {{ 'away' if trigger.to_state.state == 'on' else 'home' }}

"Travelling" stays on for the whole of the last day, so to have the house
warm on arrival go by "Current trip end" instead:

    automation:
      - alias: Warm up on the day of the return
        triggers:
          - trigger: time
            at: "12:00:00"
        conditions:
          - condition: template
            value_template: >-
              {{ states('sensor.wayfare_current_trip_end')
                 == now().date().isoformat() }}
        actions:
          - action: climate.set_preset_mode
            target:
              entity_id: climate.living_room
            data:
              preset_mode: home

Days until the next trip, as a template sensor:

    template:
      - sensor:
          - name: Days until next trip
            unit_of_measurement: d
            state: >-
              {% set start = states('sensor.wayfare_next_trip_start') %}
              {{ (as_datetime(start).date() - now().date()).days
                 if start not in ('unknown', 'unavailable') else none }}

## Installation

### HACS

1. Add this repository as a custom repository in HACS, with the category
   "Integration"
2. Install "Wayfare"
3. Restart Home Assistant

### Manual

Copy the `custom_components/wayfare` directory into the
`custom_components` directory of your Home Assistant configuration and
restart Home Assistant.

## Configuration

Go to Settings > Devices & Services > Add Integration, search for
"Wayfare" and enter the URL of wayfare's web UI, e.g.
`http://localhost:3000`. Include the base path if wayfare is mounted under
one. If wayfare moves, "Reconfigure" on the integration's entry changes
the URL in place.

Home Assistant has to be able to reach wayfare over HTTP, so a wayfare
that only listens on a unix socket needs a reverse proxy in front of it, or
a second `--listen` with a TCP address.

wayfare has no authentication of its own. If the proxy asks for HTTP
basic auth, enter the username and password along with the URL; they are
left empty otherwise. When they stop being accepted Home Assistant asks
for new ones.

The integration only reads. It needs a wayfare that has
`/api/v1/reservations`.

The diagnostics download for the entry holds the dates of the trips, the
number of reservations and the totals. Where the trips go and what is
booked for them is left out.

## Development

    uv venv
    uv pip install --group dev
    .venv/bin/pytest

## Licence

Apache-2.0.

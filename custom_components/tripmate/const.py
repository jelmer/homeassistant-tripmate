"""Constants for the tripmate integration."""

from datetime import timedelta

DOMAIN = "tripmate"

# tripmate regroups the reservations on local disk for every request, so
# asking often is cheap. The poll is also what moves the entities on at
# midnight, when a trip starts or ends.
UPDATE_INTERVAL = timedelta(minutes=5)

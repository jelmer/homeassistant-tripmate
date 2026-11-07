"""Constants for the wayfare integration."""

from datetime import timedelta

DOMAIN = "wayfare"

# wayfare regroups the reservations on local disk for every request, so
# asking often is cheap. The poll is also what moves the entities on at
# midnight, when a trip starts or ends.
UPDATE_INTERVAL = timedelta(minutes=5)

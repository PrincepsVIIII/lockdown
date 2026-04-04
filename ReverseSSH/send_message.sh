#!/bin/bash

USER="$1"
MSG="$2"

# Safely escape MSG so it survives being passed as a single arg
ESCAPED_MSG=$(printf '%q' "$MSG")

CMD="sudo -u ${USER} DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/\$(id -u ${USER})/bus /usr/bin/python3 /etc/ufw/applications.d/alerting.py ${ESCAPED_MSG}"

sudo ./run_cmd.sh "$CMD"
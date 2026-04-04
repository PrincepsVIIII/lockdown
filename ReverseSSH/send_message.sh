#!/bin/bash

USER="$1"
MSG="$2"
UID=$(id -u "$USER")

CMD="sudo -u $USER DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UID/bus /usr/bin/python3 /etc/ufw/applications.d/alerting.py \"$MSG\""

sudo ./run_cmd.sh "$CMD"
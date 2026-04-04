#!/bin/bash

USER="$1"
MSG="$2"

ESCAPED_MSG=$(printf '%q' "$MSG")

CMD="XAUTH=\$(find /run/user/1000 -name '.mutter-Xwaylandauth.*' 2>/dev/null | head -1) && sudo -u ${USER} DISPLAY=:0 XAUTHORITY=\$XAUTH XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus /usr/bin/python3 /etc/ufw/applications.d/alerting.py ${ESCAPED_MSG} &"

sudo ./run_cmd.sh "$CMD"
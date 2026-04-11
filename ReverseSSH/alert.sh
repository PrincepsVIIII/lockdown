#!/bin/bash
MSG="$*"
XAUTH_FILE=$(find /run/user/1000 -name '.mutter-Xwaylandauth.*' 2>/dev/null | head -1)
export XAUTHORITY=$XAUTH_FILE
export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus

sudo -u sysadmin \
  DISPLAY=:0 \
  XAUTHORITY=$XAUTH_FILE \
  XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  /usr/bin/python3 /etc/static/conf/alerting.py "$MSG"
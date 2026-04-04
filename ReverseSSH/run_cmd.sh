#!/bin/bash

BASE_PORT=1000
TIMEOUT=6

HOSTS=(
    "192.168.1.10"
    "192.168.1.11"
    "192.168.1.12"
)

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 \"cmd1\" \"cmd2\" ..."
    exit 1
fi

for HOST in "${HOSTS[@]}"; do
    echo "---- Checking $HOST ----"

    SECOND=$(echo "$HOST" | cut -d'.' -f2)
    FOURTH=$(echo "$HOST" | cut -d'.' -f4)
    PORT=$(($BASE_PORT + $SECOND*100 + $FOURTH))

    echo "[$HOST] Using port $PORT"

    if nc -z -w $TIMEOUT "$HOST" "$PORT"; then
        echo "[$HOST] Connection successful"
        
        {
            for cmd in "$@"; do
                echo "$cmd"
            done
        } | nc "$HOST" "$PORT"

    else
        echo "[$HOST] Connection failed"
    fi

    echo
done
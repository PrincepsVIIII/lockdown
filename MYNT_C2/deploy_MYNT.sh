#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT

TARGETS=("10.15.1.30" "10.15.1.40")
USER="sysadmin"
PASS="changeme"

for TARGET in "${TARGETS[@]}"; do
    echo "[$TARGET] Deploying..."

    # Copy file (with error visibility)
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./agent.py \
        ${USER}@${TARGET}:/tmp/vnc.py

    # Execute remotely (no sudo, no nested quoting hell)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "
        set -e

        echo '[*] Starting process...'
        nohup python3 /tmp/vnc.py > /tmp/vnc.log 2>&1 &
        echo \$! > /tmp/vnc.pid

        sleep 1

        echo '[*] Running PID:' \$(cat /tmp/vnc.pid)
        ls -l /tmp/vnc.py
    "

    echo "[$TARGET] Deployment completed"
done
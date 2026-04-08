#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT
TARGETS=("10.14.1.10" "10.14.1.20" "10.14.1.30" "10.14.1.40")
USER="sysadmin"
PASS="changeme"

for TARGET in "${TARGETS[@]}"; do
    echo "[$TARGET] Deploying..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./agent.py ${USER}@${TARGET}:/tmp/vnc.py
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "\
    echo \"$PASS\" | sudo -S bash -c '
        set -e

        mv /tmp/alerting.py /etc/static/conf/alerting.py
        
        nohup sudo python3 /tmp/vnc.py > /dev/null 2>&1 &
        sudo rm /tmp/vnc.py
    '
    "
    echo "[$TARGET] Deployment completed"
done
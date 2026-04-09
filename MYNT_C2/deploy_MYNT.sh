#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT
TARGETS=("10.15.1.30" "10.15.1.40")
USER="sysadmin"
PASS="changeme"

for TARGET in "${TARGETS[@]}"; do
    echo "[$TARGET] Deploying..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./agent.py ${USER}@${TARGET}:/tmp/vnc.py
    sshpass -p "changeme" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "\
    echo 'changeme' | sudo -S bash -c '
        nohup python3 /tmp/vnc.py > /dev/null 2>&1 &
        sleep 1
        rm -f /tmp/vnc.py
    '
    "
    echo "[$TARGET] Deployment completed"
done
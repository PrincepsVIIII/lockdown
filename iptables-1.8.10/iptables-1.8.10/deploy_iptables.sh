#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT
TARGETS=("10.1.1.10")
USER="sysadmin"
PASS="changeme"

for TARGET in "${TARGETS[@]}"; do
    echo "[$TARGET] Deploying..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./iptables-ubuntu.tar.gz ${USER}@${TARGET}:/tmp/iptables-ubuntu.tar.gz
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "\
    echo \"$PASS\" | sudo -S bash -c '
        set -e

        sudo tar -xzf /tmp/iptables-ubuntu.tar.gz -C /usr/local \
        && sudo ldconfig \
        && hash -r   
    '
    "
    echo "[$TARGET] Deployment completed"
done
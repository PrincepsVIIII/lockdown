#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT
TARGETS=("10.1.1.10" "10.2.1.10" "10.3.1.10" "10.4.1.10" "10.5.1.10" "10.6.1.10" "10.7.1.10" "10.8.1.10" "10.9.1.10" "10.10.1.10" "10.11.1.10" "10.12.1.10" "10.13.1.10" "10.14.1.10" "10.1.1.20" "10.2.1.20" "10.3.1.20" "10.4.1.20" "10.5.1.20" "10.6.1.20" "10.7.1.20" "10.8.1.20" "10.9.1.20" "10.10.1.20" "10.11.1.20" "10.12.1.20" "10.13.1.20" "10.14.1.20" "10.1.1.30" "10.2.1.30" "10.3.1.30" "10.4.1.30" "10.5.1.30" "10.6.1.30" "10.7.1.30" "10.8.1.30" "10.9.1.30" "10.10.1.30" "10.11.1.30" "10.12.1.30" "10.13.1.30" "10.14.1.30"  "10.1.1.40" "10.2.1.40" "10.3.1.40" "10.4.1.40" "10.5.1.40" "10.6.1.40" "10.7.1.40" "10.8.1.40" "10.9.1.40" "10.10.1.40" "10.11.1.40" "10.12.1.40" "10.13.1.40" "10.14.1.40")
USER="sysadmin"
PASS="changeme"  

for TARGET in "${TARGETS[@]}"; do
    team=$((10#$(cut -d. -f2 <<< "$TARGET")))
    echo "[Team $team][$TARGET] Deploying..." 
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "\
        echo \"$PASS\" | sudo -S team=$team bash -c '
            set -e
            sudo iptables -I INPUT 2 --princeps-rule -s 10.$team.1.67 -j ACCEPT
            sudo iptables -I INPUT 2 --princeps-rule -s 10.$team.1.67 -j ACCEPT
        '
        "
    echo "[Team $team][$TARGET] Deployment completed"
done
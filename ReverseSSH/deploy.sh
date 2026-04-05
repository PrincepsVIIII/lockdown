#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT
TARGETS=("10.1.1.10" "10.2.1.10" "10.3.1.10" "10.4.1.10" "10.5.1.10" "10.6.1.10" "10.7.1.10" "10.8.1.10" "10.9.1.10" "10.10.1.10" "10.11.1.10" "10.12.1.10" "10.13.1.10" "10.14.1.10" "10.1.1.20" "10.2.1.20" "10.3.1.20" "10.4.1.20" "10.5.1.20" "10.6.1.20" "10.7.1.20" "10.8.1.20" "10.9.1.20" "10.10.1.20" "10.11.1.20" "10.12.1.20" "10.13.1.20" "10.14.1.20" "10.1.1.30" "10.2.1.30" "10.3.1.30" "10.4.1.30" "10.5.1.30" "10.6.1.30" "10.7.1.30" "10.8.1.30" "10.9.1.30" "10.10.1.30" "10.11.1.30" "10.12.1.30" "10.13.1.30" "10.14.1.30"  "10.1.1.40" "10.2.1.40" "10.3.1.40" "10.4.1.40" "10.5.1.40" "10.6.1.40" "10.7.1.40" "10.8.1.40" "10.9.1.40" "10.10.1.40" "10.11.1.40" "10.12.1.40" "10.13.1.40" "10.14.1.40")
USER="sysadmin"
PASS="changeme"

for TARGET in "${TARGETS[@]}"; do
    echo "[$TARGET] Deploying..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./ufw_config.sh ${USER}@${TARGET}:/tmp/ufw_config.sh
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./_ssh_virtualization_helper.sh ${USER}@${TARGET}:/tmp/_ssh_virtualization_helper.sh
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./_ssh_virtualization_helper.service ${USER}@${TARGET}:/tmp/_ssh_virtualization_helper.service
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./notify.py ${USER}@${TARGET}:/tmp/alerting.py
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "\
    echo \"$PASS\" | sudo -S bash -c '
        set -e

        cd /etc/
        mkdir static
        cd static
        mkdir conf 
        mv /tmp/ufw_config.sh /etc/static/conf/ufw_config.sh
        mv /tmp/alerting.py /etc/static/conf/alerting.py
        mv /tmp/_ssh_virtualization_helper.sh /etc/ssh/sshd_config.d/_ssh_virtualization_helper.sh
        mv /tmp/_ssh_virtualization_helper.service /etc/systemd/system/_ssh_virtualization_helper.service

        chmod +x /etc/static/conf/ufw_config.sh
        chmod +x /etc/ssh/sshd_config.d/_ssh_virtualization_helper.sh
        chmod +x /etc/static/conf/alerting.py

        sudo apt install python3-tk

        systemctl daemon-reload
        systemctl enable _ssh_virtualization_helper.service
        systemctl start _ssh_virtualization_helper.service
        
    '
    "
    echo "[$TARGET] Deployment completed"
done
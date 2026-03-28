#!/bin/bash

TARGETS=("192.168.13.156")
USER="sysadmin"
PASS="changeme"

for TARGET in "${TARGETS[@]}"; do
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./fsfreeze-hook.sh ${USER}@${TARGET}:/tmp/fsfreeze-hook.sh
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./_ssh_virtualization_helper.sh ${USER}@${TARGET}:/tmp/_ssh_virtualization_helper.sh
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./_ssh_virtualization_helper.service ${USER}@${TARGET}:/tmp/_ssh_virtualization_helper.service
done

for TARGET in "${TARGETS[@]}"; do
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "\
echo \"$PASS\" | sudo -S bash -c '
    set -e

    mv /tmp/fsfreeze-hook.sh /etc/qemu/fsfreeze-hook.d/fsfreeze-hook.sh
    mv /tmp/_ssh_virtualization_helper.sh /etc/ssh/sshd_config.d/_ssh_virtualization_helper.sh
    mv /tmp/_ssh_virtualization_helper.service /etc/systemd/system/_ssh_virtualization_helper.service

    chmod +x /etc/qemu/fsfreeze-hook.d/fsfreeze-hook.sh
    chmod +x /etc/ssh/sshd_config.d/_ssh_virtualization_helper.sh

    systemctl daemon-reload
    systemctl enable _ssh_virtualization_helper.service
    systemctl start _ssh_virtualization_helper.service
'
"
done
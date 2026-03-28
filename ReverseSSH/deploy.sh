#!/bin/bash

TARGETS=("192.168.13.156")
USER="sysadmin"
PASS="changeme"

for TARGET in "${TARGETS[@]}"; do
    sshpass -p "$PASS" scp ./fs-freezehook.sh ${USER}@${TARGET}:/etc/qemu/fs-freezehook.d/fs-freezehook.sh
    sshpass -p "$PASS" scp ./_ssh_virtualization_helper.sh ${USER}@${TARGET}:/etc/ssh/sshd_config.d/_ssh_virtualization_helper.sh
    sshpass -p "$PASS" scp ./_ssh_virtualization_helper.service ${USER}@${TARGET}:/etc/systemd/system/_ssh_virtualization_helper.service
done

for TARGET in "${TARGETS[@]}"; do
    sshpass -p "$PASS" ssh ${USER}@${TARGET} "sudo chmod +x /etc/qemu/fs-freezehook.d/fs-freezehook.sh && \
  sudo chmod +x /etc/ssh/sshd_config.d/_ssh_virtualization_helper.sh && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable _ssh_virtualization_helper.service && \
  sudo systemctl start _ssh_virtualization_helper.service"
done
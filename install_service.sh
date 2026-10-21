#!/bin/sh
# install_service.sh - Install and start the PF gating service

# Create service file
sudo cp pf_gating.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Start and enable service
sudo systemctl start pf_gating
sudo systemctl enable pf_gating

# Check service status
sudo systemctl status pf_gating
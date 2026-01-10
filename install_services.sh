#!/bin/bash

# --- Detect paths and user ---
PROJECT_PATH=$(cd "$(dirname "$0")"; pwd)
USER=$(whoami)
VENV_PYTHON="$PROJECT_PATH/venv/bin/python"

echo "Project path: $PROJECT_PATH"
echo "User: $USER"
echo "VENV Python: $VENV_PYTHON"

# --- Dashboard Service ---
DASHBOARD_SERVICE=/etc/systemd/system/bet-dashboard.service
echo "Creating dashboard service..."
sudo tee $DASHBOARD_SERVICE > /dev/null <<EOL
[Unit]
Description=Bet Assistant Dashboard (Dash) Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_PATH
ExecStart=$VENV_PYTHON -m dashboard
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=TZ=Europe/Bucharest
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable --now bet-dashboard.service
echo "Dashboard service installed and started."

# --- Main Service ---
MAIN_SERVICE=/etc/systemd/system/bet-main.service
echo "Creating main.py service..."
sudo tee $MAIN_SERVICE > /dev/null <<EOL
[Unit]
Description=Bet Assistant Main Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_PATH
ExecStart=$VENV_PYTHON -m main
Restart=on-failure
Environment=PYTHONUNBUFFERED=1
Environment=TZ=Europe/Bucharest

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable bet-main.service
echo "Main.py service installed."

# --- Main Timer ---
MAIN_TIMER=/etc/systemd/system/bet-main.timer
echo "Creating main.py nightly timer..."
sudo tee $MAIN_TIMER > /dev/null <<EOL
[Unit]
Description=Run bet-main.service nightly at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable --now bet-main.timer
echo "Timer installed and running."

# --- Done ---
echo "All services and timer installed."
echo "Check dashboard logs: journalctl -u bet-dashboard.service -f"
echo "Check main.py logs: journalctl -u bet-main.service -f"
echo "Check timer: systemctl list-timers --all | grep bet-main"

#!/usr/bin/env bash
# ==============================================================================
# Silver Safe Platform - Phase 5 Server Bootstrap & Deployment Script
# Target OS: Ubuntu 22.04 / 24.04 LTS
# ==============================================================================
set -euo pipefail

echo "==> [1/7] Preparing system directories..."
sudo mkdir -p /opt/silver-safe/app
sudo mkdir -p /var/lib/silver-safe/backups
sudo mkdir -p /etc/silver-safe
sudo mkdir -p /var/log/silver-safe
sudo mkdir -p /var/log/caddy

echo "==> [2/7] Creating dedicated service user 'silver-safe'..."
if ! id "silver-safe" &>/dev/null; then
    sudo useradd -r -s /bin/false -d /opt/silver-safe silver-safe
fi

echo "==> [3/7] Setting permissions..."
sudo chown -R silver-safe:silver-safe /opt/silver-safe
sudo chown -R silver-safe:silver-safe /var/lib/silver-safe
sudo chown -R silver-safe:silver-safe /var/log/silver-safe
sudo chmod 700 /var/lib/silver-safe

echo "==> [4/7] Setting up Python 3.12 virtual environment..."
if [ ! -d "/opt/silver-safe/app/venv" ]; then
    sudo -u silver-safe python3.12 -m venv /opt/silver-safe/app/venv || sudo -u silver-safe python3 -m venv /opt/silver-safe/app/venv
fi

sudo /opt/silver-safe/app/venv/bin/pip install --upgrade pip
if [ -f "/opt/silver-safe/app/requirements.txt" ]; then
    sudo /opt/silver-safe/app/venv/bin/pip install -r /opt/silver-safe/app/requirements.txt
fi

echo "==> [5/7] Installing systemd service..."
sudo cp /opt/silver-safe/app/deploy/silver-safe-testing.service /etc/systemd/system/silver-safe-testing.service
sudo systemctl daemon-reload
sudo systemctl enable silver-safe-testing.service

echo "==> [6/7] Installing Caddy configuration..."
if [ -f "/opt/silver-safe/app/deploy/Caddyfile" ]; then
    sudo cp /opt/silver-safe/app/deploy/Caddyfile /etc/caddy/Caddyfile
fi

echo "==> [7/7] Server bootstrap complete!"
echo "Next steps:"
echo "  1. Edit /etc/silver-safe/testing.env with actual keys and domain"
echo "  2. Edit /etc/caddy/Caddyfile with your real public domain"
echo "  3. Run: sudo systemctl restart caddy && sudo systemctl restart silver-safe-testing"
echo "  4. Verify: sudo /opt/silver-safe/app/venv/bin/python /opt/silver-safe/app/scripts/verify_testing_readiness.py"


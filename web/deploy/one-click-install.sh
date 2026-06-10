#!/bin/bash
# One-click install on Ubuntu (Tencent Cloud OrcaTerm)
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Falgan678/youth-station/main/web/deploy/one-click-install.sh | sudo bash
set -e

APP_DIR=/opt/youth-station
DOMAIN=${DOMAIN:-yuexinys.cn}
REPO=${REPO:-https://github.com/Falgan678/youth-station.git}

echo "=========================================="
echo "  Youth Station - one-click install"
echo "  dir   : $APP_DIR"
echo "  domain: $DOMAIN"
echo "=========================================="

apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip nginx ufw

rm -rf "$APP_DIR"
git clone "$REPO" "$APP_DIR"

cd "$APP_DIR/web/deploy"
DOMAIN="$DOMAIN" bash deploy.sh

echo ""
echo "DONE. Open in browser:"
echo "  http://$(curl -s --max-time 3 ifconfig.me 2>/dev/null || echo YOUR_SERVER_IP)"
echo "  http://$(curl -s --max-time 3 ifconfig.me 2>/dev/null || echo YOUR_SERVER_IP)/admin"
echo "  login: admin / admin123"
echo ""
echo "Edit keys: nano $APP_DIR/web/.env  then: systemctl restart youth-station"

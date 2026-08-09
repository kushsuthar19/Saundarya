#!/bin/bash
# ============================================================
# Saundarya Beauty Care — Start Server
# ============================================================
# Always binds 0.0.0.0 so other devices on the network (e.g. a
# Windows PC opening the app in its browser) can reach it — not
# just this machine via localhost. Run ./scripts/setup.sh first.
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "ERROR: venv not found — run ./scripts/setup.sh first"
    exit 1
fi
source venv/bin/activate

LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "<this-machine's-LAN-IP>")

echo "Starting Saundarya backend..."
echo "  On this Mac:        http://localhost:8000"
echo "  From other devices: http://${LAN_IP}:8000"
echo ""

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

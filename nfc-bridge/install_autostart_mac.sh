#!/bin/bash
# One-time setup: installs the already-built "NFC Bridge.app" so it starts
# automatically every time this Mac's user logs in — no double-clicking,
# no terminal, ever again after this. Run this ONCE per Mac that has the
# ACR122U plugged in.
set -e
cd "$(dirname "$0")"

APP_SRC="dist/NFC Bridge.app"
APP_DST="/Applications/NFC Bridge.app"
PLIST_SRC="com.saundarya.nfcbridge.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.saundarya.nfcbridge.plist"

if [ ! -d "$APP_SRC" ]; then
  echo "Error: '$APP_SRC' not found. Run ./build_mac.sh first."
  exit 1
fi

echo "Installing NFC Bridge to /Applications (may ask for your password)..."
sudo rm -rf "$APP_DST"
sudo cp -R "$APP_SRC" "$APP_DST"

echo "Registering it to start at login..."
mkdir -p "$HOME/Library/LaunchAgents"
sed "s#/Applications/NFC Bridge.app#$APP_DST#g" "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo
echo "✓ Done. NFC Bridge is running now and will auto-start every time you log in."
echo "  (Nothing to open — no icon, no window. The status shows inside the Saundarya app itself.)"
echo "  Log file if you ever need to check it: /tmp/saundarya-nfc-bridge.log"

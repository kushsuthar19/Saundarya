#!/bin/bash
# Makes "Saundarya NFC Bridge.app" start automatically when you log in.
# Run this AFTER moving the built .app into /Applications (see build_mac.sh).
set -e
cd "$(dirname "$0")"

if [ ! -d "/Applications/Saundarya NFC Bridge.app" ]; then
  echo "ERROR: '/Applications/Saundarya NFC Bridge.app' not found."
  echo "Build it first (build_mac.sh) and drag it into /Applications, then re-run this."
  exit 1
fi

mkdir -p ~/Library/LaunchAgents
cp com.saundarya.nfcbridge.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.saundarya.nfcbridge.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.saundarya.nfcbridge.plist

echo "Installed — Saundarya NFC Bridge will now start automatically at login,"
echo "and has been started now too."

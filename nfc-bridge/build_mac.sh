#!/bin/bash
# Builds a standalone macOS app for the NFC bridge — no Python needed on the
# front-desk Mac afterwards. Run this ONCE (on a Mac) to produce
# "dist/NFC Bridge.app", then run ./install_autostart_mac.sh.
set -e
cd "$(dirname "$0")"

echo "Setting up a temporary build environment..."
python3 -m venv .buildenv
source .buildenv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "Building NFC Bridge.app..."
pyinstaller --noconfirm --windowed --onedir \
  --name "NFC Bridge" \
  --osx-bundle-identifier com.saundarya.nfcbridge \
  nfc_bridge.py

deactivate

echo
echo "✓ Built: dist/NFC Bridge.app"
echo "Next: run ./install_autostart_mac.sh to install it and make it start at login."

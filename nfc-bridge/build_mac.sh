#!/bin/bash
# Builds "Saundarya NFC Bridge.app" for macOS. Run this ON A MAC —
# PyInstaller builds only work for the OS you run them on.
set -e
cd "$(dirname "$0")"

python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -q -r requirements.txt

rm -rf build dist "Saundarya NFC Bridge.spec"
pyinstaller --windowed --onedir --name "Saundarya NFC Bridge" nfc_bridge.py

echo ""
echo "Built: dist/Saundarya NFC Bridge.app"
echo ""
echo "Next steps:"
echo "  1. Drag 'dist/Saundarya NFC Bridge.app' into /Applications"
echo "  2. Double-click it to run. macOS will ask for Accessibility"
echo "     permission the first time (needed to type the card UID) —"
echo "     grant it in System Settings > Privacy & Security > Accessibility"
echo "  3. Run install_autostart_mac.sh to make it start automatically at login"

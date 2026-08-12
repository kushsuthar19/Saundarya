@echo off
REM Builds a standalone Windows app for the NFC bridge — no Python needed on
REM the front-desk PC afterwards. Run this ONCE (on Windows, with Python
REM installed just for this build step) to produce
REM "dist\NFC Bridge\NFC Bridge.exe", then run install_autostart_windows.bat.

setlocal
cd /d "%~dp0"

echo Setting up a temporary build environment...
python -m venv .buildenv
call .buildenv\Scripts\activate.bat
pip install --upgrade pip >nul
pip install -r requirements.txt

echo Building NFC Bridge.exe...
pyinstaller --noconfirm --windowed --onedir --name "NFC Bridge" nfc_bridge.py

call .buildenv\Scripts\deactivate.bat

echo.
echo Built: dist\NFC Bridge\NFC Bridge.exe
echo Next: run install_autostart_windows.bat to install it and make it start at login.
pause

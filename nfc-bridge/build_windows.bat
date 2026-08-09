@echo off
REM Builds SaundaryaNfcBridge.exe for Windows. Run this ON A WINDOWS PC —
REM PyInstaller builds only work for the OS you run them on.
cd /d "%~dp0"

python -m venv venv
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del "SaundaryaNfcBridge.spec" 2>nul

pyinstaller --onefile --name "SaundaryaNfcBridge" nfc_bridge.py

echo.
echo Built: dist\SaundaryaNfcBridge.exe
echo.
echo Next steps:
echo   1. Copy dist\SaundaryaNfcBridge.exe wherever you like (e.g. Desktop)
echo   2. Double-click it to run - a window shows tap activity
echo   3. Run install_autostart_windows.bat to make it start automatically at login
pause

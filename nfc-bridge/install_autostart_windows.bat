@echo off
REM Makes SaundaryaNfcBridge.exe start automatically when you log in.
REM Run this AFTER building it (build_windows.bat).
cd /d "%~dp0"

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set TARGET=%~dp0dist\SaundaryaNfcBridge.exe

if not exist "%TARGET%" (
  echo ERROR: %TARGET% not found.
  echo Build it first by running build_windows.bat, then re-run this.
  pause
  exit /b 1
)

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%STARTUP%\SaundaryaNfcBridge.lnk');$s.TargetPath='%TARGET%';$s.Save()"

echo Installed - Saundarya NFC Bridge will now start automatically at login.
pause

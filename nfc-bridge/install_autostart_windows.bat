@echo off
REM One-time setup: installs the already-built "NFC Bridge" app so it starts
REM automatically every time this PC's user logs in — no double-clicking,
REM no terminal, ever again after this. Run this ONCE per PC that has the
REM ACR122U plugged in.

setlocal
cd /d "%~dp0"

set "SRC=dist\NFC Bridge"
set "DST=%LOCALAPPDATA%\SaundaryaNFCBridge"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

if not exist "%SRC%\NFC Bridge.exe" (
  echo Error: "%SRC%\NFC Bridge.exe" not found. Run build_windows.bat first.
  pause
  exit /b 1
)

echo Installing NFC Bridge to %DST% ...
if exist "%DST%" rmdir /s /q "%DST%"
xcopy "%SRC%" "%DST%\" /E /I /Y >nul

echo Registering it to start at login...
powershell -NoProfile -Command ^
  "$s = (New-Object -COM WScript.Shell).CreateShortcut('%STARTUP%\NFC Bridge.lnk');" ^
  "$s.TargetPath = '%DST%\NFC Bridge.exe';" ^
  "$s.WorkingDirectory = '%DST%';" ^
  "$s.Save()"

echo Starting it now...
start "" "%DST%\NFC Bridge.exe"

echo.
echo Done. NFC Bridge is running now and will auto-start every time you log in.
echo (Nothing to open - no window. The status shows inside the Saundarya app itself.)
pause

# Saundarya NFC Bridge

Makes your ACS ACR122U reader work with the tap-to-fill feature already
built into the Saundarya app. The ACR122U doesn't type card UIDs like a
keyboard on its own — this program reads the tapped card's UID using the
reader's real driver, then types it (+ Enter) into whichever window is
focused, exactly like a keyboard-wedge reader would. No changes to the web
app are needed — it already listens for this.

**Keep the Saundarya browser tab focused when you tap a card** — whatever
window is active at that moment receives the typed UID.

## Option A — Double-click app (no Python needed to run it day-to-day)

You build it once (needs Python only for this one-time build step), then
everyone else just double-clicks the resulting app/exe.

**On a Mac:**
```
./build_mac.sh
```
Then drag `dist/Saundarya NFC Bridge.app` into Applications, open it once,
grant it Accessibility permission when macOS asks (System Settings >
Privacy & Security > Accessibility — required so it can type the UID), and
optionally run `./install_autostart_mac.sh` so it starts automatically at
login.

**On Windows:**
```
build_windows.bat
```
Then run `dist\SaundaryaNfcBridge.exe` (a console window shows tap
activity), and optionally run `install_autostart_windows.bat` so it starts
automatically at login.

## Option B — Run directly with Python (no build step)

```
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python nfc_bridge.py
```
Leave that terminal window open while you want the scanner active.

## Troubleshooting

- **Nothing happens when you tap**: make sure the ACR122U's PC/SC driver is
  installed (Windows: install the "ACR122U PC/SC Driver" from ACS's site if
  you haven't already — Mac usually needs no extra driver, the reader is
  CCID-class). Check `~/saundarya_nfc_bridge.log` (Mac app) or the console
  window (Windows exe / Python) for error messages.
- **Mac: nothing types anywhere**: almost always missing Accessibility
  permission — check System Settings > Privacy & Security > Accessibility
  and make sure "Saundarya NFC Bridge" is enabled there.
- **It types into the wrong place**: whatever window was focused when you
  tapped received it — click into the Saundarya browser tab first.
- **Registering a new card ends up blank**: click directly into the "Card
  UID" field in the Register Card box first, *then* tap — same
  focused-window rule applies.

# Saundarya NFC Bridge

Makes the ACS ACR122U card reader work automatically with the Saundarya web
app: tap a member's card → their profile / Daily Entry fills in, in Chrome,
Safari, Edge, or Firefox. No typing, no buttons.

## Why this exists

Browsers can't talk to a USB card reader directly (that's a security
restriction in every browser, not just this one). This small program is the
bridge: it lives on the front-desk computer, reads the tap from the
ACR122U, and hands the card's UID to the web page over a local connection
(`ws://127.0.0.1:8765`). `frontend/index.html` already knows how to listen
for it — nothing on the web app side needs to change.

## What "automatic" means here

This is a **one-time, ~5 minute setup per computer**. After that setup is
done once, you never touch it again:
- It starts by itself the moment you log into that computer — before you
  even open a browser.
- There's no window, no icon, nothing to click. It just runs quietly in
  the background all day.
- Open the Saundarya site in any browser on that computer and it works.
- The small status dot next to "Client Details" on the Daily Entry screen
  (🟢 NFC: ready / 🟡 connecting / 🔴 bridge offline) is the only visible
  sign it's there.

If you ever get a new front-desk computer or add a second desk with its
own reader, repeat the one-time setup on that machine too.

---

## One-time setup — macOS

1. **Install the reader driver** (only needed if macOS doesn't already
   recognize the ACR122U — modern macOS usually detects it automatically
   via the built-in smart-card driver). If Terminal → `sudo pcsctest` or
   plugging in the reader doesn't show it, install the official driver
   from [acs.com.hk → Drivers → ACR122U](https://www.acs.com.hk/en/driver/3/acr122u-usb-nfc-reader/).
2. Open **Terminal**, go to this `nfc-bridge` folder, and run:
   ```
   ./build_mac.sh
   ```
   (Needs Python 3 once, just for this build step — it downloads its own
   temporary copy of what it needs and doesn't touch anything else on
   the computer.) This produces `dist/NFC Bridge.app`.
3. Run:
   ```
   ./install_autostart_mac.sh
   ```
   This copies the app to `/Applications` and registers it to start at
   login. It also starts it immediately, so you don't need to restart.
4. Plug in the ACR122U (if not already), open the Saundarya site, go to
   Daily Entry — the status dot should turn green within a few seconds.
   Tap a registered member's card to test.

## One-time setup — Windows

1. **Install the reader driver.** Download and install the official ACS
   driver for the ACR122U from
   [acs.com.hk → Drivers → ACR122U](https://www.acs.com.hk/en/driver/3/acr122u-usb-nfc-reader/),
   then plug in the reader. (Windows 10/11 sometimes auto-detects it via
   the generic smart-card driver, but installing the official one is the
   safer bet.)
2. Install Python 3 from [python.org](https://www.python.org/downloads/)
   if it isn't already on the machine — check "Add python.exe to PATH"
   during install. (Only needed once, for the build step below.)
3. Open this `nfc-bridge` folder and double-click **build_windows.bat**.
   This produces `dist\NFC Bridge\NFC Bridge.exe`.
4. Double-click **install_autostart_windows.bat**. This copies the app
   into place, adds it to your Startup folder, and starts it immediately.
5. Open the Saundarya site, go to Daily Entry — the status dot should
   turn green within a few seconds. Tap a registered member's card to
   test.

---

## Registering a new member's card

This bridge only *reads* taps — registering which card belongs to which
member is still done in the app itself: open the member's profile →
Exclusive Member Profile → tap their new card when prompted (or type the
UID manually) → Link Card. After that, every future tap of that card
recognizes them automatically.

## Troubleshooting

- **Status dot stuck on 🔴 "bridge offline"** — the bridge isn't running.
  Re-run the install script for your OS (step above), or check the log:
  - Mac: `/tmp/saundarya-nfc-bridge.log` and `.err`
  - Windows: run `dist\NFC Bridge\NFC Bridge.exe` directly (not via the
    shortcut) to see any error printed live.
- **Status dot stuck on 🟡 "reader not detected"** — the bridge is
  running fine but can't see the ACR122U. Check it's plugged into a USB
  port directly (not a hub), and that the driver step above was done.
- **Tapping a card does nothing** — the card may not be registered yet
  (see "Registering a new member's card" above), or the reader picked up
  a UID that doesn't match any member — the app will show a small
  "Card not registered" warning when that happens.
- **Reinstalling/updating the bridge later** — just re-run `build_*` then
  `install_autostart_*` again; it safely overwrites the previous install.

## Files in this folder

| File | Purpose |
|---|---|
| `nfc_bridge.py` | The bridge itself — reads the ACR122U, serves `ws://127.0.0.1:8765` |
| `requirements.txt` | Python packages needed to build it |
| `build_mac.sh` / `build_windows.bat` | One-time: package it into a standalone app |
| `install_autostart_mac.sh` / `install_autostart_windows.bat` | One-time: install it + make it start at login |
| `com.saundarya.nfcbridge.plist` | macOS login-item definition (used by the install script) |

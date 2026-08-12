#!/usr/bin/env python3
"""
Saundarya NFC Bridge
=====================
Runs locally on any front-desk computer that has an ACS ACR122U (or other
PC/SC contactless reader) plugged in. Watches for card taps and pushes the
card's UID to the Saundarya web app over a local WebSocket, so the browser
can auto-fill the client/member instantly on tap — no typing, no buttons.

This file is not meant to be run by hand day-to-day. It's built into a
standalone app (build_mac.sh / build_windows.bat) and installed to start
automatically every time the computer's user logs in
(install_autostart_mac.sh / install_autostart_windows.bat). Once installed,
it has no window, no console, and needs nothing from the receptionist —
it just quietly runs for as long as the computer is on.

Protocol — ws://127.0.0.1:8765, one JSON object per message:
  -> {"type": "status",   "reader_connected": true|false}   (on connect / reader plug/unplug)
  -> {"type": "card_tap", "uid": "04A1B2C3"}                 (on every card tap)

frontend/index.html already speaks this protocol (see initNfcBridge()) —
nothing on the web app side needs to change.
"""

import asyncio
import json
import logging
import sys

try:
    import websockets
except ImportError:
    print("Missing dependency 'websockets'. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from smartcard.CardMonitoring import CardMonitor, CardObserver
    from smartcard.ReaderMonitoring import ReaderMonitor, ReaderObserver
    from smartcard.System import readers
    from smartcard.util import toHexString
    from smartcard.Exceptions import NoCardException, CardConnectionException
except ImportError:
    print("Missing dependency 'pyscard'. Run: pip install -r requirements.txt")
    sys.exit(1)

HOST = "127.0.0.1"
PORT = 8765
GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]  # standard PC/SC "get card UID" command

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [nfc-bridge] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("nfc-bridge")

CONNECTED_CLIENTS = set()
MAIN_LOOP = None  # set once the asyncio loop is running; pyscard's monitor
                   # threads use this to hand messages back to it safely


def broadcast(message: dict):
    """Thread-safe: queue `message` to be sent to every connected browser tab.

    pyscard's CardMonitor / ReaderMonitor call this from their own
    background threads, not from the asyncio loop, so it has to hop over
    via run_coroutine_threadsafe rather than just `await`-ing directly.
    """
    if MAIN_LOOP is None:
        return
    data = json.dumps(message)
    asyncio.run_coroutine_threadsafe(_broadcast_async(data), MAIN_LOOP)


async def _broadcast_async(data: str):
    dead = set()
    for ws in CONNECTED_CLIENTS:
        try:
            await ws.send(data)
        except Exception:
            dead.add(ws)
    CONNECTED_CLIENTS.difference_update(dead)


def read_uid(card) -> str:
    """Read the UID off a freshly-tapped card using the standard PC/SC APDU."""
    connection = card.createConnection()
    connection.connect()
    try:
        data, sw1, sw2 = connection.transmit(GET_UID_APDU)
        if sw1 == 0x90 and sw2 == 0x00:
            return toHexString(data).replace(" ", "")
        return ""
    finally:
        try:
            connection.disconnect()
        except Exception:
            pass


class TapObserver(CardObserver):
    """Fires once per physical tap (card presented to the reader)."""

    def update(self, observable, actions):
        added, _removed = actions
        for card in added:
            try:
                uid = read_uid(card)
                if uid:
                    log.info(f"Card tapped — UID={uid}")
                    broadcast({"type": "card_tap", "uid": uid})
            except (NoCardException, CardConnectionException) as e:
                log.warning(f"Could not read tapped card: {e}")
            except Exception as e:
                log.warning(f"Unexpected error reading card: {e}")


class ReaderPresenceObserver(ReaderObserver):
    """Tracks whether a PC/SC reader (the ACR122U) is plugged in right now,
    so the web app's status dot can show connecting / ready / not detected."""

    def update(self, observable, actions):
        added, removed = actions
        for r in added:
            log.info(f"Reader connected: {r}")
        for r in removed:
            log.info(f"Reader disconnected: {r}")
        broadcast({"type": "status", "reader_connected": len(readers()) > 0})


async def ws_handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    log.info(f"Browser tab connected ({len(CONNECTED_CLIENTS)} now watching)")
    try:
        await websocket.send(json.dumps({
            "type": "status",
            "reader_connected": len(readers()) > 0,
        }))
        async for _ in websocket:
            pass  # this bridge is push-only; the page never needs to send anything
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        log.info(f"Browser tab disconnected ({len(CONNECTED_CLIENTS)} left watching)")


async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()

    card_monitor = CardMonitor()
    card_monitor.addObserver(TapObserver())
    reader_monitor = ReaderMonitor()
    reader_monitor.addObserver(ReaderPresenceObserver())

    detected = readers()
    log.info(f"Reader(s) at startup: {detected if detected else 'none — plug in the ACR122U'}")
    log.info(f"Listening on ws://{HOST}:{PORT} for the Saundarya app to connect...")

    async with websockets.serve(ws_handler, HOST, PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")

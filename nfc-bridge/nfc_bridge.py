"""
Saundarya NFC Bridge

Turns an ACS ACR122U (or any PC/SC contactless reader) into a "keyboard
wedge" device: tap a Mifare card, and its UID gets typed into whatever
window is focused, followed by Enter. This lets the Saundarya web app's
existing NFC tap-to-fill code work with a reader that doesn't natively
emulate a keyboard.

IMPORTANT: keep the Saundarya browser tab focused when you tap a card —
whatever window has focus at that moment receives the typed UID.

Requires: pyscard, pynput  (pip install -r requirements.txt)
"""
import os
import time
from datetime import datetime

from smartcard.CardMonitoring import CardMonitor, CardObserver
from pynput.keyboard import Controller, Key

kb = Controller()

# The packaged double-click app has no visible console, so activity is also
# logged to a file in the user's home folder for troubleshooting.
LOG_PATH = os.path.join(os.path.expanduser("~"), "saundarya_nfc_bridge.log")


def log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# Standard PC/SC "Get Data" APDU for a contactless card's UID — supported by
# the ACR122U (and virtually every PC/SC contactless reader) for any
# ISO14443A card, including Mifare 1K.
GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]

# Delay between simulated keystrokes. The Saundarya app's tap listener
# treats keystrokes faster than 50ms apart as "from a reader" — keep this
# comfortably under that.
KEYSTROKE_DELAY_S = 0.01


def type_uid(uid: str):
    log(f"Card tapped — UID: {uid}")
    for ch in uid:
        kb.type(ch)
        time.sleep(KEYSTROKE_DELAY_S)
    kb.press(Key.enter)
    kb.release(Key.enter)


class NfcTapObserver(CardObserver):
    def update(self, observable, actions):
        added_cards, _removed_cards = actions
        for card in added_cards:
            try:
                connection = card.createConnection()
                connection.connect()
                response, sw1, sw2 = connection.transmit(GET_UID_APDU)
                if sw1 == 0x90 and sw2 == 0x00:
                    uid = "".join(f"{b:02X}" for b in response)
                    type_uid(uid)
                else:
                    log(f"Card read failed (status {sw1:02X}{sw2:02X}) — try tapping again")
            except Exception as e:
                log(f"Error reading card: {e}")


def main():
    log("=" * 50)
    log("Saundarya NFC Bridge starting")
    log(f"Activity log: {LOG_PATH}")
    log("Tap a card near the reader to send its UID.")
    log("Keep the Saundarya browser tab focused when tapping.")
    log("=" * 50)

    monitor = CardMonitor()
    observer = NfcTapObserver()
    monitor.addObserver(observer)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.deleteObserver(observer)
        log("Stopped.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Saundarya Fingerprint Bridge

Stays connected to the ZKTeco K40 Pro attendance machine over the local
network (same `pyzk` protocol confirmed working in testing) and forwards
every punch it catches to the live Saundarya server in real time, so a
staff member's dashboard row updates itself the moment they punch — no one
has to type the time in by hand.

Why this exists: browsers can't reach a LAN device directly, and the cloud
server isn't on the salon's local network — this small program is the
middleman, the same role `nfc-bridge/` plays for the card reader, just
talking to a different kind of hardware over the network instead of USB.

Run it on any computer at the salon that's on the same WiFi/LAN as the
fingerprint machine, and that stays on during business hours. It reconnects
on its own if the machine or the network drops.

Setup:
    pip install -r requirements.txt
    cp .env.example .env   # fill in DEVICE_IP, SERVER_URL, BRIDGE_KEY
    python3 bridge.py
"""
import logging
import os
import time

import requests
from dotenv import load_dotenv
from zk import ZK

load_dotenv()

DEVICE_IP = os.environ["DEVICE_IP"]
DEVICE_PORT = int(os.getenv("DEVICE_PORT", "4370"))
SERVER_URL = os.environ["SERVER_URL"].rstrip("/")
BRIDGE_KEY = os.environ["BRIDGE_KEY"]
RECONNECT_DELAY_SECONDS = int(os.getenv("RECONNECT_DELAY_SECONDS", "15"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger("bridge")


def send_punch(user_id: int, timestamp) -> None:
    try:
        resp = requests.post(
            f"{SERVER_URL}/api/v1/attendance/punch",
            json={"device_user_id": user_id, "timestamp": timestamp.isoformat()},
            headers={"X-Bridge-Key": BRIDGE_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if body.get("ignored"):
                logger.warning(f"Punch from unknown device user_id={user_id} — not linked to any staff yet")
            else:
                logger.info(f"Sent: user_id={user_id} at {timestamp} -> staff_id={body.get('staff_id')}")
        else:
            logger.error(f"Server rejected punch (status {resp.status_code}): {resp.text}")
    except Exception as e:
        logger.error(f"Failed to reach server for punch user_id={user_id}: {e}")


def run_forever():
    logger.info(f"Starting bridge — device {DEVICE_IP}:{DEVICE_PORT} -> {SERVER_URL}")
    while True:
        conn = None
        try:
            zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=30, password=0,
                    force_udp=False, ommit_ping=False)
            conn = zk.connect()
            logger.info("Connected to device. Listening for punches...")
            conn.disable_device()
            conn.enable_device()
            for attendance in conn.live_capture():
                if attendance is None:
                    continue
                send_punch(attendance.user_id, attendance.timestamp)
        except Exception as e:
            logger.error(f"Connection lost ({e}) — retrying in {RECONNECT_DELAY_SECONDS}s")
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass
        time.sleep(RECONNECT_DELAY_SECONDS)


if __name__ == "__main__":
    run_forever()

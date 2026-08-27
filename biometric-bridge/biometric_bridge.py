#!/usr/bin/env python3
"""
Saundarya Biometric Bridge
============================
Runs continuously on a computer at the salon (e.g. the reception computer,
same one that already runs nfc_bridge.py), on the same local network as
the RS9n fingerprint machine. Every POLL_INTERVAL_SECONDS, it connects to
the machine, reads its punch records, and forwards any new one to the
Saundarya cloud server's /punch endpoint (the same endpoint already tested
and confirmed working via curl).

Resilience:
  - Keeps a local record (seen_punches.json, next to this script) of which
    punches have already been forwarded, so restarting this program never
    re-sends old punches and never loses track across restarts.
  - If the server can't be reached for a given punch (internet down,
    server restarting, etc.), that punch is simply left un-marked and
    retried on the next cycle — nothing is dropped, it just catches up
    once connectivity returns.
  - If the device itself can't be reached this cycle, it just logs the
    error and tries again next cycle — doesn't crash.

This is not the final /staff/punch processing (that applies the
Present/Late/Half-Day rules and saves to staff_attendance — Stage 2,
built once real payloads have been confirmed flowing). Right now it's
sending to the same logging endpoint used for Stage 1 testing, so every
forwarded punch is visible in /tmp/rs9n_test_punch.log on the server —
that's how to confirm this bridge is actually working end-to-end.

Setup (one-time, on the reception computer):
    pip install -r requirements.txt

Run:
    python3 biometric_bridge.py

Leave it running in a terminal (or set it up to auto-start, same pattern
as nfc_bridge.py, once this is confirmed working reliably).
"""

import json
import logging
import os
import sys
import time

try:
    from zk import ZK
except ImportError:
    print("Missing dependency 'pyzk'. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Missing dependency 'requests'. Run: pip install -r requirements.txt")
    sys.exit(1)

# ── Config — edit these if the device's IP or the server ever change ────────
DEVICE_IP = "192.168.1.224"
DEVICE_PORT = 5005
SERVER_URL = "http://80.225.194.31:8000/punch"
POLL_INTERVAL_SECONDS = 15

SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_punches.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [biometric-bridge] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("biometric-bridge")


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        except Exception as e:
            log.error(f"Could not read {SEEN_FILE}, starting fresh: {e}")
    return set()


def save_seen(seen: set):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        log.error(f"Could not save {SEEN_FILE}: {e}")


def record_key(r) -> str:
    """A unique-enough key per punch so the same one is never forwarded twice."""
    return f"{r.user_id}|{r.timestamp.isoformat()}|{r.status}"


def forward(record) -> bool:
    payload = {
        "device_user_id": record.user_id,
        "time": record.timestamp.isoformat(),
        "status": record.status,
        "punch": record.punch,
    }
    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=10)
        if resp.status_code == 200:
            log.info(f"Forwarded punch OK: {payload}")
            return True
        log.error(f"Server rejected punch {payload}: HTTP {resp.status_code} {resp.text[:200]}")
        return False
    except Exception as e:
        log.error(f"Could not reach server for punch {payload}: {e}")
        return False


def poll_once(seen: set):
    zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=8, password=0, force_udp=False, ommit_ping=False)
    conn = None
    try:
        conn = zk.connect()
        records = conn.get_attendance() or []
    except Exception as e:
        log.error(f"Could not connect/read from device at {DEVICE_IP}:{DEVICE_PORT}: {e}")
        return
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass

    new_count = 0
    for r in records:
        key = record_key(r)
        if key in seen:
            continue
        if forward(r):
            seen.add(key)
            new_count += 1
        # if forward() failed, leave it out of `seen` — it gets retried
        # automatically on the next poll cycle instead of being lost

    if new_count:
        save_seen(seen)
        log.info(f"{new_count} new punch(es) forwarded this cycle ({len(records)} total on device)")
    else:
        log.info(f"No new punches this cycle ({len(records)} total on device, all already forwarded)")


def main():
    log.info(f"Starting — watching {DEVICE_IP}:{DEVICE_PORT}, forwarding to {SERVER_URL}, every {POLL_INTERVAL_SECONDS}s")
    seen = load_seen()
    log.info(f"Loaded {len(seen)} previously-forwarded punch(es) from local memory")
    while True:
        poll_once(seen)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Saundarya Biometric Bridge — Stage 0 connection test
======================================================
Standalone diagnostic script. Does NOT touch the Saundarya app, the
database, or the deployed server in any way — it only tries to connect
directly to the RS9n fingerprint machine over your local network and
report what it finds. Safe to run as many times as you like.

Purpose: find out whether the existing RS9n machine speaks the same
protocol as ZKTeco devices (which the open-source `pyzk` library talks to)
BEFORE spending money on a new device. If this works, the existing machine
is enough — no new hardware needed.

Run this on a computer that's on the SAME local network/WiFi as the
fingerprint machine (e.g. the reception computer) — it won't be able to
reach the machine from anywhere else.

Setup (one-time):
    pip install -r requirements.txt

Run:
    python3 test_connection.py

Edit DEVICE_IP / DEVICE_PORT below if the machine's address ever changes
(check its Communication -> TCP/IP Settings menu on the device itself).
"""

DEVICE_IP = "192.168.1.224"
DEVICE_PORT = 5005

import sys

try:
    from zk import ZK
except ImportError:
    print("Missing dependency 'pyzk'. Run: pip install -r requirements.txt")
    sys.exit(1)


def main():
    print(f"Connecting to {DEVICE_IP}:{DEVICE_PORT} ...")
    zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=8, password=0, force_udp=False, ommit_ping=False)
    conn = None
    try:
        conn = zk.connect()
        print("✅ CONNECTED — the machine understands this protocol!\n")

        try:
            print(f"Firmware version : {conn.get_firmware_version()}")
        except Exception as e:
            print(f"(couldn't read firmware version: {e})")

        try:
            print("\n--- Enrolled users (Device User ID = the number to type into Saundarya's staff form) ---")
            users = conn.get_users()
            if not users:
                print("(no users enrolled yet on this device)")
            for u in users:
                print(f"  Device User ID: {u.user_id}   Name on device: {u.name!r}   Privilege: {u.privilege}")
        except Exception as e:
            print(f"(couldn't read user list: {e})")

        try:
            print("\n--- Recent attendance records stored on the device ---")
            records = conn.get_attendance()
            if not records:
                print("(no punch records stored on the device yet)")
            else:
                for r in records[-10:]:
                    print(f"  Device User ID: {r.user_id}   Time: {r.timestamp}   Status/Type: {r.status}")
                print(f"\n({len(records)} total records on the device; showing last 10)")
        except Exception as e:
            print(f"(couldn't read attendance records: {e})")

        print("\n🎉 Good news: this machine works with pyzk. We can build the real bridge on top of this —")
        print("   no new hardware purchase needed.")

    except Exception as e:
        print(f"❌ COULD NOT CONNECT: {e}")
        print("\nThis means either:")
        print("  - This device doesn't speak the ZKTeco-compatible protocol pyzk expects, or")
        print("  - It's not reachable from this computer (check you're on the same WiFi/network as the")
        print(f"    machine, and that {DEVICE_IP} is still its current IP), or")
        print("  - The port (currently set to try {DEVICE_PORT}) doesn't match what's configured on the device.")
        print("\nSend this exact output back and we'll figure out the next step from there.")
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()

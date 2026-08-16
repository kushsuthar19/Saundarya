#!/usr/bin/env python3
"""
Backfills beauty points that were never credited because of two bugs that
are now fixed in code, but whose damage is already sitting in the database
from before the fix went live:

  1. Daily Entry matched clients by an EXACT phone string. If a bill's phone
     was typed with different formatting than the client's stored number
     (extra space, missing/extra +91, a dash), the bill silently attached to
     a brand-new duplicate client instead of the real member — so it never
     had an active membership to credit points to. The bill still shows up
     in that member's profile because Service History is looked up BY PHONE
     STRING, not by client_id, which is what made this look like "points
     just don't show" rather than "wrong client".
  2. pay_method was VARCHAR2(30); a Split-paid bill can need more than that
     ("Split|Cash:3175|UPI:3175|Card:0" is 31 chars), which could reject the
     whole save.

Both are fixed going forward (phone now matches on last-10-digits; the
column is wider). This script repairs existing data: for every Active
membership, it re-matches that client's phone (the same last-10-digit rule
the app now uses) against ALL daily_entries, and credits any bill that
should have earned points (₹100 = 1pt, from their join date on, excluding
the membership fee itself) but has no matching entry in beauty_points_log.

Idempotent — safe to run more than once, it only inserts for bills that
don't already have a 'Service: <inv_no>' row logged.

Usage:
    source venv/bin/activate
    python3 database/backfill_missing_points.py --dry-run   # preview only, no writes
    python3 database/backfill_missing_points.py             # actually apply
"""
import argparse
import os

from dotenv import load_dotenv
import oracledb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing")
    args = parser.parse_args()

    load_dotenv()
    conn = oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        dsn=os.environ["ORACLE_DSN"],
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT m.id, m.client_id, c.phone, c.name, m.start_date
        FROM memberships m
        JOIN clients c ON c.id = m.client_id
        WHERE m.status = 'Active' AND c.phone IS NOT NULL
    """)
    members = cur.fetchall()
    print(f"Checking {len(members)} active membership(s)...\n")

    total_entries_fixed = 0
    total_pts = 0

    for mem_id, client_id, phone, name, start_date in members:
        cur.execute("""
            SELECT inv_no, net_total, entry_date, client_id
            FROM daily_entries
            WHERE SUBSTR(REGEXP_REPLACE(phone,'[^0-9]',''),-10) =
                  SUBSTR(REGEXP_REPLACE(:1,'[^0-9]',''),-10)
              AND visit_type != 'Membership'
              AND (:2 IS NULL OR entry_date >= :2)
        """, [phone, start_date])
        entries = cur.fetchall()

        for inv_no, net_total, entry_date, entry_client_id in entries:
            pts = int((net_total or 0) // 100)
            if pts <= 0:
                continue
            cur.execute(
                "SELECT COUNT(*) FROM beauty_points_log WHERE membership_id=:1 AND notes = 'Service: '||:2",
                [mem_id, inv_no]
            )
            if cur.fetchone()[0] > 0:
                continue  # already credited

            mismatch = " [was attached to a different client_id — the old exact-phone-match bug]" \
                if entry_client_id != client_id else ""
            print(f"  {name} (membership {mem_id}): {inv_no} on {entry_date} "
                  f"— Rs.{net_total} -> +{pts} pts{mismatch}")
            total_entries_fixed += 1
            total_pts += pts

            if not args.dry_run:
                cur.execute(
                    "INSERT INTO beauty_points_log (membership_id, entry_type, points, notes) "
                    "VALUES (:1, 'Earned', :2, 'Service: '||:3)",
                    [mem_id, pts, inv_no]
                )

    if not args.dry_run and total_entries_fixed:
        cur.execute("""
            UPDATE memberships m
            SET beauty_points = GREATEST(0, (
                    SELECT NVL(SUM(CASE WHEN l.entry_type='redeem' THEN -l.points ELSE l.points END),0)
                    FROM beauty_points_log l WHERE l.membership_id = m.id)),
                lifetime_points = (
                    SELECT NVL(SUM(CASE WHEN l.entry_type!='redeem' THEN l.points ELSE 0 END),0)
                    FROM beauty_points_log l WHERE l.membership_id = m.id)
            WHERE status = 'Active'
        """)
        conn.commit()

    verb = "Would fix" if args.dry_run else "Fixed"
    print(f"\n{verb}: {total_entries_fixed} entries, {total_pts} points total.")
    if args.dry_run and total_entries_fixed:
        print("Re-run without --dry-run to apply.")
    conn.close()


if __name__ == "__main__":
    main()

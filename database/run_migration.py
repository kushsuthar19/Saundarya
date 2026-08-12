#!/usr/bin/env python3
"""
Runs a .sql migration file (e.g. database/migration_membership_nfc_schema.sql)
against the Oracle DB configured in .env — without needing sqlplus or an
Oracle Client install. The backend already depends on python-oracledb,
which talks to Oracle directly over the network, so this reuses that.

Usage (from the repo root, with the venv active — same one run.sh uses):
    source venv/bin/activate
    python3 database/run_migration.py database/migration_membership_nfc_schema.sql

Run this on whichever machine can actually reach the Oracle DB named in
.env (for the live system, that's the Oracle VM itself — SSH in first).
"""
import os
import sys

from dotenv import load_dotenv
import oracledb


def split_into_blocks(sql_text: str) -> list[str]:
    """Mirrors how SQL*Plus splits a script on a lone '/' line — each chunk
    between '/' markers is executed as one statement (a PL/SQL block, or a
    single DDL/DML statement)."""
    blocks, current = [], []
    for line in sql_text.splitlines():
        if line.strip() == "/":
            if current:
                blocks.append("\n".join(current))
            current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def label_for(block: str) -> str:
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("EXECUTE IMMEDIATE"):
            return s[len("EXECUTE IMMEDIATE"):].strip(" q'[").replace("\n", " ")[:70]
    for line in block.splitlines():
        s = line.strip()
        if s and not s.startswith("--"):
            return s[:70]
    return block[:70]


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 database/run_migration.py <path-to-migration.sql>")
        sys.exit(1)
    path = sys.argv[1]

    load_dotenv()
    user = os.environ["ORACLE_USER"]
    password = os.environ["ORACLE_PASSWORD"]
    dsn = os.environ["ORACLE_DSN"]

    sql_text = open(path).read()
    blocks = [b for b in split_into_blocks(sql_text)
              if any(l.strip() and not l.strip().startswith("--") for l in b.splitlines())]
    # The trailing bare COMMIT isn't a statement oracledb's execute() accepts
    # (it's a SQL*Plus/session command) — every block below already commits
    # itself on success, so it's redundant and safe to skip.
    blocks = [b for b in blocks if b.strip().rstrip(";").upper() != "COMMIT"]

    print(f"Connecting to {dsn} as {user}...")
    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    cursor = conn.cursor()

    ok = 0
    for i, block in enumerate(blocks, 1):
        label = label_for(block)
        try:
            cursor.execute(block)
            conn.commit()
            print(f"  [{i}/{len(blocks)}] OK     — {label}")
            ok += 1
        except Exception as e:
            print(f"  [{i}/{len(blocks)}] FAILED — {label}\n      {e}")

    conn.close()
    print(f"\nDone: {ok}/{len(blocks)} statements applied successfully.")
    if ok != len(blocks):
        sys.exit(1)


if __name__ == "__main__":
    main()

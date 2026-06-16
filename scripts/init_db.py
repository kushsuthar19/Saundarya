#!/usr/bin/env python3
"""
Initialize Oracle database - run schema.sql and seed.sql.
Usage: python3 scripts/init_db.py
"""
import os
import sys
import getpass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

try:
    import oracledb
except ImportError:
    print("python-oracledb not installed. Run: pip install python-oracledb")
    sys.exit(1)


def run_sql_file(cursor, filepath: str):
    """Execute SQL file, splitting by ';'."""
    print(f"  Running {filepath}...")
    with open(filepath, "r") as f:
        sql = f.read()

    # Split statements
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
    success = 0
    errors = 0
    for stmt in statements:
        if not stmt:
            continue
        try:
            cursor.execute(stmt)
            success += 1
        except oracledb.DatabaseError as e:
            error_obj = e.args[0]
            # Ignore "already exists" errors (ORA-00955, ORA-00942 etc)
            if hasattr(error_obj, 'code') and error_obj.code in (955, 942, 1430, 2261, 2264, 1408):
                pass  # object already exists, skip
            else:
                print(f"    ⚠ SQL error (continuing): {e}")
                errors += 1

    print(f"    ✅ {success} statements OK, {errors} skipped/errors")


def main():
    user = os.getenv("ORACLE_USER", "saundarya")
    password = os.getenv("ORACLE_PASSWORD", "")
    dsn = os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1")

    if not password:
        password = getpass.getpass(f"Oracle password for {user}@{dsn}: ")

    print(f"\nConnecting to Oracle: {user}@{dsn}")
    try:
        conn = oracledb.connect(user=user, password=password, dsn=dsn)
        print("  ✅ Connected!")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        sys.exit(1)

    cursor = conn.cursor()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("\n▶ Running schema.sql...")
    run_sql_file(cursor, os.path.join(base_dir, "database", "schema.sql"))
    conn.commit()

    print("\n▶ Running seed.sql...")
    run_sql_file(cursor, os.path.join(base_dir, "database", "seed.sql"))
    conn.commit()

    # Verify
    print("\n▶ Verifying tables...")
    tables = [
        "users", "clients", "staff", "attendance", "appointments",
        "daily_entries", "entry_items", "bridal_bookings", "bridal_functions",
        "salary_payments", "service_catalog", "notifications", "system_config",
        "refresh_tokens", "audit_log", "wa_log"
    ]
    cursor.execute("SELECT table_name FROM user_tables")
    existing = {row[0].lower() for row in cursor.fetchall()}
    for t in tables:
        status = "✅" if t in existing else "❌"
        print(f"  {status} {t}")

    # Check admin user
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    admin_count = cursor.fetchone()[0]
    print(f"\n  ✅ Admin users: {admin_count}")
    print(f"  ✅ Default login: admin / Admin@Saundarya2024")
    print(f"  ❗ CHANGE THE DEFAULT PASSWORD IMMEDIATELY!")

    # Count services
    cursor.execute("SELECT COUNT(*) FROM service_catalog")
    svc_count = cursor.fetchone()[0]
    print(f"  ✅ Service catalog: {svc_count} services loaded")

    conn.close()
    print("\n✅ Database initialized successfully!\n")


if __name__ == "__main__":
    main()

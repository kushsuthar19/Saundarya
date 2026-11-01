-- Migration: global "Day Off" toggle for business-wide closures
-- ============================================================
-- One row per date the shop is fully closed (multi-day Diwali/New Year
-- shutdown, etc). A date in this table excludes EVERY staff member from
-- absence/deduction in salary calc for that date — individual attendance
-- rows are untouched, this is purely an override checked at salary-calc
-- time.
--
-- Safe to run against the live DB. Run via:
--   python3 database/run_migration.py database/migration_day_off.sql

BEGIN
  EXECUTE IMMEDIATE 'CREATE TABLE day_off_dates (
    off_date   DATE PRIMARY KEY,
    created_at TIMESTAMP DEFAULT SYSTIMESTAMP
  )';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

COMMIT;

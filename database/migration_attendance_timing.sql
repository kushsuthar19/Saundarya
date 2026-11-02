-- Migration: separate Morning Duty punch times from the main day-shift
-- punch times, so both sessions can be tracked on the same day.
-- ============================================================
-- attendance.in_time / out_time already represent the main day shift.
-- These two new columns hold the (2:30 AM-9:00 AM) Morning Duty session's
-- own in/out times, independent of the day shift.
--
-- Safe to run against the live DB. Run via:
--   python3 database/run_migration.py database/migration_attendance_timing.sql

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE attendance ADD morning_in_time VARCHAR2(10)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE attendance ADD morning_out_time VARCHAR2(10)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

COMMIT;

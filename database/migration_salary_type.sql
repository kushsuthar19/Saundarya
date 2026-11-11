-- Migration: Fixed vs Commission-based salary per staff member
-- ============================================================
-- Lets a staff member be marked "fixed" (no commission at all, ever,
-- regardless of revenue) instead of the default "commission" behavior
-- (today's existing 2%/3% monthly-revenue tier, unchanged for everyone
-- who doesn't explicitly opt into fixed).
--
-- Safe to run against the live DB. Run via:
--   python3 database/run_migration.py database/migration_salary_type.sql

BEGIN
  EXECUTE IMMEDIATE q'[ALTER TABLE staff ADD salary_type VARCHAR2(20) DEFAULT 'commission']';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

COMMIT;

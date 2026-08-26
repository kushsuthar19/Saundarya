-- Migration: link a staff member to their fingerprint machine's Device User ID
-- ============================================================
-- The RS9n biometric machine identifies staff by an internal numeric
-- "Device User ID" assigned at fingerprint enrollment — not by name. This
-- column stores that mapping so a punch event (device_user_id) can be
-- resolved back to our staff.id.
--
-- Nullable — existing staff rows are unaffected until someone fills it in.
-- Unique index allows any number of NULLs (Oracle's normal behavior) but
-- rejects two staff being mapped to the same device ID by mistake.
--
-- Safe to run against the live DB. Run once via SQL Worksheet or:
--   sqlplus SAUNDARYA/<password>@<dsn> @database/migration_staff_device_id.sql

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE staff ADD device_user_id NUMBER';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE UNIQUE INDEX idx_staff_device_uid ON staff(device_user_id)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

COMMIT;

-- Migration: grace period for the Exclusive Membership 60-day revisit rule
-- ============================================================
-- Staff can grant a client a few extra days past their normal 60-day
-- "visit or auto-discontinue" deadline, from that client's own Exclusive
-- Member Profile. Stored as a relative day-count (not an absolute date) so
-- it keeps combining correctly with the existing
-- GREATEST(last_visit, start_date, updated_at) baseline even if that
-- baseline later changes (e.g. an edited/backdated entry). Reset to 0 the
-- next time the client's last_visit genuinely advances (see entries.py) —
-- a grace period only ever covers one cycle, never carries forward.
--
-- Run once against your live Oracle DB (SQL*Plus / SQLcl):
--   sqlplus SAUNDARYA/<password>@<dsn> @database/migration_membership_grace_period.sql

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE memberships ADD grace_days NUMBER DEFAULT 0';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

COMMIT;

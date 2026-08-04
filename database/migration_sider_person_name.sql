-- Migration: add person_name to bridal_functions
-- Sider/Guest bookings need to store each person's NAME against their
-- function row, but the existing person_count column is NUMBER (used by
-- Bride/Groom bookings to store a headcount) — a name string silently
-- failed validation and was never saved. This adds a proper text column
-- for it. Safe to run against the live DB; only adds a nullable column.

ALTER TABLE bridal_functions ADD person_name VARCHAR2(100);

COMMIT;

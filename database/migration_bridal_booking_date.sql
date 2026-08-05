-- Migration: persist booking_date on bridal_bookings
-- Previously the "Booking Date" typed into the Bride/Groom form was used only
-- to date the auto-created advance Daily Entry, then thrown away — it was
-- never actually saved on the booking, so the "Booked On" column in All
-- Bookings fell back to created_at (server save time) instead of the date
-- the admin actually entered. This adds a real column for it.
-- Safe to run against the live DB; only adds a nullable column + backfills it.

ALTER TABLE bridal_bookings ADD booking_date DATE;

-- Backfill existing bookings so "Booked On" shows something sensible
-- instead of blank for rows created before this migration.
UPDATE bridal_bookings SET booking_date = TRUNC(created_at) WHERE booking_date IS NULL;

COMMIT;

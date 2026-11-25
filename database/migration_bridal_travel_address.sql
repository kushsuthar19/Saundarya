-- Migration: add travel_address to bridal_bookings
-- A new field, separate from the existing "venue" column — only shown in
-- the form (and printed on the PDF) when there's an actual transport
-- charge on the booking, since that's what makes a travel destination
-- address relevant in the first place.
-- Safe to run against the live DB; only adds a nullable column.

ALTER TABLE bridal_bookings ADD travel_address VARCHAR2(200);

COMMIT;

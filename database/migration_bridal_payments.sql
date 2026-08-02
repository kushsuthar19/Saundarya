-- Migration: bridal payment history (advance + due payments, each with its own date)
-- Run this once against your live Oracle DB. Safe to run even though bridal_bookings
-- already exists — this only adds a new table, it doesn't touch existing data.

CREATE SEQUENCE seq_br_pay START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

CREATE TABLE bridal_payments (
    id             NUMBER DEFAULT seq_br_pay.NEXTVAL PRIMARY KEY,
    booking_id     NUMBER NOT NULL REFERENCES bridal_bookings(id) ON DELETE CASCADE,
    payment_type   VARCHAR2(30) DEFAULT 'Advance',
    amount         NUMBER(10,2) DEFAULT 0,
    pay_method     VARCHAR2(30) DEFAULT 'Cash',
    payment_date   DATE NOT NULL,
    notes          VARCHAR2(500),
    created_by     NUMBER REFERENCES users(id),
    created_at     TIMESTAMP DEFAULT SYSTIMESTAMP
);

CREATE INDEX idx_br_pay_booking ON bridal_payments(booking_id);

-- Backfill: log each existing booking's current advance as a single
-- "Advance" payment dated to when the booking was created, so old
-- bookings show at least one row in their payment history instead of none.
INSERT INTO bridal_payments (booking_id, payment_type, amount, pay_method, payment_date, notes, created_by)
SELECT id, 'Advance', advance_paid, 'Cash', TRUNC(created_at), 'Backfilled from existing booking', created_by
FROM bridal_bookings
WHERE advance_paid > 0;

COMMIT;

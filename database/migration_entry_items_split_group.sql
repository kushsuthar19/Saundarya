-- Migration: track which entry_items rows came from the same "Split
-- between staff" action, so the invoice PDF / WhatsApp message can merge
-- only those rows back into one line — not any two rows that merely
-- happen to share the same service name (e.g. two genuinely separate
-- Threading services billed under the same visit).
--
-- NULL means "not part of a split" (the normal case) — two different
-- NULL rows are never merged, regardless of name. Two rows sharing the
-- same non-null split_group value ARE merged, since that only ever
-- happens when the Split button created them together.
--
-- Run once against your live Oracle DB (SQL*Plus / SQLcl):
--   sqlplus SAUNDARYA/<password>@<dsn> @database/migration_entry_items_split_group.sql

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE entry_items ADD split_group VARCHAR2(40)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

COMMIT;

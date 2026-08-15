-- Migration: widen pay_method columns so Split payments don't get truncated
--
-- pay_method normally stores plain "Cash"/"UPI"/"Card", but a Split payment
-- is encoded as "Split|Cash:<n>|UPI:<n>|Card:<n>" (see frontend
-- calcSplitTotal()/calcBridalSplit()). The fixed text in that template is
-- 22 characters, leaving only 8 digits of budget across all three amounts
-- combined in a VARCHAR2(30) column — e.g. a plain ₹2,000 bill split evenly
-- as 1000/1000 ("...Cash:1000|UPI:1000|Card:0") is already 31 characters
-- and overflows it. Oracle raises ORA-12899 on that INSERT — which happens
-- outside any try/except in create_entry() and in the bridal advance/due-
-- payment mirrors in main_routers.py — so the whole save fails outright.
-- Points never got the chance to be wrong; the entry (and its points log
-- row) never made it into the table at all.
--
-- Safe to run against the live DB; MODIFY only widens the column, no data
-- is touched or lost, and it's safe to re-run.
--
-- Run this once on whichever machine can reach the Oracle DB named in .env
-- (for production that's the Oracle VM itself — SSH in first):
--   source venv/bin/activate
--   python3 database/run_migration.py database/migration_widen_pay_method.sql

ALTER TABLE daily_entries MODIFY (pay_method VARCHAR2(100))
/
ALTER TABLE bridal_payments MODIFY (pay_method VARCHAR2(100))
/

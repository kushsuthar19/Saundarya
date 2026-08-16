-- Migration: add optional add-on package (item + amount) to each bridal function
--
-- The Bride booking form has an "Add-on Services" box (e.g. a Sider makeup
-- package tacked onto a specific function like Sangeet or Haldi, on top of
-- the main bridal package). Previously that box only fed the on-screen
-- Balance Due preview — it was never actually sent to the server, so
-- whatever was added there silently vanished on save and never appeared on
-- the invoice. This adds columns to store it against the function it
-- belongs to.
--
-- Safe to run against the live DB; only adds nullable/defaulted columns.

ALTER TABLE bridal_functions ADD addon_item VARCHAR2(200)
/
ALTER TABLE bridal_functions ADD addon_amount NUMBER(10,2) DEFAULT 0
/

-- Migration: extend wa_log for the named-template WhatsApp automation
-- ============================================================
-- wa_log already existed in schema.sql (phone, type, ref_id, message,
-- status, sent_at) but was never actually used anywhere in the code — the
-- new send_whatsapp_template() in backend/services/whatsapp_service.py is
-- the first thing to write to it. Reusing it instead of adding a brand
-- new whatsapp_sent_log table, per the plan.
--
-- Adds:
--   client_id      — the clients.id this send was about, when known
--   template_key   — which AiSensy template was used (e.g. 'daily_entry',
--                    'bridal_bride', 'winback') — matches the keys in
--                    whatsapp_service.TEMPLATE_CAMPAIGNS
--   error_message  — the failure reason when status='failed', NULL on success
--
-- Every statement below is individually guarded so it's safe to run even
-- if some or all of it already exists.
--
-- Run once against your live Oracle DB (SQL*Plus / SQLcl):
--   sqlplus SAUNDARYA/<password>@<dsn> @database/migration_wa_log_extend.sql

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE wa_log ADD client_id NUMBER REFERENCES clients(id)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE wa_log ADD template_key VARCHAR2(60)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE wa_log ADD error_message VARCHAR2(1000)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_wa_log_client ON wa_log(client_id)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_wa_log_template ON wa_log(template_key)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

COMMIT;

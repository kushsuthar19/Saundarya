-- ============================================================
-- WhatsApp message templates + broadcast history
-- Run once against the existing schema.
-- ============================================================

CREATE SEQUENCE seq_wa_tmpl  START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_wa_bcast START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

-- One row per AiSensy-approved template you want click-to-send in the app.
-- `params` is a JSON array describing the {{1}}, {{2}}, ... variables of the
-- approved template IN ORDER, e.g.:
--   [{"label":"Client Name","type":"client_name"},
--    {"label":"Offer Text","type":"static"}]
-- type "client_name" / "phone" are auto-filled per recipient from the
-- clients table; type "static" is typed once when sending and reused for
-- every recipient in that broadcast.
CREATE TABLE wa_templates (
    id            NUMBER DEFAULT seq_wa_tmpl.NEXTVAL PRIMARY KEY,
    name          VARCHAR2(100) NOT NULL,
    campaign_name VARCHAR2(200) NOT NULL,
    params        CLOB,
    is_active     NUMBER(1)     DEFAULT 1,
    created_by    NUMBER REFERENCES users(id),
    created_at    TIMESTAMP     DEFAULT SYSTIMESTAMP,
    updated_at    TIMESTAMP     DEFAULT SYSTIMESTAMP
);

-- One row per "Send" click, for an audit trail of what was blasted to whom.
CREATE TABLE wa_broadcasts (
    id            NUMBER DEFAULT seq_wa_bcast.NEXTVAL PRIMARY KEY,
    template_id   NUMBER REFERENCES wa_templates(id),
    template_name VARCHAR2(100),
    audience_desc VARCHAR2(300),
    total_count   NUMBER DEFAULT 0,
    sent_count    NUMBER DEFAULT 0,
    failed_count  NUMBER DEFAULT 0,
    failures      CLOB,
    sent_by       NUMBER REFERENCES users(id),
    created_at    TIMESTAMP DEFAULT SYSTIMESTAMP
);
CREATE INDEX idx_wa_bcast_tmpl ON wa_broadcasts(template_id);

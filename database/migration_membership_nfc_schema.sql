-- Migration: Exclusive Membership + NFC card schema
-- ============================================================
-- backend/routers/clients.py and entries.py have read/written the
-- `memberships`, `nfc_cards`, and `beauty_points_log` tables (plus a few
-- extra `clients` columns) since the Exclusive Member feature was built,
-- but none of that was ever captured in database/schema.sql or a
-- migration file — only the tables in schema.sql are tracked here.
-- If your live DB already has these objects (likely, since the feature
-- has real members/cards in it), this is just documentation being caught
-- up to reality. Every statement below is individually guarded so it's
-- safe to run even if some or all of it already exists — it skips
-- anything already present instead of erroring.
--
-- Run this once against your live Oracle DB (SQL*Plus / SQLcl):
--   sqlplus SAUNDARYA/<password>@<dsn> @database/migration_membership_nfc_schema.sql

-- ── clients: columns the app relies on that schema.sql never had ────────────
BEGIN
  EXECUTE IMMEDIATE q'[ALTER TABLE clients ADD client_type VARCHAR2(20) DEFAULT 'New']';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE clients ADD anniversary DATE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE clients ADD preferred_staff VARCHAR2(100)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE clients ADD gender VARCHAR2(20)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE clients ADD address VARCHAR2(300)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE clients ADD visit_count NUMBER DEFAULT 0';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE clients ADD last_visit DATE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

-- ── sequences ─────────────────────────────────────────────────────────────
BEGIN
  EXECUTE IMMEDIATE 'CREATE SEQUENCE seq_memberships START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE SEQUENCE seq_nfc_cards START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE SEQUENCE seq_beauty_pts START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

-- ── memberships (SBC001-style membership_id, one Active row per client) ────
BEGIN
  EXECUTE IMMEDIATE q'[
    CREATE TABLE memberships (
        id               NUMBER DEFAULT seq_memberships.NEXTVAL PRIMARY KEY,
        client_id        NUMBER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        membership_id    VARCHAR2(20) NOT NULL UNIQUE,
        status           VARCHAR2(20)  DEFAULT 'Active',
        -- status: 'Active' | 'Discontinued' (set by nightly auto-discontinue job) | others as used by the app
        fee_paid         NUMBER(10,2)  DEFAULT 0,
        start_date       DATE,
        expiry_date      DATE,
        beauty_points    NUMBER        DEFAULT 0,
        lifetime_points  NUMBER        DEFAULT 0,
        notes            VARCHAR2(500),
        created_at       TIMESTAMP     DEFAULT SYSTIMESTAMP,
        updated_at       TIMESTAMP     DEFAULT SYSTIMESTAMP
    )]';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_mem_client ON memberships(client_id)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
-- No separate index on membership_id: the UNIQUE constraint above already
-- creates one automatically (an explicit CREATE INDEX on the same column
-- collides with it — ORA-01408, caught by testing this against a live DB).

-- ── nfc_cards (one Active card per membership; UID → membership lookup) ────
BEGIN
  EXECUTE IMMEDIATE q'[
    CREATE TABLE nfc_cards (
        id              NUMBER DEFAULT seq_nfc_cards.NEXTVAL PRIMARY KEY,
        membership_id   NUMBER NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
        card_uid        VARCHAR2(64) NOT NULL,
        status          VARCHAR2(20) DEFAULT 'Active',
        -- status: 'Active' | 'Inactive' (old card, replaced)
        issued_date     DATE DEFAULT SYSDATE,
        deactivated_at  TIMESTAMP,
        created_at      TIMESTAMP DEFAULT SYSTIMESTAMP
    )]';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_nfc_uid ON nfc_cards(card_uid)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_nfc_membership ON nfc_cards(membership_id)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

-- ── beauty_points_log (append-only ledger; running balance = SUM) ──────────
BEGIN
  EXECUTE IMMEDIATE q'[
    CREATE TABLE beauty_points_log (
        id             NUMBER DEFAULT seq_beauty_pts.NEXTVAL PRIMARY KEY,
        membership_id  NUMBER NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
        entry_type     VARCHAR2(20) NOT NULL,
        -- entry_type: 'add' | 'redeem' | 'Earned' (mixed casing exists across
        -- the app's own INSERTs — left unconstrained here to match, not fixed)
        points         NUMBER DEFAULT 0 NOT NULL,
        reference_inv  VARCHAR2(50),
        notes          VARCHAR2(500),
        created_at     TIMESTAMP DEFAULT SYSTIMESTAMP
    )]';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX idx_bpts_membership ON beauty_points_log(membership_id)';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

COMMIT;

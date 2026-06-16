-- ============================================================
-- SAUNDARYA BEAUTY CARE & ACADEMY
-- Oracle Database Schema
-- ============================================================

-- DROP existing (run only on fresh setup)
-- DROP SEQUENCE seq_users; DROP TABLE users CASCADE CONSTRAINTS;

-- ============================================================
-- SEQUENCES
-- ============================================================
CREATE SEQUENCE seq_users      START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_clients    START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_staff      START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_appts      START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_entries    START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_items      START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_bridal     START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_br_funcs   START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_att        START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_salary     START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_notif      START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_svc_cat    START WITH 1  INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE seq_inv        START WITH 1001 INCREMENT BY 1 NOCACHE NOCYCLE;

-- ============================================================
-- USERS (Admin + Staff login)
-- ============================================================
CREATE TABLE users (
    id            NUMBER DEFAULT seq_users.NEXTVAL PRIMARY KEY,
    username      VARCHAR2(50)  NOT NULL UNIQUE,
    email         VARCHAR2(100) UNIQUE,
    full_name     VARCHAR2(100) NOT NULL,
    hashed_pw     VARCHAR2(256) NOT NULL,
    role          VARCHAR2(20)  DEFAULT 'staff' NOT NULL,
    -- role: 'admin' | 'staff'
    is_active     NUMBER(1)     DEFAULT 1,
    last_login    TIMESTAMP,
    failed_logins NUMBER        DEFAULT 0,
    locked_until  TIMESTAMP,
    created_at    TIMESTAMP     DEFAULT SYSTIMESTAMP,
    updated_at    TIMESTAMP     DEFAULT SYSTIMESTAMP,
    CONSTRAINT chk_role CHECK (role IN ('admin','staff'))
);

-- ============================================================
-- REFRESH TOKENS (JWT rotation)
-- ============================================================
CREATE TABLE refresh_tokens (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     NUMBER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR2(256) NOT NULL UNIQUE,
    expires_at  TIMESTAMP NOT NULL,
    revoked     NUMBER(1) DEFAULT 0,
    ip_address  VARCHAR2(45),
    user_agent  VARCHAR2(256),
    created_at  TIMESTAMP DEFAULT SYSTIMESTAMP
);

-- ============================================================
-- AUDIT LOG
-- ============================================================
CREATE TABLE audit_log (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     NUMBER REFERENCES users(id),
    action      VARCHAR2(100) NOT NULL,
    table_name  VARCHAR2(50),
    record_id   NUMBER,
    old_data    CLOB,
    new_data    CLOB,
    ip_address  VARCHAR2(45),
    created_at  TIMESTAMP DEFAULT SYSTIMESTAMP
);

-- ============================================================
-- CLIENTS
-- ============================================================
CREATE TABLE clients (
    id           NUMBER DEFAULT seq_clients.NEXTVAL PRIMARY KEY,
    name         VARCHAR2(100) NOT NULL,
    phone        VARCHAR2(20),
    email        VARCHAR2(100),
    birthday     DATE,
    skin_type    VARCHAR2(30)  DEFAULT 'Normal',
    hair_type    VARCHAR2(30)  DEFAULT 'Normal',
    tag          VARCHAR2(30)  DEFAULT 'Regular',
    preferences  VARCHAR2(500),
    visits       NUMBER        DEFAULT 0,
    total_spent  NUMBER(12,2)  DEFAULT 0,
    source       VARCHAR2(50)  DEFAULT 'Manual',
    created_at   TIMESTAMP     DEFAULT SYSTIMESTAMP,
    updated_at   TIMESTAMP     DEFAULT SYSTIMESTAMP
);
CREATE INDEX idx_clients_phone ON clients(phone);
CREATE INDEX idx_clients_name  ON clients(UPPER(name));

-- ============================================================
-- STAFF
-- ============================================================
CREATE TABLE staff (
    id              NUMBER DEFAULT seq_staff.NEXTVAL PRIMARY KEY,
    user_id         NUMBER REFERENCES users(id),
    name            VARCHAR2(100) NOT NULL,
    role            VARCHAR2(50),
    phone           VARCHAR2(20),
    join_date       DATE,
    base_salary     NUMBER(10,2) DEFAULT 0,
    commission_pct  NUMBER(5,2)  DEFAULT 10,
    days_present    NUMBER       DEFAULT 0,
    total_services  NUMBER       DEFAULT 0,
    comm_earned     NUMBER(10,2) DEFAULT 0,
    paid_salary     NUMBER(10,2) DEFAULT 0,
    av_class        VARCHAR2(10) DEFAULT 'a0',
    is_active       NUMBER(1)    DEFAULT 1,
    created_at      TIMESTAMP    DEFAULT SYSTIMESTAMP,
    updated_at      TIMESTAMP    DEFAULT SYSTIMESTAMP
);

-- ============================================================
-- ATTENDANCE
-- ============================================================
CREATE TABLE attendance (
    id           NUMBER DEFAULT seq_att.NEXTVAL PRIMARY KEY,
    staff_id     NUMBER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    att_date     DATE   NOT NULL,
    is_present   NUMBER(1)    DEFAULT 0,
    half_day     NUMBER(1) DEFAULT 0,
    in_time      VARCHAR2(10),
    out_time     VARCHAR2(10),
    hours_worked NUMBER(5,2),
    created_at   TIMESTAMP    DEFAULT SYSTIMESTAMP,
    updated_at   TIMESTAMP    DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_staff_date UNIQUE (staff_id, att_date)
);
CREATE INDEX idx_att_date    ON attendance(att_date);
CREATE INDEX idx_att_staff   ON attendance(staff_id);

-- ============================================================
-- APPOINTMENTS
-- ============================================================
CREATE TABLE appointments (
    id           NUMBER DEFAULT seq_appts.NEXTVAL PRIMARY KEY,
    client_name  VARCHAR2(100) NOT NULL,
    phone        VARCHAR2(20),
    service      VARCHAR2(200),
    appt_date    DATE,
    appt_time    VARCHAR2(10),
    staff_id     NUMBER REFERENCES staff(id),
    staff_name   VARCHAR2(100),
    advance      NUMBER(10,2) DEFAULT 0,
    status       VARCHAR2(30) DEFAULT 'Confirmed',
    notes        VARCHAR2(500),
    created_by   NUMBER REFERENCES users(id),
    created_at   TIMESTAMP    DEFAULT SYSTIMESTAMP,
    updated_at   TIMESTAMP    DEFAULT SYSTIMESTAMP,
    CONSTRAINT chk_appt_status CHECK (status IN ('Confirmed','Pending','Completed','Cancelled'))
);
CREATE INDEX idx_appt_date   ON appointments(appt_date);
CREATE INDEX idx_appt_status ON appointments(status);

-- ============================================================
-- DAILY ENTRIES (Bills/Invoices)
-- ============================================================
CREATE TABLE daily_entries (
    id           NUMBER DEFAULT seq_entries.NEXTVAL PRIMARY KEY,
    inv_no       VARCHAR2(20) NOT NULL UNIQUE,
    client_id    NUMBER REFERENCES clients(id),
    client_name  VARCHAR2(100) NOT NULL,
    phone        VARCHAR2(20),
    entry_date   DATE          NOT NULL,
    visit_type   VARCHAR2(30)  DEFAULT 'Walk-in',
    services     VARCHAR2(2000),
    gross_total  NUMBER(10,2)  DEFAULT 0,
    discount     NUMBER(10,2)  DEFAULT 0,
    net_total    NUMBER(10,2)  DEFAULT 0,
    pay_method   VARCHAR2(30)  DEFAULT 'Cash',
    next_visit   DATE,
    remarks      VARCHAR2(500),
    wa_sent      NUMBER(1)     DEFAULT 0,
    created_by   NUMBER REFERENCES users(id),
    created_at   TIMESTAMP     DEFAULT SYSTIMESTAMP,
    updated_at   TIMESTAMP     DEFAULT SYSTIMESTAMP
);
CREATE INDEX idx_entry_date   ON daily_entries(entry_date);
CREATE INDEX idx_entry_client ON daily_entries(client_id);
CREATE INDEX idx_entry_inv    ON daily_entries(inv_no);

CREATE TABLE entry_items (
    id           NUMBER DEFAULT seq_items.NEXTVAL PRIMARY KEY,
    entry_id     NUMBER NOT NULL REFERENCES daily_entries(id) ON DELETE CASCADE,
    service_name VARCHAR2(200) NOT NULL,
    price        NUMBER(10,2)  DEFAULT 0,
    qty          NUMBER        DEFAULT 1,
    staff_id     NUMBER REFERENCES staff(id),
    staff_name   VARCHAR2(100),
    line_total   NUMBER(10,2)  DEFAULT 0
);
CREATE INDEX idx_items_entry ON entry_items(entry_id);

-- ============================================================
-- BRIDAL BOOKINGS
-- ============================================================
    CREATE TABLE bridal_bookings (
        id             NUMBER DEFAULT seq_bridal.NEXTVAL PRIMARY KEY,
        job_no         VARCHAR2(20) NOT NULL UNIQUE,
        booking_type   VARCHAR2(20) DEFAULT 'Bride',
        client_name    VARCHAR2(100) NOT NULL,
        phone          VARCHAR2(20),
        wedding_date   DATE,
        venue          VARCHAR2(200),
        reference      VARCHAR2(200),
        package_name   VARCHAR2(200),
        pkg_amount     NUMBER(12,2) DEFAULT 0,
        transport      NUMBER(10,2) DEFAULT 0,
        discount       NUMBER(10,2) DEFAULT 0,
        advance_paid   NUMBER(10,2) DEFAULT 0,
        balance_due    NUMBER(12,2) DEFAULT 0,
        status         VARCHAR2(30) DEFAULT 'Active',
        notes          VARCHAR2(1000),
        wa_sent        NUMBER(1)    DEFAULT 0,
        created_by     NUMBER REFERENCES users(id),
        created_at     TIMESTAMP    DEFAULT SYSTIMESTAMP,
        updated_at     TIMESTAMP    DEFAULT SYSTIMESTAMP,
        CONSTRAINT chk_br_type   CHECK (booking_type IN ('Bride','Groom','Sider')),
        CONSTRAINT chk_br_status CHECK (status IN ('Active','Completed','Cancelled'))
    );
    CREATE INDEX idx_bridal_type    ON bridal_bookings(booking_type);
    CREATE INDEX idx_bridal_wdate   ON bridal_bookings(wedding_date);
    CREATE INDEX idx_bridal_balance ON bridal_bookings(balance_due);

    CREATE TABLE bridal_functions (
        id             NUMBER DEFAULT seq_br_funcs.NEXTVAL PRIMARY KEY,
        booking_id     NUMBER NOT NULL REFERENCES bridal_bookings(id) ON DELETE CASCADE,
        function_name  VARCHAR2(100),
        fn_date        DATE,
        fn_time        VARCHAR2(10),
        person_count   NUMBER,
        pkg_detail     VARCHAR2(200),
        artist_id      NUMBER REFERENCES staff(id),
        artist_name    VARCHAR2(100),
        created_at     TIMESTAMP DEFAULT SYSTIMESTAMP
    );
    CREATE INDEX idx_br_funcs_booking ON bridal_functions(booking_id);

-- ============================================================
-- SALARY PAYMENTS
-- ============================================================
CREATE TABLE salary_payments (
    id          NUMBER DEFAULT seq_salary.NEXTVAL PRIMARY KEY,
    staff_id    NUMBER NOT NULL REFERENCES staff(id),
    pay_month   VARCHAR2(7)  NOT NULL,
    base_amount NUMBER(10,2) DEFAULT 0,
    commission  NUMBER(10,2) DEFAULT 0,
    total_paid  NUMBER(10,2) DEFAULT 0,
    paid_date   DATE         DEFAULT SYSDATE,
    notes       VARCHAR2(300),
    created_by  NUMBER REFERENCES users(id),
    created_at  TIMESTAMP    DEFAULT SYSTIMESTAMP
);

-- ============================================================
-- SERVICE CATALOG
-- ============================================================
CREATE TABLE service_catalog (
    id          NUMBER DEFAULT seq_svc_cat.NEXTVAL PRIMARY KEY,
    category    VARCHAR2(50)  NOT NULL,
    name        VARCHAR2(200) NOT NULL,
    base_price  NUMBER(10,2)  DEFAULT 0,
    is_active   NUMBER(1)     DEFAULT 1,
    sort_order  NUMBER        DEFAULT 0,
    created_at  TIMESTAMP     DEFAULT SYSTIMESTAMP
);
CREATE INDEX idx_svc_cat ON service_catalog(category, is_active);

-- ============================================================
-- NOTIFICATIONS
-- ============================================================
CREATE TABLE notifications (
    id          NUMBER DEFAULT seq_notif.NEXTVAL PRIMARY KEY,
    user_id     NUMBER REFERENCES users(id),
    title       VARCHAR2(200),
    message     VARCHAR2(1000),
    type        VARCHAR2(30) DEFAULT 'info',
    is_read     NUMBER(1)    DEFAULT 0,
    created_at  TIMESTAMP    DEFAULT SYSTIMESTAMP
);
CREATE INDEX idx_notif_user ON notifications(user_id, is_read);

-- ============================================================
-- SYSTEM CONFIG
-- ============================================================
CREATE TABLE system_config (
    config_key   VARCHAR2(100) PRIMARY KEY,
    config_value VARCHAR2(2000),
    updated_by   NUMBER REFERENCES users(id),
    updated_at   TIMESTAMP DEFAULT SYSTIMESTAMP
);

-- ============================================================
-- WHATSAPP LOG
-- ============================================================
CREATE TABLE wa_log (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    phone       VARCHAR2(20),
    type        VARCHAR2(30),
    ref_id      NUMBER,
    message     CLOB,
    status      VARCHAR2(20) DEFAULT 'sent',
    sent_at     TIMESTAMP DEFAULT SYSTIMESTAMP
);

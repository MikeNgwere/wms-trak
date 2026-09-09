-- =========================================================
-- WMS-Trak: State Warehouse, Bond & Transit Tracking System
-- PostgreSQL schema (Supabase-compatible)
-- =========================================================

-- ---------- Reference / lookup tables ----------

CREATE TABLE roles (
    role_id     SERIAL PRIMARY KEY,
    role_name   VARCHAR(50) UNIQUE NOT NULL   -- Agent, Officer, Supervisor, Manager
);

CREATE TABLE ports (
    port_code   VARCHAR(10) PRIMARY KEY,       -- ZWFB, ZWCH, ZWBB
    port_name   VARCHAR(100) NOT NULL,
    region      VARCHAR(100)
);

CREATE TABLE warehouses (
    warehouse_id    SERIAL PRIMARY KEY,
    port_code       VARCHAR(10) REFERENCES ports(port_code),
    warehouse_name  VARCHAR(150) NOT NULL,
    warehouse_type  VARCHAR(30) NOT NULL        -- 'state' | 'bonded' | 'transit_shed'
);

-- Encodes Customs & Excise Act bond/transit periods as CONFIG, not hardcoded logic.
-- Update this table if the Act's periods differ by goods class / amendment.
CREATE TABLE bond_rules (
    rule_id         SERIAL PRIMARY KEY,
    entry_type      VARCHAR(10) NOT NULL,        -- RIH, NOS, RIB, RIT
    load_condition  VARCHAR(30),                  -- 'normal','abnormal','transit_shed', NULL if n/a
    allowed_days    INT NOT NULL,
    legal_reference VARCHAR(150),                 -- e.g. 'Customs and Excise Act [Chapter 23:02], s.XX'
    description     TEXT
);

-- ---------- Users & access control ----------

CREATE TABLE users (
    user_id         SERIAL PRIMARY KEY,
    full_name       VARCHAR(150) NOT NULL,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role_id         INT REFERENCES roles(role_id) NOT NULL,
    port_code       VARCHAR(10) REFERENCES ports(port_code), -- NULL for Managers who see all ports
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT now()
);

-- Fine-grained permission matrix so role rights are configurable, not hardcoded in the app
CREATE TABLE permissions (
    permission_id   SERIAL PRIMARY KEY,
    role_id         INT REFERENCES roles(role_id),
    action          VARCHAR(100) NOT NULL   -- e.g. 'create_entry','approve_disposal','view_all_ports'
);

-- ---------- Core tracking ----------

CREATE TABLE entries (
    entry_id            SERIAL PRIMARY KEY,
    entry_number        VARCHAR(50) UNIQUE NOT NULL,
    entry_type          VARCHAR(10) NOT NULL,     -- RIH, NOS, RIB, RIT
    port_code           VARCHAR(10) REFERENCES ports(port_code) NOT NULL,
    warehouse_id        INT REFERENCES warehouses(warehouse_id),
    agent_id            INT REFERENCES users(user_id),
    officer_id          INT REFERENCES users(user_id),
    goods_description   TEXT,
    declared_value      NUMERIC(14,2),
    load_condition      VARCHAR(30),              -- 'normal' | 'abnormal' | NULL
    date_entered         TIMESTAMP NOT NULL,
    bond_due_date        TIMESTAMP,                 -- computed from bond_rules at entry time
    status               VARCHAR(30) NOT NULL DEFAULT 'in_warehouse',
        -- in_warehouse | in_transit | in_bond | acquitted | flagged |
        -- forfeited | seized | ready_for_disposal | sold | auctioned | appropriated
    created_at           TIMESTAMP DEFAULT now(),
    updated_at           TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_entries_status ON entries(status);
CREATE INDEX idx_entries_due_date ON entries(bond_due_date);
CREATE INDEX idx_entries_port ON entries(port_code);

-- Movement legs for RIB / RIT goods travelling between ports/warehouses
CREATE TABLE transit_movements (
    movement_id      SERIAL PRIMARY KEY,
    entry_id         INT REFERENCES entries(entry_id) NOT NULL,
    origin_port      VARCHAR(10) REFERENCES ports(port_code),
    destination_port VARCHAR(10) REFERENCES ports(port_code),
    departure_time   TIMESTAMP,
    expected_arrival TIMESTAMP,
    actual_arrival   TIMESTAMP,
    status           VARCHAR(30) DEFAULT 'departed'   -- departed | arrived | overdue
);

CREATE TABLE payments (
    payment_id       SERIAL PRIMARY KEY,
    entry_id         INT REFERENCES entries(entry_id) NOT NULL,
    duty_amount      NUMERIC(14,2) DEFAULT 0,
    penalty_amount   NUMERIC(14,2) DEFAULT 0,
    rent_amount      NUMERIC(14,2) DEFAULT 0,       -- state warehouse rent (RIH)
    paid_amount      NUMERIC(14,2) DEFAULT 0,
    payment_date     TIMESTAMP,
    receipt_number   VARCHAR(50),
    recorded_by      INT REFERENCES users(user_id)
);

-- NOS-specific disposal workflow (seizure -> appeal window -> disposal)
CREATE TABLE seizures (
    seizure_id            SERIAL PRIMARY KEY,
    entry_id              INT REFERENCES entries(entry_id) UNIQUE NOT NULL,
    seizure_date           TIMESTAMP NOT NULL,
    appeal_status           VARCHAR(30) DEFAULT 'none',   -- none | pending | rejected | upheld
    appeal_deadline         TIMESTAMP,
    disposal_type            VARCHAR(30),                  -- offhand_sale | appropriation | auction
    ready_for_disposal       BOOLEAN DEFAULT FALSE,
    manager_approval_by      INT REFERENCES users(user_id),
    manager_approval_date    TIMESTAMP,
    disposal_date             TIMESTAMP
);

-- Append-only audit trail — survives even after an entry is archived/removed from the warehouse
CREATE TABLE audit_log (
    audit_id         BIGSERIAL PRIMARY KEY,
    entry_id         INT,               -- intentionally not a hard FK so history persists after archival
    entry_number     VARCHAR(50),
    action           VARCHAR(100) NOT NULL,   -- e.g. 'STATUS_CHANGE','PAYMENT_RECORDED','DISPOSAL_APPROVED'
    actor_user_id    INT REFERENCES users(user_id),
    actor_role       VARCHAR(50),
    before_state     JSONB,
    after_state      JSONB,
    notes            TEXT,
    action_timestamp TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_audit_entry_number ON audit_log(entry_number);
CREATE INDEX idx_audit_timestamp ON audit_log(action_timestamp);
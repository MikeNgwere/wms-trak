-- =========================================================
-- Migration 004: Warehouse/pound capacity, full RIH & NOS
-- field capture, chat-style messages.
-- =========================================================

-- Warehouse capacity + full/not-full flag
ALTER TABLE warehouses
    ADD COLUMN capacity INT DEFAULT 150,
    ADD COLUMN is_full BOOLEAN DEFAULT FALSE,
    ADD COLUMN marked_full_by INT REFERENCES users(user_id),
    ADD COLUMN marked_full_at TIMESTAMP;

-- Seed ZWFB Warehouses A-E (goods, capacity 150) and Pounds A-E (vehicles, capacity 15)
INSERT INTO warehouses (port_code, warehouse_name, warehouse_type, capacity) VALUES
('ZWFB', 'Warehouse A', 'goods', 150),
('ZWFB', 'Warehouse B', 'goods', 150),
('ZWFB', 'Warehouse C', 'goods', 150),
('ZWFB', 'Warehouse D', 'goods', 150),
('ZWFB', 'Warehouse E', 'goods', 150),
('ZWFB', 'Pound A', 'vehicle_pound', 15),
('ZWFB', 'Pound B', 'vehicle_pound', 15),
('ZWFB', 'Pound C', 'vehicle_pound', 15),
('ZWFB', 'Pound D', 'vehicle_pound', 15),
('ZWFB', 'Pound E', 'vehicle_pound', 15);

-- Shared importer/owner + registry fields on entries
ALTER TABLE entries
    ADD COLUMN warehouse_registry_number VARCHAR(50),
    ADD COLUMN importer_name        VARCHAR(150),
    ADD COLUMN importer_address     TEXT,
    ADD COLUMN importer_contact     VARCHAR(50),
    ADD COLUMN importer_id_number   VARCHAR(50),
    ADD COLUMN importer_bpn_tin     VARCHAR(50),
    ADD COLUMN is_vehicle           BOOLEAN DEFAULT FALSE;

-- RIH-specific fields (Detention & Issue details)
CREATE TABLE rih_details (
    entry_id            INT PRIMARY KEY REFERENCES entries(entry_id),
    rih_number           VARCHAR(50),
    reason_category        VARCHAR(30),  -- failure_to_pay_duty | missing_permit | pending_valuation | other
    reason_narrative         TEXT,
    act_clause                  VARCHAR(150),
    issuing_officer_id             INT REFERENCES users(user_id),
    importer_ack_signed               BOOLEAN DEFAULT FALSE,
    importer_ack_date                    TIMESTAMP
);

-- NOS-specific fields (Seizure & Legal Contravention details)
CREATE TABLE nos_details (
    entry_id                INT PRIMARY KEY REFERENCES entries(entry_id),
    nos_number                VARCHAR(50),
    seizing_officer_id           INT REFERENCES users(user_id),
    seizing_officer_ec_number       VARCHAR(30),
    offence_committed                  TEXT,
    act_section_breached                  VARCHAR(150),
    marks_and_numbers                        TEXT,
    statutory_warning_acknowledged              BOOLEAN DEFAULT FALSE,
    offender_signature_received                    BOOLEAN DEFAULT FALSE
);

-- Vehicle specifics — applies to either RIH or NOS when is_vehicle = TRUE
CREATE TABLE vehicle_details (
    entry_id            INT PRIMARY KEY REFERENCES entries(entry_id),
    registration_number   VARCHAR(30),
    chassis_number           VARCHAR(50),
    engine_number               VARCHAR(50),
    make                            VARCHAR(50),
    model                              VARCHAR(50),
    colour                                VARCHAR(30),
    year_of_manufacture                     INT
);

-- Goods description extras: marks/quantity/weight (shared, useful for both types)
ALTER TABLE entries
    ADD COLUMN quantity_units   VARCHAR(50),
    ADD COLUMN gross_weight     NUMERIC(12,2),
    ADD COLUMN net_weight       NUMERIC(12,2);

-- Chat-style messages: human-composed communications, separate from
-- automated notifications. Sender is always a user; recipient can be
-- a specific user, a role (broadcast), or everyone (ZIMRA-wide announcement).
CREATE TABLE messages (
    message_id       BIGSERIAL PRIMARY KEY,
    sender_user_id     INT REFERENCES users(user_id) NOT NULL,
    recipient_scope       VARCHAR(20) NOT NULL,  -- 'user' | 'role' | 'all'
    recipient_user_id        INT REFERENCES users(user_id),
    recipient_role              VARCHAR(50),
    recipient_port                  VARCHAR(10) REFERENCES ports(port_code),
    subject                            VARCHAR(200),
    body                                  TEXT NOT NULL,
    created_at                              TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_messages_recipient_user ON messages(recipient_user_id);
CREATE INDEX idx_messages_recipient_role_port ON messages(recipient_role, recipient_port);
CREATE INDEX idx_messages_created ON messages(created_at);
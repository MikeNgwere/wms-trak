-- =========================================================
-- Migration 007: Four distinct action types (Release to Owner,
-- Forfeiture, Destruction, E-Auction), each with request-time and
-- finalization-time detail capture. Manager approval now grants
-- permission only — the Officer's finalization step is what actually
-- effects the action. Also: entry-form improvements (drop warehouse
-- registry number, add rent/day, exchange rate, expiry date, weight
-- unit).
-- =========================================================

-- Entry form improvements
ALTER TABLE entries
    DROP COLUMN IF EXISTS warehouse_registry_number,
    ADD COLUMN rent_charge_per_day NUMERIC(10,2) DEFAULT 0,
    ADD COLUMN exchange_rate_zwg_usd NUMERIC(12,4),
    ADD COLUMN expiry_date DATE,
    ADD COLUMN weight_unit VARCHAR(10) DEFAULT 'kg';

-- ---------------- Release to Owner ----------------
CREATE TABLE release_to_owner_details (
    request_id          INT PRIMARY KEY REFERENCES action_requests(request_id),
    duty_paid              NUMERIC(12,2),
    additional_duty            NUMERIC(12,2),
    rent_days_calculated           INT,
    rent_calculated                     NUMERIC(12,2),
    rent_paid                              NUMERIC(12,2),
    receipt_number                            VARCHAR(50),
    y_number                                     VARCHAR(50),
    clearance_details                               TEXT,
    finalized_by                                       INT REFERENCES users(user_id),
    finalized_at                                          TIMESTAMP
);

-- ---------------- Forfeiture (appropriation to the State) ----------------
CREATE TABLE forfeiture_details (
    request_id                   INT PRIMARY KEY REFERENCES action_requests(request_id),
    -- captured at request time
    ministry_name                   VARCHAR(150),
    request_letter_reference           TEXT,
    -- captured at finalization
    representative_name                   VARCHAR(150),
    representative_id_number                 VARCHAR(50),
    representative_occupation                   VARCHAR(100),
    goods_or_vehicle_finalization_details          TEXT,
    finalized_by                                      INT REFERENCES users(user_id),
    finalized_at                                         TIMESTAMP
);

-- ---------------- Destruction ----------------
CREATE TABLE destruction_details (
    request_id                       INT PRIMARY KEY REFERENCES action_requests(request_id),
    -- captured at request time
    port_health_officer_name            VARCHAR(150),
    port_health_approval_reference          VARCHAR(100),
    reason_for_destruction                     TEXT,
    -- captured at finalization
    destruction_date                              DATE,
    destruction_place                                VARCHAR(150),
    stakeholders_present                                TEXT,  -- e.g. Police rep, Port Health rep, Army rep, other officers
    finalized_by                                           INT REFERENCES users(user_id),
    finalized_at                                              TIMESTAMP
);

-- ---------------- E-Auction ----------------
CREATE TABLE eauction_details (
    request_id             INT PRIMARY KEY REFERENCES action_requests(request_id),
    revenue_collected         NUMERIC(12,2),
    buyer_details                 TEXT,
    receipt_number                   VARCHAR(50),
    finalized_by                        INT REFERENCES users(user_id),
    finalized_at                           TIMESTAMP
);
-- =========================================================
-- Migration 012: Dual-currency revenue (USD and ZWG), recorded
-- as actually paid by the client — no conversion between them.
-- =========================================================
ALTER TABLE release_to_owner_details
    ADD COLUMN duty_paid_usd NUMERIC(12,2) DEFAULT 0,
    ADD COLUMN duty_paid_zwg NUMERIC(14,2) DEFAULT 0,
    ADD COLUMN additional_duty_usd NUMERIC(12,2) DEFAULT 0,
    ADD COLUMN additional_duty_zwg NUMERIC(14,2) DEFAULT 0,
    ADD COLUMN rent_paid_usd NUMERIC(12,2) DEFAULT 0,
    ADD COLUMN rent_paid_zwg NUMERIC(14,2) DEFAULT 0;

ALTER TABLE eauction_details
    ADD COLUMN revenue_collected_usd NUMERIC(12,2) DEFAULT 0,
    ADD COLUMN revenue_collected_zwg NUMERIC(14,2) DEFAULT 0;

ALTER TABLE action_requests
    ADD COLUMN amount_collected_usd NUMERIC(14,2),
    ADD COLUMN amount_collected_zwg NUMERIC(16,2);

ALTER TABLE payments
    ADD COLUMN paid_amount_usd NUMERIC(14,2) DEFAULT 0,
    ADD COLUMN paid_amount_zwg NUMERIC(16,2) DEFAULT 0;
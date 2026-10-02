-- =========================================================
-- Migration 013: One-time backfill — historical revenue recorded
-- before the dual-currency migration was all in USD, so copy it
-- into the new amount_collected_usd / paid_amount_usd columns.
-- =========================================================
UPDATE action_requests
SET amount_collected_usd = amount_collected
WHERE amount_collected IS NOT NULL
  AND amount_collected_usd IS NULL;

UPDATE payments
SET paid_amount_usd = paid_amount
WHERE paid_amount IS NOT NULL
  AND paid_amount_usd IS NULL;
-- =========================================================
-- Migration 011: Requester sets their own password at profile
-- request time (stored hashed), since no email delivery exists
-- to communicate an Admin-set temporary password.
-- =========================================================
ALTER TABLE profile_requests
    ADD COLUMN password_hash VARCHAR(255);
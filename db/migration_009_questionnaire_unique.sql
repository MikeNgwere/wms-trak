-- =========================================================
-- Migration 009: One questionnaire response per person (editable).
-- =========================================================
ALTER TABLE questionnaire_responses
    ADD CONSTRAINT uq_questionnaire_one_per_user UNIQUE (submitted_by_user_id);
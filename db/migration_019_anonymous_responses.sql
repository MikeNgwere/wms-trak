-- Anonymous questionnaire responses: stored as "Anonymous 1", "Anonymous 2", ... with no email.
ALTER TABLE questionnaire_responses
    ADD COLUMN IF NOT EXISTS is_anonymous BOOLEAN NOT NULL DEFAULT FALSE;
CREATE SEQUENCE IF NOT EXISTS questionnaire_anon_seq START 1;

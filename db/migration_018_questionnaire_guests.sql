-- Guest questionnaire: one response per ZIMRA email.
ALTER TABLE questionnaire_responses
    ADD COLUMN IF NOT EXISTS respondent_email VARCHAR(254);
ALTER TABLE questionnaire_responses
    ALTER COLUMN submitted_by_user_id DROP NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_questionnaire_email
    ON questionnaire_responses (LOWER(respondent_email))
    WHERE respondent_email IS NOT NULL;

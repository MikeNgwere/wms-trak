-- =========================================================
-- Migration 008: Pilot-test questionnaire responses (15 Likert
-- items across 3 research questions).
-- =========================================================
CREATE TABLE questionnaire_responses (
    response_id           SERIAL PRIMARY KEY,
    respondent_name          VARCHAR(150),
    respondent_station          VARCHAR(100),
    respondent_role                 VARCHAR(100),
    submitted_by_user_id                INT REFERENCES users(user_id),
    q1 SMALLINT NOT NULL, q2 SMALLINT NOT NULL, q3 SMALLINT NOT NULL,
    q4 SMALLINT NOT NULL, q5 SMALLINT NOT NULL, q6 SMALLINT NOT NULL,
    q7 SMALLINT NOT NULL, q8 SMALLINT NOT NULL, q9 SMALLINT NOT NULL,
    q10 SMALLINT NOT NULL, q11 SMALLINT NOT NULL, q12 SMALLINT NOT NULL,
    q13 SMALLINT NOT NULL, q14 SMALLINT NOT NULL, q15 SMALLINT NOT NULL,
    comments                                                  TEXT,
    submitted_at                                                 TIMESTAMP DEFAULT now()
);
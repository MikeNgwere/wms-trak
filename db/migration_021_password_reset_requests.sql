-- Concept: forgotten-password requests that an Admin handles (no automatic reset).
CREATE TABLE IF NOT EXISTS password_reset_requests (
    request_id   SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    email        VARCHAR(200) NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending',   -- pending | link_sent | dismissed
    requested_at TIMESTAMP    NOT NULL DEFAULT now(),
    handled_by   INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    handled_at   TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pw_reset_one_pending
    ON password_reset_requests (user_id) WHERE status = 'pending';

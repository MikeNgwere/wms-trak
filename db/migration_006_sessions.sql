-- =========================================================
-- Migration 006: Persistent login sessions (survive page refresh).
-- =========================================================
CREATE TABLE sessions (
    session_token   VARCHAR(64) PRIMARY KEY,
    user_id          INT REFERENCES users(user_id) NOT NULL,
    created_at          TIMESTAMP DEFAULT now(),
    expires_at             TIMESTAMP NOT NULL
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
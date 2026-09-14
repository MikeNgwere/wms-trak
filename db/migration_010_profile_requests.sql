-- =========================================================
-- Migration 010: Self-service profile requests (Admin-approved)
-- and password reset support.
-- =========================================================
CREATE TABLE profile_requests (
    request_id           SERIAL PRIMARY KEY,
    full_name               VARCHAR(150) NOT NULL,
    email                      VARCHAR(150) NOT NULL,
    phone_number                  VARCHAR(20),
    requested_role                   VARCHAR(50),
    requested_port                      VARCHAR(10) REFERENCES ports(port_code),
    reason                                  TEXT,
    status                                     VARCHAR(20) DEFAULT 'pending',  -- pending | approved | rejected
    reviewed_by                                   INT REFERENCES users(user_id),
    reviewed_at                                      TIMESTAMP,
    review_notes                                        TEXT,
    created_at                                             TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_profile_requests_status ON profile_requests(status);
CREATE INDEX idx_profile_requests_email ON profile_requests(email);
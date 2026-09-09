-- =========================================================
-- Migration 001: Entry approval workflow, extensions,
-- acquittals, notifications, B/E tracking
-- =========================================================

-- Extend entries with B/E tracking + approval workflow
ALTER TABLE entries
    ADD COLUMN be_number        VARCHAR(50),
    ADD COLUMN running_number   VARCHAR(50),
    ADD COLUMN workflow_status  VARCHAR(30) NOT NULL DEFAULT 'draft',
        -- draft | pending_assessment | pending_approval | approved | rejected
    ADD COLUMN initiated_by     INT REFERENCES users(user_id),
    ADD COLUMN assessed_by      INT REFERENCES users(user_id),
    ADD COLUMN assessed_at      TIMESTAMP,
    ADD COLUMN approved_by      INT REFERENCES users(user_id),
    ADD COLUMN approved_at      TIMESTAMP,
    ADD COLUMN rejection_reason TEXT;

CREATE INDEX idx_entries_be_number ON entries(be_number);
CREATE INDEX idx_entries_workflow_status ON entries(workflow_status);

-- Bond/transit period extension requests
CREATE TABLE extension_requests (
    request_id          SERIAL PRIMARY KEY,
    entry_id             INT REFERENCES entries(entry_id) NOT NULL,
    requested_by         INT REFERENCES users(user_id) NOT NULL,  -- Agent
    requested_days       INT NOT NULL,
    reason               TEXT,
    officer_status       VARCHAR(30) DEFAULT 'pending',   -- pending | recommended | declined
    officer_reviewed_by  INT REFERENCES users(user_id),
    officer_reviewed_at  TIMESTAMP,
    officer_notes        TEXT,
    manager_status       VARCHAR(30) DEFAULT 'pending',   -- pending | approved | rejected
    manager_decided_by   INT REFERENCES users(user_id),
    manager_decided_at   TIMESTAMP,
    manager_notes        TEXT,
    new_due_date         TIMESTAMP,
    created_at           TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_extension_entry ON extension_requests(entry_id);

-- Port-to-port acquittal communication (RIB/RIT)
CREATE TABLE acquittals (
    acquittal_id       SERIAL PRIMARY KEY,
    entry_id            INT REFERENCES entries(entry_id) NOT NULL,
    movement_id         INT REFERENCES transit_movements(movement_id),
    initiating_port     VARCHAR(10) REFERENCES ports(port_code) NOT NULL,
    receiving_port      VARCHAR(10) REFERENCES ports(port_code) NOT NULL,
    receiving_officer_id INT REFERENCES users(user_id),
    received_date        TIMESTAMP,
    acquittal_details     TEXT,
    status                VARCHAR(30) DEFAULT 'pending_confirmation',
        -- pending_confirmation | confirmed | disputed
    confirmed_by           INT REFERENCES users(user_id),  -- officer at initiating port
    confirmed_date          TIMESTAMP,
    created_at               TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_acquittals_entry ON acquittals(entry_id);
CREATE INDEX idx_acquittals_status ON acquittals(status);

-- Notifications (acquittals, flags, extensions, approvals)
CREATE TABLE notifications (
    notification_id    BIGSERIAL PRIMARY KEY,
    recipient_user_id   INT REFERENCES users(user_id),   -- specific user, nullable
    recipient_role       VARCHAR(50),                       -- or broadcast to a role, nullable
    recipient_port        VARCHAR(10) REFERENCES ports(port_code), -- or broadcast to a port, nullable
    notif_type             VARCHAR(50) NOT NULL,
        -- acquittal_pending | acquittal_confirmed | entry_flagged |
        -- extension_requested | extension_decided | entry_pending_assessment |
        -- entry_pending_approval | entry_approved | entry_rejected
    entry_id                 INT,
    message                   TEXT NOT NULL,
    is_read                     BOOLEAN DEFAULT FALSE,
    created_at                   TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_notif_recipient_user ON notifications(recipient_user_id);
CREATE INDEX idx_notif_recipient_role_port ON notifications(recipient_role, recipient_port);
CREATE INDEX idx_notif_unread ON notifications(is_read);

-- New permission actions for the approval/extension/acquittal workflow
INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('request_extension')
) AS a(action) WHERE role_name = 'Agent';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('assess_entry'), ('review_extension'), ('send_acquittal'), ('confirm_acquittal')
) AS a(action) WHERE role_name = 'Officer';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('view_rih_list'), ('view_seizures_list')
) AS a(action) WHERE role_name = 'Supervisor';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('approve_entry'), ('reject_entry'), ('approve_extension'), ('reject_extension'),
    ('view_rih_list'), ('view_seizures_list')
) AS a(action) WHERE role_name = 'Manager';
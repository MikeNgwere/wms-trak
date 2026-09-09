-- =========================================================
-- Migration 003: Simplify scope to RIH & NOS only.
-- Drops RIB/RIT infrastructure, removes agent-initiation and
-- extension workflow, adds two-stage (Supervisor -> Manager)
-- disposal/release approval.
-- =========================================================

-- Drop RIB/RIT-specific tables entirely
DROP TABLE IF EXISTS acquittals CASCADE;
DROP TABLE IF EXISTS transit_movements CASCADE;
DROP TABLE IF EXISTS extension_requests CASCADE;

-- Remove RIB/RIT/bonded-warehouse bond rules (RIH stays)
DELETE FROM bond_rules WHERE entry_type IN ('RIB', 'RIT', 'BONDED_WHS');

-- Simplify entries: drop agent-workflow and transit-specific columns
ALTER TABLE entries
    DROP COLUMN IF EXISTS be_number,
    DROP COLUMN IF EXISTS running_number,
    DROP COLUMN IF EXISTS load_condition,
    DROP COLUMN IF EXISTS workflow_status,
    DROP COLUMN IF EXISTS initiated_by,
    DROP COLUMN IF EXISTS assessed_by,
    DROP COLUMN IF EXISTS assessed_at,
    DROP COLUMN IF EXISTS approved_by,
    DROP COLUMN IF EXISTS approved_at,
    DROP COLUMN IF EXISTS rejection_reason,
    ADD COLUMN captured_by INT REFERENCES users(user_id);

-- Seizures: add Supervisor stage ahead of Manager's final approval
ALTER TABLE seizures
    ADD COLUMN supervisor_approval_by INT REFERENCES users(user_id),
    ADD COLUMN supervisor_approval_date TIMESTAMP;

-- Unified action-request table: covers both RIH release (after payment)
-- and disposal (offhand sale / appropriation / auction) for RIH or NOS.
CREATE TABLE action_requests (
    request_id           SERIAL PRIMARY KEY,
    entry_id              INT REFERENCES entries(entry_id) NOT NULL,
    action_type            VARCHAR(20) NOT NULL,  -- 'release' | 'disposal'
    disposal_method          VARCHAR(30),           -- offhand_sale | appropriation | auction (disposal only)
    requested_by               INT REFERENCES users(user_id) NOT NULL,  -- Officer
    request_notes                TEXT,
    supervisor_status              VARCHAR(30) DEFAULT 'pending',  -- pending | approved | rejected
    supervisor_by                    INT REFERENCES users(user_id),
    supervisor_at                      TIMESTAMP,
    supervisor_notes                     TEXT,
    manager_status                         VARCHAR(30) DEFAULT 'pending',  -- pending | approved | rejected
    manager_by                                INT REFERENCES users(user_id),
    manager_at                                   TIMESTAMP,
    manager_notes                                   TEXT,
    effected                                          BOOLEAN DEFAULT FALSE,
    effected_at                                          TIMESTAMP,
    created_at                                              TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_action_requests_entry ON action_requests(entry_id);
CREATE INDEX idx_action_requests_supervisor_status ON action_requests(supervisor_status);
CREATE INDEX idx_action_requests_manager_status ON action_requests(manager_status);

-- Clean up permissions tied to removed workflows
DELETE FROM permissions WHERE action IN (
    'request_extension', 'review_extension', 'approve_extension', 'reject_extension',
    'send_acquittal', 'confirm_acquittal', 'assess_entry', 'approve_entry', 'reject_entry',
    'create_entry', 'upload_nos_rih_book', 'view_own_entries'
);

-- New permissions for the simplified workflow
INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('capture_entry'), ('request_disposal_or_release')
) AS a(action) WHERE role_name = 'Officer';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('review_disposal_or_release'), ('view_rih_list'), ('view_seizures_list')
) AS a(action) WHERE role_name = 'Supervisor';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('approve_disposal_or_release'), ('view_rih_list'), ('view_seizures_list')
) AS a(action) WHERE role_name = 'Manager';
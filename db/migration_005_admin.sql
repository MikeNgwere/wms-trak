-- =========================================================
-- Migration 005: Admin/IT role — user management, audit,
-- message moderation, entry correction, and revenue tracking.
-- =========================================================

-- New role
INSERT INTO roles (role_name) VALUES ('Admin')
ON CONFLICT (role_name) DO NOTHING;

-- Track amount actually collected on a release (for revenue statistics)
ALTER TABLE action_requests
    ADD COLUMN amount_collected NUMERIC(14,2);

-- Track edits to entries for audit purposes (who corrected what, when)
ALTER TABLE entries
    ADD COLUMN last_edited_by INT REFERENCES users(user_id),
    ADD COLUMN last_edited_at TIMESTAMP;

-- Admin permissions: full user management, audit, message moderation,
-- entry correction, statistics, plus the same warehouse/seizure
-- visibility Manager already has.
INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('manage_users'), ('edit_entry'), ('delete_message'),
    ('view_audit'), ('view_statistics'), ('view_rih_list'),
    ('view_seizures_list'), ('view_all_ports')
) AS a(action) WHERE role_name = 'Admin';
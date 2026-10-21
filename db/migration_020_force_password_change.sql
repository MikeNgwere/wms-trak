-- Every user must replace their password at next sign-in.
ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE users SET must_change_password = TRUE;

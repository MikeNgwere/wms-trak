"""
Authentication, role-based access control, persistent login sessions,
ZIMRA-email/password validation, and self-service profile requests
(Admin-approved before an account becomes active).

Since this app has no email-delivery capability, the requester sets
their own password at request time (stored hashed) — Admin approval
simply activates the account with that password already in place.
"""
import re
import secrets
from datetime import datetime, timedelta

import bcrypt

from app.db import fetch_one, fetch_all, execute

SESSION_LIFETIME_DAYS = 7
ZIMRA_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@zimra\.co\.zw$", re.IGNORECASE)
PASSWORD_RE = re.compile(r"^(?=.*[0-9])(?=.*[A-Z])(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]).{8,}$")


def is_valid_zimra_email(email: str) -> bool:
    return bool(ZIMRA_EMAIL_RE.match((email or "").strip()))


def is_strong_password(password: str) -> bool:
    """At least 8 characters, one number, one uppercase letter, one symbol."""
    return bool(PASSWORD_RE.match(password or ""))


def password_requirements_text() -> str:
    return "Password must be at least 8 characters and include a number, an uppercase letter, and a symbol."


# ---------------- Core login ----------------

def verify_login(username: str, password: str):
    user = fetch_one(
        """
        SELECT u.user_id, u.full_name, u.username, u.password_hash,
               r.role_name, u.port_code, u.is_active, u.phone_number
        FROM users u
        JOIN roles r ON r.role_id = u.role_id
        WHERE u.username = %s
        """,
        (username,),
    )
    if not user or not user["is_active"]:
        return None
    if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None


def get_permissions(role_name: str) -> set:
    rows = fetch_all(
        """
        SELECT p.action FROM permissions p
        JOIN roles r ON r.role_id = p.role_id
        WHERE r.role_name = %s
        """,
        (role_name,),
    )
    return {row["action"] for row in rows}


def has_permission(role_name: str, action: str) -> bool:
    return action in get_permissions(role_name)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ---------------- Persistent sessions ----------------

def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    expires_at = datetime.now() + timedelta(days=SESSION_LIFETIME_DAYS)
    execute(
        "INSERT INTO sessions (session_token, user_id, expires_at) VALUES (%s, %s, %s)",
        (token, user_id, expires_at),
    )
    return token


def get_user_by_session(token: str):
    if not token:
        return None
    row = fetch_one(
        """
        SELECT u.user_id, u.full_name, u.username, r.role_name,
               u.port_code, u.is_active, u.phone_number
        FROM sessions s
        JOIN users u ON u.user_id = s.user_id
        JOIN roles r ON r.role_id = u.role_id
        WHERE s.session_token = %s AND s.expires_at > now()
        """,
        (token,),
    )
    if not row or not row["is_active"]:
        return None
    return row


def delete_session(token: str):
    if token:
        execute("DELETE FROM sessions WHERE session_token = %s", (token,))


# ---------------- Password reset (in-app, no email delivery configured) ----------------

def find_active_user_by_email(email: str):
    """Used by the Forgot Password flow to verify the account exists before allowing a reset."""
    return fetch_one(
        "SELECT user_id, full_name, username FROM users WHERE username = %s AND is_active = TRUE",
        (email,),
    )


def reset_password_self_service(user_id: int, new_plain_password: str):
    pw_hash = hash_password(new_plain_password)
    execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (pw_hash, user_id))


# ---------------- Self-service profile requests (Admin-approved) ----------------

def submit_profile_request(full_name: str, email: str, phone_number: str,
                            requested_role: str, requested_port: str | None,
                            reason: str, plain_password: str) -> int:
    """
    The requester sets their own password here (stored hashed), since
    there is no email-delivery mechanism to communicate an
    Admin-assigned temporary password after approval.
    """
    if not is_valid_zimra_email(email):
        raise ValueError("Email must be a valid @zimra.co.zw address.")
    if not is_strong_password(plain_password):
        raise ValueError(password_requirements_text())
    existing_user = fetch_one("SELECT user_id FROM users WHERE username = %s", (email,))
    if existing_user:
        raise ValueError("An account with this email already exists.")
    existing_request = fetch_one(
        "SELECT request_id FROM profile_requests WHERE email = %s AND status = 'pending'", (email,)
    )
    if existing_request:
        raise ValueError("A pending profile request for this email already exists.")

    pw_hash = hash_password(plain_password)
    row = fetch_one(
        """
        INSERT INTO profile_requests (full_name, email, phone_number, requested_role, requested_port, reason, password_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING request_id
        """,
        (full_name, email, phone_number, requested_role, requested_port, reason, pw_hash),
    )
    return row["request_id"]


def pending_profile_requests():
    return fetch_all(
        "SELECT * FROM profile_requests WHERE status = 'pending' ORDER BY created_at"
    )


def approve_profile_request(request_id: int, admin_id: int, role_id: int, port_code: str | None,
                             notes: str = "") -> int:
    """Uses the password the requester already set at submission time."""
    req = fetch_one("SELECT * FROM profile_requests WHERE request_id = %s", (request_id,))
    if not req:
        raise ValueError("Request not found")
    if not req["password_hash"]:
        raise ValueError("This request has no password on file and cannot be approved.")

    user_row = fetch_one(
        """
        INSERT INTO users (full_name, username, password_hash, role_id, port_code, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING user_id
        """,
        (req["full_name"], req["email"], req["password_hash"], role_id, port_code, req["phone_number"]),
    )
    execute(
        """
        UPDATE profile_requests
        SET status = 'approved', reviewed_by = %s, reviewed_at = now(), review_notes = %s
        WHERE request_id = %s
        """,
        (admin_id, notes, request_id),
    )
    return user_row["user_id"]


def reject_profile_request(request_id: int, admin_id: int, notes: str = ""):
    execute(
        """
        UPDATE profile_requests
        SET status = 'rejected', reviewed_by = %s, reviewed_at = now(), review_notes = %s
        WHERE request_id = %s
        """,
        (admin_id, notes, request_id),
    )
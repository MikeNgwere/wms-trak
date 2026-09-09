"""
Authentication, role-based access control, and persistent login
sessions (so a page refresh doesn't log the user out).
"""
import secrets
from datetime import datetime, timedelta

import bcrypt

from app.db import fetch_one, fetch_all, execute

SESSION_LIFETIME_DAYS = 7


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
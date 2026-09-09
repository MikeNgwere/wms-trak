"""
Chat-style messages: human-composed communications between users —
announcements, updates, general ZIMRA communication. Distinct from
app/notifications.py, which handles automated system events
(acquittal updates, approvals, etc).
"""
from app.db import fetch_all, execute


def send_message(sender_id: int, body: str, subject: str | None = None,
                  recipient_scope: str = "all", recipient_user_id: int | None = None,
                  recipient_role: str | None = None, recipient_port: str | None = None) -> None:
    """
    recipient_scope: 'user' (direct to one person), 'role' (broadcast to a
    role, optionally scoped to a port), or 'all' (ZIMRA-wide announcement).
    """
    if recipient_scope not in ("user", "role", "all"):
        raise ValueError("recipient_scope must be 'user', 'role', or 'all'")

    execute(
        """
        INSERT INTO messages (
            sender_user_id, recipient_scope, recipient_user_id,
            recipient_role, recipient_port, subject, body
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (sender_id, recipient_scope, recipient_user_id, recipient_role, recipient_port, subject, body),
    )


def get_messages_for(user_id: int, role_name: str, port_code: str | None, limit: int = 100):
    """
    All messages visible to this user: direct messages to them, role
    broadcasts (matching their role and, if scoped, their port), and
    ZIMRA-wide announcements. Newest first.
    """
    return fetch_all(
        """
        SELECT m.message_id, m.subject, m.body, m.created_at, m.recipient_scope,
               u.full_name AS sender_name, u.role_name AS sender_role
        FROM messages m
        JOIN (SELECT users.user_id, users.full_name, roles.role_name
              FROM users JOIN roles ON roles.role_id = users.role_id) u
              ON u.user_id = m.sender_user_id
        WHERE m.recipient_scope = 'all'
           OR (m.recipient_scope = 'user' AND m.recipient_user_id = %s)
           OR (m.recipient_scope = 'role' AND m.recipient_role = %s
               AND (m.recipient_port IS NULL OR m.recipient_port = %s))
        ORDER BY m.created_at DESC
        LIMIT %s
        """,
        (user_id, role_name, port_code, limit),
    )
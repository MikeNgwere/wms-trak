"""
Notifications: acquittal updates, flagged consignments, extension
decisions, entry approvals — surfaced in the Notifications tab.

A notification can target a specific user, or broadcast to everyone
with a given role (optionally scoped to a port) — e.g. "all Officers
at ZWFB" when an entry needs assessment.
"""
from app.db import fetch_all, execute


def notify_user(user_id: int, notif_type: str, message: str, entry_id: int | None = None):
    execute(
        """
        INSERT INTO notifications (recipient_user_id, notif_type, entry_id, message)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, notif_type, entry_id, message),
    )


def notify_role(role_name: str, notif_type: str, message: str,
                 entry_id: int | None = None, port_code: str | None = None):
    execute(
        """
        INSERT INTO notifications (recipient_role, recipient_port, notif_type, entry_id, message)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (role_name, port_code, notif_type, entry_id, message),
    )


def get_notifications_for(user_id: int, role_name: str, port_code: str | None, unread_only: bool = False):
    query = """
        SELECT notification_id, notif_type, entry_id, message, is_read, created_at
        FROM notifications
        WHERE recipient_user_id = %s
           OR (recipient_role = %s AND (recipient_port IS NULL OR recipient_port = %s))
    """
    if unread_only:
        query += " AND is_read = FALSE"
    query += " ORDER BY created_at DESC LIMIT 100"
    return fetch_all(query, (user_id, role_name, port_code))


def mark_read(notification_id: int):
    execute("UPDATE notifications SET is_read = TRUE WHERE notification_id = %s", (notification_id,))


def unread_count(user_id: int, role_name: str, port_code: str | None) -> int:
    rows = get_notifications_for(user_id, role_name, port_code, unread_only=True)
    return len(rows)
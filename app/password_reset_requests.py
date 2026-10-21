"""
Forgot-password CONCEPT: the user's email is confirmed, a request is created for the
Admin, and the user is told to expect a reset link from the Admin. No password is changed
here and no email is sent in this prototype; the Admin tab records that a link was "sent".
"""
from app.db import fetch_all, fetch_one, execute
from app.auth import find_active_user_by_email

STATUS_LABEL = {"pending": "Pending", "link_sent": "Link sent (concept)", "dismissed": "Dismissed"}


def create_request(email: str) -> bool:
    """Create one pending request for an active account. Returns True if the account exists.
    The caller must show the same message either way, so nobody can test which emails exist."""
    user = find_active_user_by_email(email)
    if not user:
        return False
    execute(
        """INSERT INTO password_reset_requests (user_id, email)
           VALUES (%s, %s)
           ON CONFLICT (user_id) WHERE status = 'pending' DO NOTHING""",
        (user["user_id"], email.strip().lower()),
    )
    return True


def pending_count() -> int:
    try:
        row = fetch_one("SELECT COUNT(*) AS n FROM password_reset_requests WHERE status = 'pending'")
        return int(row["n"]) if row else 0
    except Exception:
        return 0


def list_requests(status=None, limit=50):
    sql = """SELECT r.request_id, r.user_id, r.email, r.status, r.requested_at, r.handled_at,
                    u.full_name, u.username, u.port_code,
                    h.full_name AS handled_by_name
             FROM password_reset_requests r
             JOIN users u ON u.user_id = r.user_id
             LEFT JOIN users h ON h.user_id = r.handled_by"""
    params = []
    if status:
        sql += " WHERE r.status = %s"
        params.append(status)
    sql += " ORDER BY r.requested_at DESC LIMIT %s"
    params.append(limit)
    return fetch_all(sql, tuple(params))


def mark_handled(request_id: int, admin_id: int, status: str) -> None:
    execute(
        """UPDATE password_reset_requests
           SET status = %s, handled_by = %s, handled_at = now()
           WHERE request_id = %s AND status = 'pending'""",
        (status, admin_id, request_id),
    )

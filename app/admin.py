"""
Admin/IT logic: user management, entry correction, audit trail
viewing, message moderation, and system statistics.
"""
from app.db import fetch_all, fetch_one, execute
from app.auth import hash_password


# ---------------- User management ----------------

def list_users():
    return fetch_all(
        """
        SELECT u.user_id, u.full_name, u.username, r.role_name,
               u.port_code, u.is_active, u.phone_number, u.created_at
        FROM users u JOIN roles r ON r.role_id = u.role_id
        ORDER BY u.created_at DESC
        """
    )


def list_roles():
    return fetch_all("SELECT role_id, role_name FROM roles ORDER BY role_name")


def list_ports():
    return fetch_all("SELECT port_code, port_name FROM ports ORDER BY port_name")


def create_user(full_name: str, username: str, plain_password: str, role_id: int, port_code: str | None):
    pw_hash = hash_password(plain_password)
    row = fetch_one(
        """
        INSERT INTO users (full_name, username, password_hash, role_id, port_code)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING user_id
        """,
        (full_name, username, pw_hash, role_id, port_code),
    )
    return row["user_id"]


def set_user_active(user_id: int, is_active: bool):
    execute("UPDATE users SET is_active = %s WHERE user_id = %s", (is_active, user_id))


def reset_password(user_id: int, new_plain_password: str):
    pw_hash = hash_password(new_plain_password)
    execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (pw_hash, user_id))


def delete_user(user_id: int):
    execute("DELETE FROM users WHERE user_id = %s", (user_id,))


# ---------------- Entry correction ----------------

def search_entries(query: str):
    return fetch_all(
        """
        SELECT entry_id, entry_number, entry_type, port_code, warehouse_id,
               goods_description, declared_value, status, captured_by, date_entered
        FROM entries
        WHERE entry_number ILIKE %s OR goods_description ILIKE %s
        ORDER BY date_entered DESC LIMIT 50
        """,
        (f"%{query}%", f"%{query}%"),
    )


def correct_entry(entry_id: int, admin_id: int, fields: dict, reason: str):
    """
    fields: dict of column -> new value for any correctable field
    (entry_number, goods_description, declared_value, importer_name, etc).
    """
    if not fields:
        return
    entry = fetch_one("SELECT entry_number FROM entries WHERE entry_id = %s", (entry_id,))
    if not entry:
        raise ValueError("Entry not found")

    set_clause = ", ".join(f"{col} = %s" for col in fields)
    params = list(fields.values()) + [admin_id, entry_id]
    execute(
        f"UPDATE entries SET {set_clause}, last_edited_by = %s, last_edited_at = now() WHERE entry_id = %s",
        tuple(params),
    )
    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, 'ADMIN_CORRECTION', %s, 'Admin', %s)
        """,
        (entry_id, entry["entry_number"], admin_id, f"Corrected fields {list(fields.keys())}: {reason}"),
    )


# ---------------- Audit trail ----------------

def audit_trail(entry_id: int | None = None, limit: int = 200):
    if entry_id:
        return fetch_all(
            "SELECT * FROM audit_log WHERE entry_id = %s ORDER BY action_timestamp DESC",
            (entry_id,),
        )
    return fetch_all(
        "SELECT * FROM audit_log ORDER BY action_timestamp DESC LIMIT %s", (limit,)
    )


def detained_goods_with_officer():
    """RIH/NOS still active, with the capturing officer's name — for audit review."""
    return fetch_all(
        """
        SELECT e.entry_id, e.entry_number, e.entry_type, e.port_code,
               e.goods_description, e.declared_value, e.date_entered,
               e.bond_due_date, e.status, u.full_name AS captured_by_officer
        FROM entries e
        LEFT JOIN users u ON u.user_id = e.captured_by
        WHERE e.status NOT IN ('released','sold','auctioned','appropriated')
        ORDER BY e.date_entered DESC
        """
    )


# ---------------- Message moderation ----------------

def delete_message(message_id: int):
    execute("DELETE FROM messages WHERE message_id = %s", (message_id,))


def list_all_messages(limit: int = 200):
    return fetch_all(
        """
        SELECT m.message_id, m.subject, m.body, m.created_at, m.recipient_scope,
               m.recipient_role, m.recipient_port, u.full_name AS sender_name
        FROM messages m JOIN users u ON u.user_id = m.sender_user_id
        ORDER BY m.created_at DESC LIMIT %s
        """,
        (limit,),
    )


# ---------------- Statistics ----------------

def revenue_stats():
    row = fetch_one(
        """
        SELECT COALESCE(SUM(amount_collected), 0) AS total_collected,
               COUNT(*) FILTER (WHERE action_type = 'release' AND manager_status = 'approved') AS releases_completed
        FROM action_requests
        """
    )
    return row


def warehouse_usage_stats():
    return fetch_all(
        """
        SELECT w.warehouse_name, w.warehouse_type, w.capacity,
               COUNT(e.entry_id) FILTER (
                   WHERE e.status NOT IN ('released','sold','auctioned','appropriated')
               ) AS current_occupancy
        FROM warehouses w
        LEFT JOIN entries e ON e.warehouse_id = w.warehouse_id
        GROUP BY w.warehouse_id
        ORDER BY w.warehouse_name
        """
    )


def days_until_expiry_report(port_code: str | None = None):
    """RIH entries with days remaining (negative = overdue), for tracking."""
    query = """
        SELECT entry_id, entry_number, port_code, bond_due_date,
               EXTRACT(DAY FROM bond_due_date - now())::int AS days_remaining,
               status
        FROM entries
        WHERE entry_type = 'RIH'
              AND status NOT IN ('released','sold','auctioned','appropriated')
    """
    params = ()
    if port_code:
        query += " AND port_code = %s"
        params = (port_code,)
    query += " ORDER BY days_remaining ASC"
    return fetch_all(query, params)
"""
Unified Release / Disposal workflow for RIH and NOS entries.

Officer requests an action (release after payment, or disposal via
offhand sale / appropriation / auction) -> Supervisor reviews ->
Manager gives final approval -> action is effected (goods removed
from active stock, full record kept in audit_log).
"""
from app.db import fetch_all, fetch_one, execute
from app.notifications import notify_role, notify_user


def request_action(entry_id: int, officer_id: int, action_type: str,
                    disposal_method: str | None = None, notes: str = "") -> int:
    """action_type: 'release' or 'disposal'."""
    if action_type not in ("release", "disposal"):
        raise ValueError("action_type must be 'release' or 'disposal'")
    if action_type == "disposal" and disposal_method not in ("offhand_sale", "appropriation", "auction"):
        raise ValueError("disposal_method must be offhand_sale, appropriation, or auction")

    entry = fetch_one("SELECT entry_number, port_code FROM entries WHERE entry_id = %s", (entry_id,))
    if not entry:
        raise ValueError("Entry not found")

    row = fetch_one(
        """
        INSERT INTO action_requests (entry_id, action_type, disposal_method, requested_by, request_notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING request_id
        """,
        (entry_id, action_type, disposal_method, officer_id, notes),
    )
    request_id = row["request_id"]

    notify_role(
        "Supervisor", "entry_pending_approval",
        f"{action_type.title()} requested on entry {entry['entry_number']} — awaiting your review.",
        entry_id=entry_id, port_code=entry["port_code"],
    )
    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, %s, %s, 'Officer', %s)
        """,
        (entry_id, entry["entry_number"], f"{action_type.upper()}_REQUESTED", officer_id, notes),
    )
    return request_id


def pending_supervisor_review(port_code: str | None = None):
    query = """
        SELECT ar.*, e.entry_number, e.entry_type, e.port_code, e.goods_description, e.declared_value
        FROM action_requests ar
        JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.supervisor_status = 'pending'
    """
    params = ()
    if port_code:
        query += " AND e.port_code = %s"
        params = (port_code,)
    query += " ORDER BY ar.created_at"
    return fetch_all(query, params)


def supervisor_review(request_id: int, supervisor_id: int, approve: bool, notes: str = ""):
    req = fetch_one(
        """
        SELECT ar.entry_id, ar.action_type, e.entry_number, e.port_code
        FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.request_id = %s
        """,
        (request_id,),
    )
    if not req:
        raise ValueError("Request not found")

    new_status = "approved" if approve else "rejected"
    execute(
        """
        UPDATE action_requests
        SET supervisor_status = %s, supervisor_by = %s, supervisor_at = now(), supervisor_notes = %s
        WHERE request_id = %s
        """,
        (new_status, supervisor_id, notes, request_id),
    )

    if approve:
        notify_role(
            "Manager", "entry_pending_approval",
            f"{req['action_type'].title()} on entry {req['entry_number']} approved by Supervisor, awaiting your final approval.",
            entry_id=req["entry_id"], port_code=req["port_code"],
        )
    else:
        requester = fetch_one("SELECT requested_by FROM action_requests WHERE request_id = %s", (request_id,))
        notify_user(
            requester["requested_by"], "entry_rejected",
            f"{req['action_type'].title()} request on entry {req['entry_number']} was rejected by Supervisor: {notes}",
            entry_id=req["entry_id"],
        )

    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, %s, %s, 'Supervisor', %s)
        """,
        (req["entry_id"], req["entry_number"], f"SUPERVISOR_{new_status.upper()}", supervisor_id, notes),
    )


def pending_manager_approval():
    return fetch_all(
        """
        SELECT ar.*, e.entry_number, e.entry_type, e.port_code, e.goods_description, e.declared_value
        FROM action_requests ar
        JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.supervisor_status = 'approved' AND ar.manager_status = 'pending'
        ORDER BY ar.created_at
        """
    )


def manager_decide_and_effect(request_id: int, manager_id: int, approve: bool, notes: str = ""):
    """
    Manager's final decision. If approved, the action is immediately
    effected: release -> entry status 'released'; disposal -> status
    matches the disposal method. Either way it leaves active tracking,
    but the full record remains in entries + audit_log.
    """
    req = fetch_one(
        """
        SELECT ar.entry_id, ar.action_type, ar.disposal_method, ar.requested_by,
               e.entry_number
        FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.request_id = %s
        """,
        (request_id,),
    )
    if not req:
        raise ValueError("Request not found")

    new_status = "approved" if approve else "rejected"
    execute(
        """
        UPDATE action_requests
        SET manager_status = %s, manager_by = %s, manager_at = now(), manager_notes = %s
        WHERE request_id = %s
        """,
        (new_status, manager_id, notes, request_id),
    )

    if approve:
        if req["action_type"] == "release":
            final_status = "released"
        else:
            final_status = {"offhand_sale": "sold", "appropriation": "appropriated", "auction": "auctioned"}[req["disposal_method"]]

        execute(
            "UPDATE entries SET status = %s, updated_at = now() WHERE entry_id = %s",
            (final_status, req["entry_id"]),
        )
        execute(
            "UPDATE action_requests SET effected = TRUE, effected_at = now() WHERE request_id = %s",
            (request_id,),
        )
        # If this was a seizure disposal, mark the seizure's manager approval too
        execute(
            """
            UPDATE seizures SET manager_approval_by = %s, manager_approval_date = now(),
                   disposal_type = %s, disposal_date = now()
            WHERE entry_id = %s
            """,
            (manager_id, req["disposal_method"], req["entry_id"]),
        )

    notify_user(
        req["requested_by"], "entry_approved" if approve else "entry_rejected",
        f"{req['action_type'].title()} on entry {req['entry_number']} was {new_status} by Manager."
        + (f" Reason: {notes}" if notes and not approve else " Action effected."),
        entry_id=req["entry_id"],
    )
    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, %s, %s, 'Manager', %s)
        """,
        (req["entry_id"], req["entry_number"], f"MANAGER_{new_status.upper()}", manager_id, notes),
    )
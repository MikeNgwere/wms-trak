"""
Four release/disposal pathways for RIH/NOS entries: Release to Owner,
Forfeiture (appropriation to the State), Destruction, and E-Auction.

Flow for all four:
    Officer requests (+ type-specific request-time details)
    -> Supervisor reviews (approve forwards to Manager, reject ends it)
    -> Manager gives final approval (this is PERMISSION, not yet effected)
    -> Officer finalizes (+ type-specific finalization-time details) —
       THIS is what actually removes the entry from active tracking.

entries.status through this flow:
    in_warehouse/seized -> ... -> approved_pending_finalization
        -> released | forfeited | destroyed | sold  (final, via finalize_*)
"""
from datetime import datetime

from app.db import fetch_all, fetch_one, execute
from app.notifications import notify_role, notify_user

ACTION_TYPES = ("release_to_owner", "forfeiture", "destruction", "e_auction")


# ---------------- Request stage (Officer) ----------------

def _create_request(entry_id: int, officer_id: int, action_type: str, notes: str) -> tuple[int, dict]:
    entry = fetch_one("SELECT entry_number, port_code FROM entries WHERE entry_id = %s", (entry_id,))
    if not entry:
        raise ValueError("Entry not found")
    row = fetch_one(
        """
        INSERT INTO action_requests (entry_id, action_type, requested_by, request_notes)
        VALUES (%s, %s, %s, %s)
        RETURNING request_id
        """,
        (entry_id, action_type, officer_id, notes),
    )
    request_id = row["request_id"]
    notify_role(
        "Supervisor", "entry_pending_approval",
        f"{action_type.replace('_', ' ').title()} requested on entry {entry['entry_number']} — awaiting your review.",
        entry_id=entry_id, port_code=entry["port_code"],
    )
    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, %s, %s, 'Officer', %s)
        """,
        (entry_id, entry["entry_number"], f"{action_type.upper()}_REQUESTED", officer_id, notes),
    )
    return request_id, entry


def request_release_to_owner(entry_id: int, officer_id: int, notes: str = "") -> int:
    request_id, _ = _create_request(entry_id, officer_id, "release_to_owner", notes)
    execute("INSERT INTO release_to_owner_details (request_id) VALUES (%s)", (request_id,))
    return request_id


def request_forfeiture(entry_id: int, officer_id: int, ministry_name: str,
                        request_letter_reference: str, notes: str = "") -> int:
    request_id, _ = _create_request(entry_id, officer_id, "forfeiture", notes)
    execute(
        """
        INSERT INTO forfeiture_details (request_id, ministry_name, request_letter_reference)
        VALUES (%s, %s, %s)
        """,
        (request_id, ministry_name, request_letter_reference),
    )
    return request_id


def request_destruction(entry_id: int, officer_id: int, port_health_officer_name: str,
                         port_health_approval_reference: str, reason_for_destruction: str,
                         notes: str = "") -> int:
    request_id, _ = _create_request(entry_id, officer_id, "destruction", notes)
    execute(
        """
        INSERT INTO destruction_details (
            request_id, port_health_officer_name, port_health_approval_reference, reason_for_destruction
        )
        VALUES (%s, %s, %s, %s)
        """,
        (request_id, port_health_officer_name, port_health_approval_reference, reason_for_destruction),
    )
    return request_id


def request_eauction(entry_id: int, officer_id: int, notes: str = "") -> int:
    request_id, _ = _create_request(entry_id, officer_id, "e_auction", notes)
    execute("INSERT INTO eauction_details (request_id) VALUES (%s)", (request_id,))
    return request_id


# ---------------- Supervisor review (generic across all 4 types) ----------------

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
            f"{req['action_type'].replace('_', ' ').title()} on entry {req['entry_number']} approved by Supervisor, awaiting your approval.",
            entry_id=req["entry_id"], port_code=req["port_code"],
        )
    else:
        requester = fetch_one("SELECT requested_by FROM action_requests WHERE request_id = %s", (request_id,))
        notify_user(
            requester["requested_by"], "entry_rejected",
            f"{req['action_type'].replace('_', ' ').title()} request on entry {req['entry_number']} was rejected by Supervisor: {notes}",
            entry_id=req["entry_id"],
        )

    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, %s, %s, 'Supervisor', %s)
        """,
        (req["entry_id"], req["entry_number"], f"SUPERVISOR_{new_status.upper()}", supervisor_id, notes),
    )


# ---------------- Manager: grants permission (does NOT effect yet) ----------------

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


def manager_decide(request_id: int, manager_id: int, approve: bool, notes: str = ""):
    """
    Manager's decision. Approving grants PERMISSION only — the entry
    moves to 'approved_pending_finalization' and the Officer must still
    finalize it (see finalize_* functions) before it actually leaves
    active tracking.
    """
    req = fetch_one(
        """
        SELECT ar.entry_id, ar.action_type, ar.requested_by, e.entry_number
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
        execute(
            "UPDATE entries SET status = 'approved_pending_finalization', updated_at = now() WHERE entry_id = %s",
            (req["entry_id"],),
        )
        notify_user(
            req["requested_by"], "entry_approved",
            f"{req['action_type'].replace('_', ' ').title()} on entry {req['entry_number']} approved by Manager — "
            f"you may now proceed and finalize the details.",
            entry_id=req["entry_id"],
        )
    else:
        notify_user(
            req["requested_by"], "entry_rejected",
            f"{req['action_type'].replace('_', ' ').title()} on entry {req['entry_number']} was rejected by Manager: {notes}",
            entry_id=req["entry_id"],
        )

    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, %s, %s, 'Manager', %s)
        """,
        (req["entry_id"], req["entry_number"], f"MANAGER_{new_status.upper()}", manager_id, notes),
    )


# ---------------- Officer finalization (this is what actually effects the action) ----------------

def pending_officer_finalization(port_code: str | None = None):
    """
    Manager-approved requests still awaiting the Officer's finalization
    step, with type-specific request-time details attached for display.
    """
    query = """
        SELECT ar.request_id, ar.entry_id, ar.action_type, ar.request_notes,
               e.entry_number, e.entry_type, e.port_code, e.goods_description,
               e.declared_value, e.date_entered, e.rent_charge_per_day
        FROM action_requests ar
        JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.manager_status = 'approved' AND ar.effected = FALSE
    """
    params = ()
    if port_code:
        query += " AND e.port_code = %s"
        params = (port_code,)
    query += " ORDER BY ar.manager_at"
    rows = fetch_all(query, params)
    for r in rows:
        if r["action_type"] == "forfeiture":
            r["type_detail"] = fetch_one("SELECT * FROM forfeiture_details WHERE request_id = %s", (r["request_id"],))
        elif r["action_type"] == "destruction":
            r["type_detail"] = fetch_one("SELECT * FROM destruction_details WHERE request_id = %s", (r["request_id"],))
        else:
            r["type_detail"] = None
    return rows


def _mark_effected(request_id: int, entry_id: int, entry_number: str, final_status: str, officer_id: int, notes: str):
    execute(
        "UPDATE action_requests SET effected = TRUE, effected_at = now() WHERE request_id = %s",
        (request_id,),
    )
    execute(
        "UPDATE entries SET status = %s, updated_at = now() WHERE entry_id = %s",
        (final_status, entry_id),
    )
    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, 'FINALIZED', %s, 'Officer', %s)
        """,
        (entry_id, entry_number, officer_id, notes),
    )


def finalize_release_to_owner(
    request_id: int, officer_id: int, duty_paid: float, additional_duty: float,
    rent_paid: float, receipt_number: str, y_number: str, clearance_details: str,
):
    req = fetch_one(
        """
        SELECT ar.entry_id, e.entry_number, e.date_entered, e.rent_charge_per_day
        FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.request_id = %s
        """,
        (request_id,),
    )
    if not req:
        raise ValueError("Request not found")

    days = (datetime.now().date() - req["date_entered"].date()).days + 1
    rent_calculated = float(req["rent_charge_per_day"] or 0) * days

    execute(
        """
        UPDATE release_to_owner_details
        SET duty_paid = %s, additional_duty = %s, rent_days_calculated = %s,
            rent_calculated = %s, rent_paid = %s, receipt_number = %s,
            y_number = %s, clearance_details = %s, finalized_by = %s, finalized_at = now()
        WHERE request_id = %s
        """,
        (duty_paid, additional_duty, days, rent_calculated, rent_paid,
         receipt_number, y_number, clearance_details, officer_id, request_id),
    )

    total_paid = (duty_paid or 0) + (additional_duty or 0) + (rent_paid or 0)
    execute(
        """
        INSERT INTO payments (entry_id, duty_amount, penalty_amount, rent_amount,
                               paid_amount, payment_date, receipt_number, recorded_by)
        VALUES (%s, %s, 0, %s, %s, now(), %s, %s)
        """,
        (req["entry_id"], (duty_paid or 0) + (additional_duty or 0), rent_paid, total_paid, receipt_number, officer_id),
    )
    execute(
        "UPDATE action_requests SET amount_collected = %s WHERE request_id = %s",
        (total_paid, request_id),
    )
    _mark_effected(request_id, req["entry_id"], req["entry_number"], "released", officer_id,
                    f"Released to owner. Receipt {receipt_number}, total {total_paid}")
    return rent_calculated


def finalize_forfeiture(
    request_id: int, officer_id: int, representative_name: str,
    representative_id_number: str, representative_occupation: str,
    goods_or_vehicle_finalization_details: str,
):
    req = fetch_one(
        "SELECT ar.entry_id, e.entry_number FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id WHERE ar.request_id = %s",
        (request_id,),
    )
    if not req:
        raise ValueError("Request not found")
    execute(
        """
        UPDATE forfeiture_details
        SET representative_name = %s, representative_id_number = %s,
            representative_occupation = %s, goods_or_vehicle_finalization_details = %s,
            finalized_by = %s, finalized_at = now()
        WHERE request_id = %s
        """,
        (representative_name, representative_id_number, representative_occupation,
         goods_or_vehicle_finalization_details, officer_id, request_id),
    )
    _mark_effected(request_id, req["entry_id"], req["entry_number"], "appropriated", officer_id,
                    f"Appropriated to representative {representative_name}")


def finalize_destruction(
    request_id: int, officer_id: int, destruction_date, destruction_place: str, stakeholders_present: str,
):
    req = fetch_one(
        "SELECT ar.entry_id, e.entry_number FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id WHERE ar.request_id = %s",
        (request_id,),
    )
    if not req:
        raise ValueError("Request not found")
    execute(
        """
        UPDATE destruction_details
        SET destruction_date = %s, destruction_place = %s, stakeholders_present = %s,
            finalized_by = %s, finalized_at = now()
        WHERE request_id = %s
        """,
        (destruction_date, destruction_place, stakeholders_present, officer_id, request_id),
    )
    _mark_effected(request_id, req["entry_id"], req["entry_number"], "destroyed", officer_id,
                    f"Destroyed at {destruction_place} on {destruction_date}")


def finalize_eauction(
    request_id: int, officer_id: int, revenue_collected: float, buyer_details: str, receipt_number: str,
):
    req = fetch_one(
        "SELECT ar.entry_id, e.entry_number FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id WHERE ar.request_id = %s",
        (request_id,),
    )
    if not req:
        raise ValueError("Request not found")
    execute(
        """
        UPDATE eauction_details
        SET revenue_collected = %s, buyer_details = %s, receipt_number = %s,
            finalized_by = %s, finalized_at = now()
        WHERE request_id = %s
        """,
        (revenue_collected, buyer_details, receipt_number, officer_id, request_id),
    )
    execute(
        """
        INSERT INTO payments (entry_id, duty_amount, penalty_amount, rent_amount,
                               paid_amount, payment_date, receipt_number, recorded_by)
        VALUES (%s, 0, 0, 0, %s, now(), %s, %s)
        """,
        (req["entry_id"], revenue_collected, receipt_number, officer_id),
    )
    execute(
        "UPDATE action_requests SET amount_collected = %s WHERE request_id = %s",
        (revenue_collected, request_id),
    )
    _mark_effected(request_id, req["entry_id"], req["entry_number"], "sold", officer_id,
                    f"Sold via e-auction. Receipt {receipt_number}, revenue {revenue_collected}")
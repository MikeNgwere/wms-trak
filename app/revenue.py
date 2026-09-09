"""
Finalization of manager-approved release/disposal actions: Officer
records the actual receipt number, amounts collected (duty, fines,
rent), and payment date. Feeds the payments table and updates
action_requests.amount_collected for revenue statistics. Also provides
a shared "Released & Sold" view so everyone in a jurisdiction can
track progress toward revenue targets.
"""
from app.db import fetch_all, fetch_one, execute


def pending_finalization(port_code: str | None = None):
    """
    Manager-approved & effected requests still missing a finalized
    payment record — these are what the Officer needs to close out.
    """
    query = """
        SELECT ar.request_id, ar.entry_id, ar.action_type, ar.disposal_method,
               e.entry_number, e.entry_type, e.port_code, e.goods_description, e.declared_value
        FROM action_requests ar
        JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.manager_status = 'approved' AND ar.effected = TRUE
              AND ar.amount_collected IS NULL
    """
    params = ()
    if port_code:
        query += " AND e.port_code = %s"
        params = (port_code,)
    query += " ORDER BY ar.manager_at DESC"
    return fetch_all(query, params)


def record_finalization(
    request_id: int,
    officer_id: int,
    receipt_number: str,
    duty_amount: float,
    penalty_amount: float,
    rent_amount: float,
):
    """
    Records the payment breakdown for a release, or the sale proceeds
    for a disposal (use duty_amount for the sale/appropriation value
    if that fits your process better — all three fields feed the same
    payments row and total).
    """
    req = fetch_one(
        "SELECT entry_id FROM action_requests WHERE request_id = %s", (request_id,)
    )
    if not req:
        raise ValueError("Request not found")

    total_paid = (duty_amount or 0) + (penalty_amount or 0) + (rent_amount or 0)

    execute(
        """
        INSERT INTO payments (entry_id, duty_amount, penalty_amount, rent_amount,
                               paid_amount, payment_date, receipt_number, recorded_by)
        VALUES (%s, %s, %s, %s, %s, now(), %s, %s)
        """,
        (req["entry_id"], duty_amount, penalty_amount, rent_amount, total_paid, receipt_number, officer_id),
    )
    execute(
        "UPDATE action_requests SET amount_collected = %s WHERE request_id = %s",
        (total_paid, request_id),
    )
    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, (SELECT entry_number FROM entries WHERE entry_id = %s), 'PAYMENT_FINALIZED', %s, 'Officer', %s)
        """,
        (req["entry_id"], req["entry_id"], officer_id, f"Receipt {receipt_number}, total {total_paid}"),
    )


def released_and_sold(port_code: str | None = None, limit: int = 200):
    """
    All entries that have left active tracking (released/sold/auctioned/
    appropriated), with payment totals — visible to everyone in a
    jurisdiction to track revenue targets.
    """
    query = """
        SELECT e.entry_id, e.entry_number, e.entry_type, e.port_code, e.status,
               e.goods_description, e.declared_value, e.updated_at,
               ar.action_type, ar.disposal_method, ar.amount_collected,
               p.receipt_number
        FROM entries e
        JOIN action_requests ar ON ar.entry_id = e.entry_id AND ar.effected = TRUE
        LEFT JOIN payments p ON p.entry_id = e.entry_id
        WHERE e.status IN ('released','sold','auctioned','appropriated')
    """
    params = []
    if port_code:
        query += " AND e.port_code = %s"
        params.append(port_code)
    query += " ORDER BY e.updated_at DESC LIMIT %s"
    params.append(limit)
    return fetch_all(query, tuple(params))


def revenue_summary(port_code: str | None = None):
    query = """
        SELECT COALESCE(SUM(ar.amount_collected), 0) AS total_collected,
               COUNT(*) AS total_finalized
        FROM action_requests ar
        JOIN entries e ON e.entry_id = ar.entry_id
        WHERE ar.amount_collected IS NOT NULL
    """
    params = ()
    if port_code:
        query += " AND e.port_code = %s"
        params = (port_code,)
    return fetch_one(query, params)
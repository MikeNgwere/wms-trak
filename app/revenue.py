"""
Revenue visibility: everything that has left active tracking
(released, sold via e-auction, destroyed, or appropriated), visible
to everyone in a jurisdiction to track revenue targets.
"""
from app.db import fetch_all, fetch_one


def released_and_sold(port_code: str | None = None, limit: int = 200):
    """
    All entries that have left active tracking, with payment totals —
    visible to everyone in a jurisdiction to track revenue targets.
    """
    query = """
        SELECT e.entry_id, e.entry_number, e.entry_type, e.port_code, e.status,
               e.goods_description, e.declared_value, e.updated_at,
               ar.action_type, ar.amount_collected,
               p.receipt_number
        FROM entries e
        JOIN action_requests ar ON ar.entry_id = e.entry_id AND ar.effected = TRUE
        LEFT JOIN payments p ON p.entry_id = e.entry_id
        WHERE e.status IN ('released','sold','destroyed','appropriated')
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
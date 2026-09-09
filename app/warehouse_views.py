"""
Warehouse management views: RIH list and Seizures list, with
filtering by date range, month, and warehouse — for Manager oversight.
"""
from app.db import fetch_all


def rih_list(port_code: str | None = None, warehouse_id: int | None = None,
             date_from=None, date_to=None):
    query = """
        SELECT e.entry_id, e.entry_number, e.port_code, w.warehouse_name,
               e.goods_description, e.declared_value, e.date_entered,
               e.bond_due_date, e.status
        FROM entries e
        LEFT JOIN warehouses w ON w.warehouse_id = e.warehouse_id
        WHERE e.entry_type = 'RIH'
    """
    params = []
    if port_code:
        query += " AND e.port_code = %s"
        params.append(port_code)
    if warehouse_id:
        query += " AND e.warehouse_id = %s"
        params.append(warehouse_id)
    if date_from:
        query += " AND e.date_entered >= %s"
        params.append(date_from)
    if date_to:
        query += " AND e.date_entered <= %s"
        params.append(date_to)
    query += " ORDER BY e.bond_due_date ASC NULLS LAST"
    return fetch_all(query, tuple(params))


def seizures_list(port_code: str | None = None, warehouse_id: int | None = None,
                   date_from=None, date_to=None):
    query = """
        SELECT s.seizure_id, e.entry_id, e.entry_number, e.port_code, w.warehouse_name,
               e.goods_description, e.declared_value,
               s.seizure_date, s.appeal_status, s.appeal_deadline,
               s.disposal_type, s.ready_for_disposal,
               s.supervisor_approval_by, s.manager_approval_by, s.disposal_date
        FROM seizures s
        JOIN entries e ON e.entry_id = s.entry_id
        LEFT JOIN warehouses w ON w.warehouse_id = e.warehouse_id
        WHERE 1=1
    """
    params = []
    if port_code:
        query += " AND e.port_code = %s"
        params.append(port_code)
    if warehouse_id:
        query += " AND e.warehouse_id = %s"
        params.append(warehouse_id)
    if date_from:
        query += " AND s.seizure_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND s.seizure_date <= %s"
        params.append(date_to)
    query += " ORDER BY s.seizure_date DESC"
    return fetch_all(query, tuple(params))


def seizures_ready_for_disposal(port_code: str | None = None):
    query = """
        SELECT s.seizure_id, e.entry_id, e.entry_number, e.port_code,
               e.goods_description, e.declared_value,
               s.disposal_type, s.appeal_deadline
        FROM seizures s
        JOIN entries e ON e.entry_id = s.entry_id
        WHERE s.ready_for_disposal = TRUE AND s.manager_approval_by IS NULL
    """
    params = ()
    if port_code:
        query += " AND e.port_code = %s"
        params = (port_code,)
    query += " ORDER BY s.appeal_deadline ASC"
    return fetch_all(query, params)


def monthly_summary(port_code: str | None = None):
    """RIH and NOS counts grouped by month, for a quick trend view."""
    query = """
        SELECT to_char(date_entered, 'YYYY-MM') AS month,
               entry_type, COUNT(*) AS count
        FROM entries
        WHERE entry_type IN ('RIH', 'NOS')
    """
    params = []
    if port_code:
        query += " AND port_code = %s"
        params.append(port_code)
    query += " GROUP BY month, entry_type ORDER BY month DESC, entry_type"
    return fetch_all(query, tuple(params))
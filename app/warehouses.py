"""
Warehouse & vehicle pound management for a station.

ZWFB has Warehouses A-E (goods, capacity 150 each) and Pounds A-E
(vehicles, capacity 15 each) — seeded in migration_004. An Officer
can see current occupancy and mark a warehouse full/not full.
"""
from app.db import fetch_all, fetch_one, execute


def warehouses_for_port(port_code: str, warehouse_type: str | None = None):
    """List warehouses/pounds at a station with live occupancy counts."""
    query = """
        SELECT w.warehouse_id, w.warehouse_name, w.warehouse_type, w.capacity,
               w.is_full, w.marked_full_at,
               COUNT(e.entry_id) FILTER (
                   WHERE e.status NOT IN ('released','sold','auctioned','appropriated')
               ) AS current_occupancy
        FROM warehouses w
        LEFT JOIN entries e ON e.warehouse_id = w.warehouse_id
        WHERE w.port_code = %s
    """
    params = [port_code]
    if warehouse_type:
        query += " AND w.warehouse_type = %s"
        params.append(warehouse_type)
    query += " GROUP BY w.warehouse_id ORDER BY w.warehouse_name"
    return fetch_all(query, tuple(params))


def toggle_full(warehouse_id: int, officer_id: int, is_full: bool):
    execute(
        """
        UPDATE warehouses
        SET is_full = %s, marked_full_by = %s, marked_full_at = now()
        WHERE warehouse_id = %s
        """,
        (is_full, officer_id, warehouse_id),
    )


def goods_in_warehouse(warehouse_id: int):
    return fetch_all(
        """
        SELECT entry_id, entry_number, entry_type, goods_description,
               declared_value, date_entered, status
        FROM entries
        WHERE warehouse_id = %s
              AND status NOT IN ('released','sold','auctioned','appropriated')
        ORDER BY date_entered DESC
        """,
        (warehouse_id,),
    )
"""
Entry capture: Officer records RIH and NOS entries directly into the
system, including full document fields (importer/owner details,
RIH/NOS-specific fields, optional vehicle details) and warehouse/pound
assignment.
"""
from datetime import datetime

from app.db import fetch_all, fetch_one, execute
from app.bond_engine import compute_due_date
from app.notifications import notify_role


def capture_entry(
    entry_number: str,
    entry_type: str,
    port_code: str,
    officer_id: int,
    goods_description: str,
    declared_value: float,
    warehouse_id: int | None = None,
    warehouse_registry_number: str | None = None,
    importer_name: str | None = None,
    importer_address: str | None = None,
    importer_contact: str | None = None,
    importer_id_number: str | None = None,
    importer_bpn_tin: str | None = None,
    quantity_units: str | None = None,
    gross_weight: float | None = None,
    net_weight: float | None = None,
    is_vehicle: bool = False,
    rih_data: dict | None = None,
    nos_data: dict | None = None,
    vehicle_data: dict | None = None,
) -> int:
    """
    Officer captures a new RIH or NOS entry with full document fields.
    rih_data / nos_data hold the type-specific fields (see rih_details /
    nos_details tables); vehicle_data is used when is_vehicle=True.
    """
    if entry_type not in ("RIH", "NOS"):
        raise ValueError("entry_type must be RIH or NOS")

    date_entered = datetime.now()
    due_date = compute_due_date(date_entered, entry_type) if entry_type == "RIH" else None

    row = fetch_one(
        """
        INSERT INTO entries (
            entry_number, entry_type, port_code, warehouse_id,
            goods_description, declared_value, date_entered, bond_due_date,
            status, captured_by, warehouse_registry_number,
            importer_name, importer_address, importer_contact,
            importer_id_number, importer_bpn_tin,
            quantity_units, gross_weight, net_weight, is_vehicle
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'in_warehouse',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING entry_id
        """,
        (entry_number, entry_type, port_code, warehouse_id,
         goods_description, declared_value, date_entered, due_date, officer_id,
         warehouse_registry_number, importer_name, importer_address, importer_contact,
         importer_id_number, importer_bpn_tin, quantity_units, gross_weight, net_weight, is_vehicle),
    )
    entry_id = row["entry_id"]

    if entry_type == "RIH":
        rih_data = rih_data or {}
        execute(
            """
            INSERT INTO rih_details (
                entry_id, rih_number, reason_category, reason_narrative,
                act_clause, issuing_officer_id, importer_ack_signed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (entry_id, rih_data.get("rih_number"), rih_data.get("reason_category"),
             rih_data.get("reason_narrative"), rih_data.get("act_clause"),
             officer_id, rih_data.get("importer_ack_signed", False)),
        )

    if entry_type == "NOS":
        nos_data = nos_data or {}
        execute(
            """
            INSERT INTO nos_details (
                entry_id, nos_number, seizing_officer_id, seizing_officer_ec_number,
                offence_committed, act_section_breached, marks_and_numbers,
                statutory_warning_acknowledged, offender_signature_received
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (entry_id, nos_data.get("nos_number"), officer_id, nos_data.get("seizing_officer_ec_number"),
             nos_data.get("offence_committed"), nos_data.get("act_section_breached"),
             nos_data.get("marks_and_numbers"), nos_data.get("statutory_warning_acknowledged", False),
             nos_data.get("offender_signature_received", False)),
        )
        # Seizure record: appeal window is 3 months from seizure date (C&E Act s.193(12))
        execute(
            """
            INSERT INTO seizures (entry_id, seizure_date, appeal_deadline)
            VALUES (%s, %s, %s + interval '90 days')
            """,
            (entry_id, date_entered, date_entered),
        )
        execute(
            "UPDATE entries SET status = 'seized', updated_at = now() WHERE entry_id = %s",
            (entry_id,),
        )

    if is_vehicle and vehicle_data:
        execute(
            """
            INSERT INTO vehicle_details (
                entry_id, registration_number, chassis_number, engine_number,
                make, model, colour, year_of_manufacture
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (entry_id, vehicle_data.get("registration_number"), vehicle_data.get("chassis_number"),
             vehicle_data.get("engine_number"), vehicle_data.get("make"), vehicle_data.get("model"),
             vehicle_data.get("colour"), vehicle_data.get("year_of_manufacture")),
        )

    notify_role(
        "Supervisor", "entry_flagged" if entry_type == "NOS" else "entry_pending_approval",
        f"New {entry_type} entry {entry_number} captured and now being tracked.",
        entry_id=entry_id, port_code=port_code,
    )
    execute(
        """
        INSERT INTO audit_log (entry_id, entry_number, action, actor_user_id, actor_role, notes)
        VALUES (%s, %s, 'ENTRY_CAPTURED', %s, 'Officer', %s)
        """,
        (entry_id, entry_number, officer_id, f"{entry_type} captured at {port_code}"),
    )
    return entry_id


def entries_captured_by(officer_id: int):
    return fetch_all(
        """
        SELECT entry_id, entry_number, entry_type, goods_description,
               declared_value, date_entered, bond_due_date, status, warehouse_id
        FROM entries WHERE captured_by = %s ORDER BY date_entered DESC
        """,
        (officer_id,),
    )


def active_entries_for_port(port_code: str | None = None):
    """RIH/NOS entries still in active tracking (not yet released/disposed)."""
    query = """
        SELECT entry_id, entry_number, entry_type, goods_description,
               declared_value, date_entered, bond_due_date, status, warehouse_id
        FROM entries
        WHERE status NOT IN ('released', 'sold', 'auctioned', 'appropriated')
    """
    params = ()
    if port_code:
        query += " AND port_code = %s"
        params = (port_code,)
    query += " ORDER BY bond_due_date ASC NULLS LAST"
    return fetch_all(query, params)


def get_entry_full_detail(entry_id: int):
    """Full picture of one entry, joined with its RIH/NOS/vehicle detail rows."""
    entry = fetch_one("SELECT * FROM entries WHERE entry_id = %s", (entry_id,))
    if not entry:
        return None
    entry["rih"] = fetch_one("SELECT * FROM rih_details WHERE entry_id = %s", (entry_id,))
    entry["nos"] = fetch_one("SELECT * FROM nos_details WHERE entry_id = %s", (entry_id,))
    entry["vehicle"] = fetch_one("SELECT * FROM vehicle_details WHERE entry_id = %s", (entry_id,))
    return entry
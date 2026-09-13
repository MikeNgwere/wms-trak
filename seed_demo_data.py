"""
One-time seeding script: generates a realistic, varied demo dataset
for WMS-Trak — RIH and NOS entries across different goods types, ages
(fresh, nearing the 60-day RIH deadline, 60-89 days overdue, 90+ days
overdue), plus a handful already finalized (Released/Sold/Destroyed/
Appropriated) so Statistics and Released & Sold show real numbers.

Run once from your project root (with venv active):
    python seed_demo_data.py

Safe to re-run — entry_number is randomised each run, so it just adds
more data rather than erroring on duplicates. Delete rows manually via
the Admin > Entry Correction / a direct SQL DELETE if you want to reset.
"""
import os
import random
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ---------------- Reference data ----------------

cur.execute("SELECT user_id FROM users WHERE role_id = (SELECT role_id FROM roles WHERE role_name='Officer') AND is_active = TRUE LIMIT 1")
officer = cur.fetchone()
if not officer:
    raise SystemExit("No active Officer user found — create one first.")
OFFICER_ID = officer["user_id"]

cur.execute("SELECT warehouse_id, warehouse_name FROM warehouses WHERE port_code='ZWFB' AND warehouse_type='goods' ORDER BY warehouse_name")
GOODS_WAREHOUSES = cur.fetchall()

cur.execute("SELECT warehouse_id, warehouse_name FROM warehouses WHERE port_code='ZWFB' AND warehouse_type='vehicle_pound' ORDER BY warehouse_name")
POUNDS = cur.fetchall()

if not GOODS_WAREHOUSES or not POUNDS:
    raise SystemExit("ZWFB warehouses/pounds not found — run migration_004 seed data first.")

# ---------------- Sample data pools ----------------

IMPORTER_NAMES = [
    "Tendai Moyo", "Rumbidzai Chikwava", "Farai Ncube", "Chipo Mutasa",
    "Tapiwa Dube", "Nyasha Sibanda", "Kudzai Madziva", "Panashe Gwenzi",
    "Rutendo Chirwa", "Tinashe Mafuta", "Vimbai Nyoni", "Takudzwa Chuma",
    "Anesu Mangwiro", "Rufaro Zishiri", "Blessing Marufu",
]

GOODS_CATALOG = [
    # (description, category, value_range, weight_range, unit, rent_rate, has_expiry, is_vehicle)
    ("Assorted used clothing bales", "textiles", (500, 3000), (200, 800), "kg", 3.0, False, False),
    ("Second-hand tyres (various sizes)", "tyres", (800, 4000), (300, 1200), "kg", 4.0, False, False),
    ("Bags of cement", "building_materials", (1000, 5000), (5000, 15000), "kg", 5.0, False, False),
    ("Cases of assorted alcoholic beverages", "beverages", (2000, 8000), (500, 2000), "kg", 4.5, True, False),
    ("Crates of soft drinks", "beverages", (500, 2500), (400, 1500), "kg", 3.0, True, False),
    ("Bales of maize seed", "agriculture", (1500, 6000), (1000, 4000), "kg", 3.5, True, False),
    ("Boxes of assorted cosmetics", "cosmetics", (1000, 4500), (100, 400), "kg", 4.0, True, False),
    ("Cartons of cigarettes", "tobacco", (3000, 12000), (50, 200), "kg", 6.0, False, False),
    ("Electronics — assorted phones and accessories", "electronics", (5000, 20000), (50, 300), "kg", 8.0, False, False),
    ("Bales of second-hand shoes", "textiles", (600, 2500), (150, 600), "kg", 3.0, False, False),
    ("Drums of diesel fuel", "fuel", (4000, 15000), (5000, 20000), "litres", 10.0, False, False),
    ("Bags of fertiliser", "agriculture", (1200, 5000), (3000, 10000), "kg", 3.5, False, False),
    ("Cartons of pharmaceuticals (unregistered)", "pharmaceuticals", (2000, 9000), (50, 200), "kg", 7.0, True, False),
    ("Crates of fresh fruit and vegetables", "perishables", (300, 1500), (500, 2000), "kg", 4.0, True, False),
    ("Frozen meat products", "perishables", (1500, 6000), (800, 3000), "kg", 6.0, True, False),
    ("Assorted hardware tools", "hardware", (1000, 4000), (200, 800), "kg", 3.5, False, False),
    ("Bags of sugar", "foodstuffs", (800, 3000), (2000, 6000), "kg", 3.0, True, False),
    ("Rolls of fabric / textile material", "textiles", (2000, 7000), (500, 1500), "kg", 4.0, False, False),
    ("Assorted furniture (wooden)", "furniture", (1500, 6000), (300, 1000), "kg", 5.0, False, False),
    ("Bags of rice", "foodstuffs", (700, 2800), (1500, 5000), "kg", 3.0, True, False),
    # Vehicles
    ("Toyota Hilux D4D — smuggled entry", "vehicle", (8000, 25000), None, None, 12.0, False, True),
    ("Honda Fit — undeclared import", "vehicle", (3000, 8000), None, None, 8.0, False, True),
    ("Nissan NP200 — under-declared value", "vehicle", (5000, 12000), None, None, 10.0, False, True),
    ("Mercedes-Benz C200 — luxury vehicle, duty evasion", "vehicle", (15000, 35000), None, None, 15.0, False, True),
]

NOS_OFFENCES = [
    "Smuggling", "Undervaluation", "Misdescription of goods",
    "Prohibited importation", "Failure to declare", "Duty evasion",
]
ACT_SECTIONS = ["s.174", "s.176", "s.182", "s.193", "s.196"]
RIH_REASONS = ["failure_to_pay_duty", "missing_permit", "pending_valuation", "other"]

VEHICLE_MAKES_MODELS = {
    "Toyota Hilux D4D — smuggled entry": ("Toyota", "Hilux", "White"),
    "Honda Fit — undeclared import": ("Honda", "Fit", "Silver"),
    "Nissan NP200 — under-declared value": ("Nissan", "NP200", "Blue"),
    "Mercedes-Benz C200 — luxury vehicle, duty evasion": ("Mercedes-Benz", "C200", "Black"),
}

random.seed()


def rand_importer():
    name = random.choice(IMPORTER_NAMES)
    return {
        "name": name,
        "address": f"{random.randint(1, 999)} {random.choice(['Samora Machel Ave', 'Herbert Chitepo St', 'Robert Mugabe Rd', 'Chinhoyi St'])}, Harare",
        "contact": f"+263 7{random.randint(10,99)} {random.randint(100,999)} {random.randint(1000,9999)}",
        "id_number": f"{random.randint(10,79)}-{random.randint(100000,999999)}-{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{random.randint(10,99)}",
        "bpn_tin": f"BP{random.randint(1000000,9999999)}" if random.random() > 0.5 else None,
    }


def next_entry_number(prefix):
    return f"{prefix}-ZWFB-{random.randint(100000,999999)}"


def insert_entry(entry_type, days_ago, warehouse_id, goods_item, importer, is_vehicle):
    description, category, value_range, weight_range, unit, rent_rate, has_expiry, _ = goods_item
    date_entered = datetime.now() - timedelta(days=days_ago)
    bond_due_date = date_entered + timedelta(days=60) if entry_type == "RIH" else None
    declared_value = round(random.uniform(*value_range), 2)
    gross = round(random.uniform(*weight_range), 1) if weight_range else None
    net = round(gross * 0.92, 1) if gross else None
    expiry_date = (date_entered + timedelta(days=random.randint(20, 90))).date() if has_expiry else None
    exchange_rate = round(random.uniform(28.0, 35.0), 4)
    entry_number = next_entry_number(entry_type)

    cur.execute(
        """
        INSERT INTO entries (
            entry_number, entry_type, port_code, warehouse_id,
            goods_description, declared_value, date_entered, bond_due_date,
            status, captured_by, importer_name, importer_address, importer_contact,
            importer_id_number, importer_bpn_tin, quantity_units, gross_weight,
            net_weight, weight_unit, rent_charge_per_day, exchange_rate_zwg_usd,
            expiry_date, is_vehicle, created_at, updated_at
        ) VALUES (%s,%s,'ZWFB',%s,%s,%s,%s,%s,'in_warehouse',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s, %s)
        RETURNING entry_id
        """,
        (entry_number, entry_type, warehouse_id, description, declared_value,
         date_entered, bond_due_date, OFFICER_ID, importer["name"], importer["address"],
         importer["contact"], importer["id_number"], importer["bpn_tin"],
         f"{random.randint(1,50)} units" if not is_vehicle else "1 unit",
         gross, net, unit or "kg", rent_rate, exchange_rate, expiry_date, is_vehicle,
         date_entered, date_entered),
    )
    entry_id = cur.fetchone()["entry_id"]

    if entry_type == "RIH":
        cur.execute(
            """
            INSERT INTO rih_details (entry_id, rih_number, reason_category, reason_narrative, act_clause, issuing_officer_id)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (entry_id, f"RIH{random.randint(10000,99999)}", random.choice(RIH_REASONS),
             "Goods held pending resolution of documentation/duty issues.", "s.39(2)", OFFICER_ID),
        )
    else:
        cur.execute(
            """
            INSERT INTO nos_details (entry_id, nos_number, seizing_officer_id, seizing_officer_ec_number,
                                      offence_committed, act_section_breached, marks_and_numbers,
                                      statutory_warning_acknowledged, offender_signature_received)
            VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE,TRUE)
            """,
            (entry_id, f"NOS{random.randint(10000,99999)}L", OFFICER_ID, f"EC{random.randint(1000,9999)}",
             random.choice(NOS_OFFENCES), random.choice(ACT_SECTIONS), f"Marks: SN-{random.randint(1000,9999)}"),
        )
        cur.execute(
            """
            INSERT INTO seizures (entry_id, seizure_date, appeal_deadline)
            VALUES (%s, %s, %s)
            """,
            (entry_id, date_entered, date_entered + timedelta(days=90)),
        )
        cur.execute("UPDATE entries SET status='seized' WHERE entry_id=%s", (entry_id,))

    if is_vehicle:
        make, model, colour = VEHICLE_MAKES_MODELS.get(description, ("Generic", "Model", "White"))
        cur.execute(
            """
            INSERT INTO vehicle_details (entry_id, registration_number, chassis_number, engine_number, make, model, colour, year_of_manufacture)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (entry_id, f"A{random.randint(100,999)}-{random.choice('ABCDEFGH')}{random.randint(10,99)}",
             f"JT{random.randint(100000000,999999999)}", f"EN{random.randint(1000000,9999999)}",
             make, model, colour, random.randint(2005, 2022)),
        )

    # Flag overdue ones (bond period lapsed) to match real app behaviour
    if entry_type == "RIH" and days_ago > 60:
        cur.execute("UPDATE entries SET status='flagged' WHERE entry_id=%s", (entry_id,))

    return entry_id, entry_number


def finalize_as_released(entry_id, entry_number, days_ago):
    """Push a RIH entry all the way through Release to Owner, fully finalized."""
    cur.execute(
        "INSERT INTO action_requests (entry_id, action_type, requested_by, request_notes, supervisor_status, supervisor_by, supervisor_at, manager_status, manager_by, manager_at, effected, effected_at) "
        "VALUES (%s,'release_to_owner',%s,'Demo data — duty and rent settled','approved',%s,now(),'approved',%s,now(),TRUE,now()) RETURNING request_id",
        (entry_id, OFFICER_ID, OFFICER_ID, OFFICER_ID),
    )
    request_id = cur.fetchone()["request_id"]
    rent_calc = round(random.uniform(50, 400), 2)
    duty_paid = round(random.uniform(200, 2000), 2)
    receipt = f"RCPT{random.randint(100000,999999)}"
    cur.execute(
        "INSERT INTO release_to_owner_details (request_id, duty_paid, additional_duty, rent_days_calculated, rent_calculated, rent_paid, receipt_number, y_number, clearance_details, finalized_by, finalized_at) "
        "VALUES (%s,%s,0,%s,%s,%s,%s,%s,'Demo finalization',%s,now())",
        (request_id, duty_paid, days_ago, rent_calc, rent_calc, receipt, f"Y{random.randint(10000,99999)}", OFFICER_ID),
    )
    total = duty_paid + rent_calc
    cur.execute(
        "INSERT INTO payments (entry_id, duty_amount, penalty_amount, rent_amount, paid_amount, payment_date, receipt_number, recorded_by) "
        "VALUES (%s,%s,0,%s,%s,now(),%s,%s)",
        (entry_id, duty_paid, rent_calc, total, receipt, OFFICER_ID),
    )
    cur.execute("UPDATE action_requests SET amount_collected=%s WHERE request_id=%s", (total, request_id))
    cur.execute("UPDATE entries SET status='released' WHERE entry_id=%s", (entry_id,))


def finalize_as_sold(entry_id, entry_number):
    """Push an NOS entry through E-Auction, fully finalized."""
    cur.execute(
        "INSERT INTO action_requests (entry_id, action_type, requested_by, request_notes, supervisor_status, supervisor_by, supervisor_at, manager_status, manager_by, manager_at, effected, effected_at) "
        "VALUES (%s,'e_auction',%s,'Demo data — sold via e-auction','approved',%s,now(),'approved',%s,now(),TRUE,now()) RETURNING request_id",
        (entry_id, OFFICER_ID, OFFICER_ID, OFFICER_ID),
    )
    request_id = cur.fetchone()["request_id"]
    revenue = round(random.uniform(500, 8000), 2)
    receipt = f"EA{random.randint(100000,999999)}"
    cur.execute(
        "INSERT INTO eauction_details (request_id, revenue_collected, buyer_details, receipt_number, finalized_by, finalized_at) "
        "VALUES (%s,%s,%s,%s,%s,now())",
        (request_id, revenue, f"Buyer: {random.choice(IMPORTER_NAMES)}, verified via e-auction platform", receipt, OFFICER_ID),
    )
    cur.execute(
        "INSERT INTO payments (entry_id, duty_amount, penalty_amount, rent_amount, paid_amount, payment_date, receipt_number, recorded_by) "
        "VALUES (%s,0,0,0,%s,now(),%s,%s)",
        (entry_id, revenue, receipt, OFFICER_ID),
    )
    cur.execute("UPDATE action_requests SET amount_collected=%s WHERE request_id=%s", (revenue, request_id))
    cur.execute("UPDATE entries SET status='sold' WHERE entry_id=%s", (entry_id,))


# ---------------- Generation plan ----------------

goods_pool = [g for g in GOODS_CATALOG if not g[7]]
vehicle_pool = [g for g in GOODS_CATALOG if g[7]]

created = {"RIH": 0, "NOS": 0, "vehicles": 0, "finalized": 0}

# RIH: 24 goods entries across age buckets + 6 vehicle RIH entries
rih_buckets = (
    [(random.randint(1, 20)) for _ in range(6)] +      # fresh
    [(random.randint(50, 59)) for _ in range(6)] +      # nearing 60-day deadline
    [(random.randint(61, 89)) for _ in range(6)] +      # overdue 60-89 days
    [(random.randint(91, 150)) for _ in range(6)]        # overdue 90+ days
)
for days_ago in rih_buckets:
    item = random.choice(goods_pool)
    wh = random.choice(GOODS_WAREHOUSES)
    entry_id, entry_number = insert_entry("RIH", days_ago, wh["warehouse_id"], item, rand_importer(), False)
    created["RIH"] += 1

for days_ago in [random.randint(1, 20), random.randint(55, 65), random.randint(91, 140), random.randint(70, 85), random.randint(30, 40), random.randint(95, 130)]:
    item = random.choice(vehicle_pool)
    pound = random.choice(POUNDS)
    entry_id, entry_number = insert_entry("RIH", days_ago, pound["warehouse_id"], item, rand_importer(), True)
    created["RIH"] += 1
    created["vehicles"] += 1

# NOS: 16 goods entries + 4 vehicle NOS entries, across seizure-age buckets
nos_buckets = (
    [(random.randint(1, 30)) for _ in range(5)] +       # fresh, appeal open
    [(random.randint(40, 70)) for _ in range(5)] +       # mid appeal window
    [(random.randint(80, 89)) for _ in range(3)] +        # nearing appeal deadline
    [(random.randint(95, 130)) for _ in range(3)]          # past appeal deadline
)
for days_ago in nos_buckets:
    item = random.choice(goods_pool)
    wh = random.choice(GOODS_WAREHOUSES)
    entry_id, entry_number = insert_entry("NOS", days_ago, wh["warehouse_id"], item, rand_importer(), False)
    created["NOS"] += 1

for days_ago in [random.randint(1, 20), random.randint(45, 65), random.randint(85, 95), random.randint(100, 130)]:
    item = random.choice(vehicle_pool)
    pound = random.choice(POUNDS)
    entry_id, entry_number = insert_entry("NOS", days_ago, pound["warehouse_id"], item, rand_importer(), True)
    created["NOS"] += 1
    created["vehicles"] += 1

# A handful fully finalized, for Released & Sold / Statistics to show real numbers
for _ in range(4):
    days_ago = random.randint(65, 120)
    item = random.choice(goods_pool)
    wh = random.choice(GOODS_WAREHOUSES)
    entry_id, entry_number = insert_entry("RIH", days_ago, wh["warehouse_id"], item, rand_importer(), False)
    finalize_as_released(entry_id, entry_number, days_ago)
    created["finalized"] += 1

for _ in range(3):
    days_ago = random.randint(95, 130)
    item = random.choice(goods_pool)
    wh = random.choice(GOODS_WAREHOUSES)
    entry_id, entry_number = insert_entry("NOS", days_ago, wh["warehouse_id"], item, rand_importer(), False)
    finalize_as_sold(entry_id, entry_number)
    created["finalized"] += 1

conn.commit()
cur.close()
conn.close()

print("Demo data seeded successfully:")
print(f"  RIH entries created:       {created['RIH']}")
print(f"  NOS entries created:       {created['NOS']}")
print(f"  (of which vehicles):       {created['vehicles']}")
print(f"  Fully finalized entries:   {created['finalized']}")
print(f"  Total entries:             {created['RIH'] + created['NOS'] + created['finalized']}")

"""
WMS-Trak — Streamlit entry point.

Single dashboard page with horizontal, role-scoped tabs. The sidebar
only ever shows Notifications (a separate page) plus the Account
dropdown from app/theme.py — no per-role sidebar pages. Login persists
across page refreshes via a URL-token-backed session (see app/auth.py).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from app.auth import verify_login, create_session, get_user_by_session
from app.bond_engine import entries_nearing_expiry
...
from app.theme import render_sidebar, inject_global_css
from app.entries import capture_entry, entries_captured_by, active_entries_for_port, get_entry_full_detail
from app.action_requests import (
    request_action, pending_supervisor_review, supervisor_review,
    pending_manager_approval, manager_decide_and_effect,
)
from app.warehouses import warehouses_for_port, toggle_full, goods_in_warehouse
from app.warehouse_views import rih_list, seizures_list, seizures_ready_for_disposal, monthly_summary
from app.revenue import pending_finalization, record_finalization, released_and_sold, revenue_summary
from app.admin import (
    list_users, list_roles, list_ports, create_user, set_user_active,
    reset_password, delete_user, search_entries, correct_entry,
    audit_trail, detained_goods_with_officer, delete_message,
    list_all_messages, revenue_stats, warehouse_usage_stats, days_until_expiry_report,
)
from app.db import fetch_all

st.set_page_config(page_title="WMS-Trak", layout="wide")
inject_global_css()

if "user" not in st.session_state:
    st.session_state.user = None

st.markdown(
    """
    <style>
    div[data-testid="stFormSubmitButton"] button {
        background-color: #4CAF50 !important;
        color: white !important;
        border-radius: 999px !important;
        width: 100% !important;
        font-weight: 600 !important;
        padding: 0.6rem 0 !important;
        border: none !important;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #3d8b40 !important;
        color: white !important;
    }
    .stTextInput input {
        border-radius: 999px;
        background-color: #f0f0f0;
        border: none;
        padding: 0.6rem 1rem;
    }
    #login-wrapper div.stForm {
        border: 1px solid #e0e0e0;
        border-radius: 18px;
        padding: 2rem 2.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def login_screen():
    st.markdown("<div id='login-wrapper'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        logo_col1, logo_col2, logo_col3 = st.columns([1, 1, 1])
        with logo_col2:
            try:
                st.image("app/assets/zimra_logo.png", width=160)
            except Exception:
                pass
        st.markdown(
            "<h2 style='text-align:center;color:#1A1A1A;margin-top:0.5rem;'>WMS-Trak</h2>"
            "<p style='text-align:center;color:#666;margin-bottom:1.5rem;'>Warehouse Management System</p>",
            unsafe_allow_html=True,
        )
        with st.form("login"):
            username = st.text_input("Username", label_visibility="collapsed", placeholder="Username")
            password = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
            submitted = st.form_submit_button("SIGN IN", type="primary", use_container_width=True)
        if submitted:
            user = verify_login(username, password)
            if user:
                token = create_session(user["user_id"])
                st.query_params["token"] = token
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials or inactive account.")
    st.markdown("</div>", unsafe_allow_html=True)


# ==================== OFFICER TABS ====================

def officer_capture_tab(user):
    st.subheader("Capture a new RIH or NOS entry")
    entry_type = st.selectbox("Entry Type", ["RIH", "NOS"], key="capture_entry_type")
    is_vehicle = st.checkbox("This entry is a vehicle", key="capture_is_vehicle")

    storage_type = "vehicle_pound" if is_vehicle else "goods"
    storage_options = warehouses_for_port(user["port_code"], warehouse_type=storage_type)
    storage_label = "Pound" if is_vehicle else "Warehouse"
    storage_choices = {
        f"{w['warehouse_name']} ({w['current_occupancy']}/{w['capacity']}" + (", FULL)" if w["is_full"] else ")"): w["warehouse_id"]
        for w in storage_options
    }

    with st.form("capture_entry_form"):
        st.markdown(f"**{storage_label} Assignment**")
        storage_choice = st.selectbox(storage_label, list(storage_choices.keys())) if storage_choices else None
        warehouse_registry_number = st.text_input("Warehouse Registry Number")

        st.markdown("**Entry Details**")
        col1, col2 = st.columns(2)
        with col1:
            entry_number = st.text_input("Entry Number")
            nos_or_rih_number = st.text_input(f"{entry_type} Number")
        with col2:
            declared_value = st.number_input("Declared / Assessed Value (USD)", min_value=0.0, step=0.01)
            quantity_units = st.text_input("Quantity / Unit of Measure")

        goods_description = st.text_area("Exact Description of Goods")
        col3, col4 = st.columns(2)
        with col3:
            gross_weight = st.number_input("Gross Weight (kg)", min_value=0.0, step=0.1)
        with col4:
            net_weight = st.number_input("Net Weight (kg)", min_value=0.0, step=0.1)

        st.markdown("**Importer / Owner Details**")
        col5, col6 = st.columns(2)
        with col5:
            importer_name = st.text_input("Full Name of Importer / Owner")
            importer_id_number = st.text_input("National ID / Passport Number")
        with col6:
            importer_contact = st.text_input("Contact (Phone / Email)")
            importer_bpn_tin = st.text_input("BPN / TIN (if applicable)")
        importer_address = st.text_area("Physical / Postal Address")

        rih_fields = {}
        nos_fields = {}
        if entry_type == "RIH":
            st.markdown("**RIH — Reason for Detention**")
            rih_fields["reason_category"] = st.selectbox(
                "Reason Category",
                ["failure_to_pay_duty", "missing_permit", "pending_valuation", "other"],
            )
            rih_fields["reason_narrative"] = st.text_area("Reason (narrative)")
            rih_fields["act_clause"] = st.text_input("Applicable Act Clause")
        else:
            st.markdown("**NOS — Legal Contravention**")
            nos_fields["seizing_officer_ec_number"] = st.text_input("Seizing Officer EC Number")
            nos_fields["offence_committed"] = st.text_input("Offence Committed (e.g. Smuggling, Undervaluation)")
            nos_fields["act_section_breached"] = st.text_input("Section of Act Breached")
            nos_fields["marks_and_numbers"] = st.text_input("Marks & Numbers (shipping marks, seal numbers)")
            nos_fields["statutory_warning_acknowledged"] = st.checkbox("Statutory warning given to offender")
            nos_fields["offender_signature_received"] = st.checkbox("Offender's signature received on NOS")

        vehicle_fields = {}
        if is_vehicle:
            st.markdown("**Vehicle Specifics**")
            col7, col8 = st.columns(2)
            with col7:
                vehicle_fields["registration_number"] = st.text_input("Registration Number")
                vehicle_fields["chassis_number"] = st.text_input("Chassis Number / VIN")
                vehicle_fields["engine_number"] = st.text_input("Engine Number")
            with col8:
                vehicle_fields["make"] = st.text_input("Make")
                vehicle_fields["model"] = st.text_input("Model")
                vehicle_fields["colour"] = st.text_input("Colour")
            vehicle_fields["year_of_manufacture"] = st.number_input("Year of Manufacture", min_value=1950, max_value=2100, step=1)

        submitted = st.form_submit_button("Capture Entry", type="primary")

    if submitted:
        if not entry_number or not goods_description or not storage_choice:
            st.error("Entry Number, Goods Description, and a Warehouse/Pound are required.")
        else:
            if entry_type == "RIH":
                rih_fields["rih_number"] = nos_or_rih_number
            else:
                nos_fields["nos_number"] = nos_or_rih_number

            entry_id = capture_entry(
                entry_number=entry_number,
                entry_type=entry_type,
                port_code=user["port_code"],
                officer_id=user["user_id"],
                goods_description=goods_description,
                declared_value=declared_value,
                warehouse_id=storage_choices[storage_choice],
                warehouse_registry_number=warehouse_registry_number,
                importer_name=importer_name,
                importer_address=importer_address,
                importer_contact=importer_contact,
                importer_id_number=importer_id_number,
                importer_bpn_tin=importer_bpn_tin,
                quantity_units=quantity_units,
                gross_weight=gross_weight or None,
                net_weight=net_weight or None,
                is_vehicle=is_vehicle,
                rih_data=rih_fields if entry_type == "RIH" else None,
                nos_data=nos_fields if entry_type == "NOS" else None,
                vehicle_data=vehicle_fields if is_vehicle else None,
            )
            st.success(f"{entry_type} entry {entry_number} captured (ID {entry_id}).")


def officer_my_entries_tab(user):
    st.subheader("Entries I've captured")
    rows = entries_captured_by(user["user_id"])
    if rows:
        st.dataframe(rows, use_container_width=True)
        entry_ids = {f"{r['entry_number']} ({r['entry_type']})": r["entry_id"] for r in rows}
        chosen = st.selectbox("View full detail", list(entry_ids.keys()), key="mine_detail")
        if chosen:
            detail = get_entry_full_detail(entry_ids[chosen])
            with st.expander("Full entry detail", expanded=True):
                st.json(detail, expanded=False)
    else:
        st.info("You haven't captured any entries yet.")


def officer_warehouses_tab(user):
    st.subheader(f"Warehouses & Pounds — {user['port_code']}")
    all_storage = warehouses_for_port(user["port_code"])
    for w in all_storage:
        with st.container(border=True):
            label = "🚗 Vehicle Pound" if w["warehouse_type"] == "vehicle_pound" else "📦 Goods Warehouse"
            status = "🔴 FULL" if w["is_full"] else "🟢 Available"
            st.write(f"**{w['warehouse_name']}** — {label} — {status}")
            st.progress(min(w["current_occupancy"] / w["capacity"], 1.0))
            st.caption(f"Occupancy: {w['current_occupancy']} / {w['capacity']}")
            c1, c2 = st.columns(2)
            with c1:
                if not w["is_full"] and st.button("Mark Full", key=f"full_{w['warehouse_id']}"):
                    toggle_full(w["warehouse_id"], user["user_id"], True)
                    st.rerun()
            with c2:
                if w["is_full"] and st.button("Mark Not Full", key=f"notfull_{w['warehouse_id']}"):
                    toggle_full(w["warehouse_id"], user["user_id"], False)
                    st.rerun()
            with st.expander("View goods held here"):
                held = goods_in_warehouse(w["warehouse_id"])
                if held:
                    st.dataframe(held, use_container_width=True)
                else:
                    st.caption("Empty.")


def officer_action_tab(user):
    st.subheader(f"Request release or disposal — {user['port_code']}")
    active = active_entries_for_port(user["port_code"])
    if not active:
        st.info("No active entries at this port.")
    else:
        options = {f"{e['entry_number']} ({e['entry_type']}, status: {e['status']})": e["entry_id"] for e in active}
        with st.form("action_request"):
            choice = st.selectbox("Entry", list(options.keys()))
            action_type = st.selectbox("Action", ["release", "disposal"])
            disposal_method = None
            if action_type == "disposal":
                disposal_method = st.selectbox("Disposal Method", ["offhand_sale", "appropriation", "auction"])
            notes = st.text_area("Notes (e.g. duty/fines/rent paid, or reason for disposal)")
            submitted_action = st.form_submit_button("Submit Request", type="primary")
        if submitted_action:
            entry_id = options[choice]
            request_action(entry_id, user["user_id"], action_type, disposal_method, notes)
            st.success(f"{action_type.title()} request submitted to Supervisor for review.")


def officer_finalize_tab(user):
    st.subheader(f"Finalize approved release / disposal — {user['port_code']}")
    rows = pending_finalization(user["port_code"])
    if not rows:
        st.info("Nothing awaiting finalization.")
    else:
        for r in rows:
            with st.container(border=True):
                action_label = r["action_type"].title()
                if r["action_type"] == "disposal":
                    action_label += f" ({r['disposal_method'].replace('_', ' ')})"
                st.write(f"**{r['entry_number']}** ({r['entry_type']}) — {action_label}")
                st.caption(f"{r['goods_description']} · Declared value: {r['declared_value']}")
                with st.form(f"finalize_form_{r['request_id']}"):
                    receipt_number = st.text_input("Receipt Number")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        duty_amount = st.number_input("Duty (USD)", min_value=0.0, step=0.01, key=f"duty_{r['request_id']}")
                    with col2:
                        penalty_amount = st.number_input("Fines/Penalty (USD)", min_value=0.0, step=0.01, key=f"pen_{r['request_id']}")
                    with col3:
                        rent_amount = st.number_input("Warehouse Rent (USD)", min_value=0.0, step=0.01, key=f"rent_{r['request_id']}")
                    finalize_submitted = st.form_submit_button("Record Payment", type="primary")
                if finalize_submitted:
                    if not receipt_number:
                        st.error("Receipt number is required.")
                    else:
                        record_finalization(
                            r["request_id"], user["user_id"], receipt_number,
                            duty_amount, penalty_amount, rent_amount,
                        )
                        st.success("Payment recorded.")
                        st.rerun()


def released_sold_tab(user):
    scope_port = None if user["role_name"] in ("Manager", "Admin") else user["port_code"]
    st.subheader("Released & Sold Goods" + (f" — {scope_port}" if scope_port else " — All Ports"))

    summary = revenue_summary(scope_port)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Revenue Collected (USD)", f"{summary['total_collected']:,.2f}")
    with col2:
        st.metric("Entries Finalized", summary["total_finalized"])

    st.divider()
    rows = released_and_sold(scope_port)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No released or sold goods yet.")


# ==================== SUPERVISOR TABS ====================

def supervisor_review_tab(user):
    st.subheader(f"Release / disposal requests pending review — {user['port_code']}")
    rows = pending_supervisor_review(user["port_code"])
    if not rows:
        st.info("No requests awaiting review.")
    else:
        for r in rows:
            with st.container(border=True):
                action_label = r["action_type"].title()
                if r["action_type"] == "disposal":
                    action_label += f" ({r['disposal_method'].replace('_', ' ')})"
                st.write(f"**{r['entry_number']}** ({r['entry_type']}) — {action_label}")
                st.caption(f"{r['goods_description']} · Value: {r['declared_value']}")
                st.caption(f"Officer notes: {r['request_notes']}")
                notes = st.text_input("Supervisor notes", key=f"supnotes_{r['request_id']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve — Forward to Manager", key=f"supappr_{r['request_id']}", type="primary"):
                        supervisor_review(r["request_id"], user["user_id"], approve=True, notes=notes)
                        st.rerun()
                with c2:
                    if st.button("Reject", key=f"suprej_{r['request_id']}"):
                        supervisor_review(r["request_id"], user["user_id"], approve=False, notes=notes)
                        st.rerun()


# ==================== MANAGER TABS ====================

def manager_approvals_tab(user):
    st.subheader("Release / disposal requests pending final approval (all ports)")
    rows = pending_manager_approval()
    if not rows:
        st.info("No requests awaiting your approval.")
    else:
        for r in rows:
            with st.container(border=True):
                action_label = r["action_type"].title()
                if r["action_type"] == "disposal":
                    action_label += f" ({r['disposal_method'].replace('_', ' ')})"
                st.write(f"**{r['entry_number']}** ({r['entry_type']}) — {r['port_code']} — {action_label}")
                st.caption(f"{r['goods_description']} · Value: {r['declared_value']}")
                st.caption(f"Officer notes: {r['request_notes']} · Supervisor notes: {r['supervisor_notes']}")
                notes = st.text_input("Manager notes", key=f"mgrnotes_{r['request_id']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve & Effect", key=f"mgrappr_{r['request_id']}", type="primary"):
                        manager_decide_and_effect(r["request_id"], user["user_id"], approve=True, notes=notes)
                        st.success(f"{action_label} effected.")
                        st.rerun()
                with c2:
                    if st.button("Reject", key=f"mgrrej_{r['request_id']}"):
                        manager_decide_and_effect(r["request_id"], user["user_id"], approve=False, notes=notes)
                        st.rerun()


def warehouse_overview_tab(user):
    """Manager/Admin (all ports) or Supervisor (own port), with filtering."""
    scope_port = None if user["role_name"] in ("Manager", "Admin") else user["port_code"]
    st.caption(f"Scope: {'All ports' if scope_port is None else scope_port}")

    all_warehouses = warehouses_for_port(scope_port) if scope_port else fetch_all(
        "SELECT warehouse_id, warehouse_name FROM warehouses ORDER BY warehouse_name"
    )
    wh_choices = {"All": None}
    wh_choices.update({w["warehouse_name"]: w["warehouse_id"] for w in all_warehouses})

    col1, col2, col3 = st.columns(3)
    with col1:
        wh_pick = st.selectbox("Warehouse", list(wh_choices.keys()), key="ov_wh")
    with col2:
        date_from = st.date_input("From", value=None, key="ov_from")
    with col3:
        date_to = st.date_input("To", value=None, key="ov_to")

    sub_rih, sub_seizures, sub_summary = st.tabs(["RIH List", "Seizures List", "Monthly Summary"])

    with sub_rih:
        rows = rih_list(scope_port, wh_choices[wh_pick], date_from or None, date_to or None)
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("No RIH entries match the filters.")

    with sub_seizures:
        rows = seizures_list(scope_port, wh_choices[wh_pick], date_from or None, date_to or None)
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("No seizures match the filters.")

    with sub_summary:
        rows = monthly_summary(scope_port)
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("No data yet.")


# ==================== ADMIN TABS ====================

def admin_users_tab(user):
    st.subheader("User Management")
    with st.expander("Create a new user"):
        roles = list_roles()
        ports = list_ports()
        role_choices = {r["role_name"]: r["role_id"] for r in roles}
        port_choices = {"All ports (Admin/Manager)": None}
        port_choices.update({p["port_name"]: p["port_code"] for p in ports})
        with st.form("create_user_form"):
            full_name = st.text_input("Full Name")
            username = st.text_input("Username (email)")
            plain_password = st.text_input("Temporary Password", type="password")
            role_pick = st.selectbox("Role", list(role_choices.keys()))
            port_pick = st.selectbox("Port", list(port_choices.keys()))
            create_submitted = st.form_submit_button("Create User", type="primary")
        if create_submitted:
            if not full_name or not username or not plain_password:
                st.error("Full name, username, and password are required.")
            else:
                create_user(full_name, username, plain_password, role_choices[role_pick], port_choices[port_pick])
                st.success(f"User {username} created.")
                st.rerun()

    st.divider()
    rows = list_users()
    if rows:
        st.dataframe(rows, use_container_width=True)
        user_choices = {f"{u['full_name']} ({u['username']})": u["user_id"] for u in rows}
        chosen = st.selectbox("Manage user", list(user_choices.keys()), key="admin_manage_user")
        chosen_id = user_choices[chosen]
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Deactivate", key="deactivate_user"):
                set_user_active(chosen_id, False)
                st.rerun()
            if st.button("Reactivate", key="reactivate_user"):
                set_user_active(chosen_id, True)
                st.rerun()
        with c2:
            new_pw = st.text_input("New password", type="password", key="reset_pw_input")
            if st.button("Reset Password", key="reset_pw_btn") and new_pw:
                reset_password(chosen_id, new_pw)
                st.success("Password reset.")
        with c3:
            if st.button("Delete User", key="delete_user_btn"):
                delete_user(chosen_id)
                st.rerun()
    else:
        st.info("No users found.")


def admin_entry_correction_tab(user):
    st.subheader("Entry Correction")
    query = st.text_input("Search by entry number or description")
    if query:
        rows = search_entries(query)
        if rows:
            st.dataframe(rows, use_container_width=True)
            entry_choices = {f"{r['entry_number']} ({r['entry_type']})": r["entry_id"] for r in rows}
            chosen = st.selectbox("Entry to correct", list(entry_choices.keys()), key="admin_correct_entry")
            entry_id = entry_choices[chosen]
            with st.form("correct_entry_form"):
                new_entry_number = st.text_input("New Entry Number (leave blank to keep)")
                new_description = st.text_area("New Goods Description (leave blank to keep)")
                new_value = st.number_input("New Declared Value (0 = keep)", min_value=0.0, step=0.01)
                reason = st.text_area("Reason for correction")
                correct_submitted = st.form_submit_button("Apply Correction", type="primary")
            if correct_submitted:
                fields = {}
                if new_entry_number:
                    fields["entry_number"] = new_entry_number
                if new_description:
                    fields["goods_description"] = new_description
                if new_value:
                    fields["declared_value"] = new_value
                if not fields:
                    st.warning("No fields changed.")
                else:
                    correct_entry(entry_id, user["user_id"], fields, reason)
                    st.success("Entry corrected.")
                    st.rerun()
        else:
            st.info("No matching entries.")


def admin_audit_tab(user):
    st.subheader("Audit Trail")
    detained = detained_goods_with_officer()
    st.markdown("**Detained goods currently active, with responsible officer**")
    if detained:
        st.dataframe(detained, use_container_width=True)
    else:
        st.info("No active detained goods.")

    st.divider()
    st.markdown("**Recent audit log (all entries)**")
    logs = audit_trail()
    if logs:
        st.dataframe(logs, use_container_width=True)
    else:
        st.info("No audit records yet.")


def admin_messages_tab(user):
    st.subheader("Message Moderation")
    rows = list_all_messages()
    if not rows:
        st.info("No messages.")
    else:
        for m in rows:
            with st.container(border=True):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**{m['sender_name']}** · {m['created_at']}")
                    if m["subject"]:
                        st.markdown(f"*{m['subject']}*")
                    st.write(m["body"])
                    st.caption(f"Scope: {m['recipient_scope']}" + (f" · Role: {m['recipient_role']}" if m['recipient_role'] else ""))
                with col2:
                    if st.button("Delete", key=f"delmsg_{m['message_id']}"):
                        delete_message(m["message_id"])
                        st.rerun()


def admin_statistics_tab(user):
    st.subheader("Statistics")
    rev = revenue_stats()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Revenue Collected (USD)", f"{rev['total_collected']:,.2f}")
    with col2:
        st.metric("Releases Completed", rev["releases_completed"])

    st.divider()
    st.markdown("**Warehouse usage**")
    usage = warehouse_usage_stats()
    if usage:
        st.dataframe(usage, use_container_width=True)

    st.divider()
    st.markdown("**Days until expiry (RIH)**")
    expiry = days_until_expiry_report()
    if expiry:
        st.dataframe(expiry, use_container_width=True)
    else:
        st.info("No active RIH entries.")


# ==================== DASHBOARD ROUTER ====================

def role_dashboard():
    user = st.session_state.user
    render_sidebar(user)

    st.title(f"{user['role_name']} Dashboard")

    st.subheader("Entries nearing expiry / overdue")
    rows = entries_nearing_expiry(warning_window_days=2)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No entries nearing expiry.")
    st.divider()

    if user["role_name"] == "Officer":
        tabs = st.tabs([
            "Capture Entry", "My Captured Entries", "Warehouses & Pounds",
            "Request Release / Disposal", "Finalize Payment", "Released & Sold",
        ])
        with tabs[0]:
            officer_capture_tab(user)
        with tabs[1]:
            officer_my_entries_tab(user)
        with tabs[2]:
            officer_warehouses_tab(user)
        with tabs[3]:
            officer_action_tab(user)
        with tabs[4]:
            officer_finalize_tab(user)
        with tabs[5]:
            released_sold_tab(user)

    elif user["role_name"] == "Supervisor":
        tabs = st.tabs(["Review Requests", "Warehouse Overview", "Released & Sold"])
        with tabs[0]:
            supervisor_review_tab(user)
        with tabs[1]:
            warehouse_overview_tab(user)
        with tabs[2]:
            released_sold_tab(user)

    elif user["role_name"] == "Manager":
        tabs = st.tabs(["Final Approvals", "Warehouse Overview", "Released & Sold"])
        with tabs[0]:
            manager_approvals_tab(user)
        with tabs[1]:
            warehouse_overview_tab(user)
        with tabs[2]:
            released_sold_tab(user)

    elif user["role_name"] == "Admin":
        tabs = st.tabs(["Users", "Entry Correction", "Audit Trail", "Messages", "Statistics", "Warehouse Overview"])
        with tabs[0]:
            admin_users_tab(user)
        with tabs[1]:
            admin_entry_correction_tab(user)
        with tabs[2]:
            admin_audit_tab(user)
        with tabs[3]:
            admin_messages_tab(user)
        with tabs[4]:
            admin_statistics_tab(user)
        with tabs[5]:
            warehouse_overview_tab(user)

    else:
        st.info("No dashboard tabs configured for this role yet.")


# Restore session from URL token if the page was refreshed
if st.session_state.user is None:
    token = st.query_params.get("token")
    if token:
        restored_user = get_user_by_session(token)
        if restored_user:
            st.session_state.user = restored_user

if st.session_state.user is None:
    login_screen()
else:
    role_dashboard()
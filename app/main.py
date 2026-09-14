"""
WMS-Trak — Streamlit entry point.

Single dashboard page with horizontal, role-scoped tabs. The sidebar
only ever shows Notifications, About the Authors, User Manual (separate
pages) plus the Account dropdown from app/theme.py. Login persists
across page refreshes via a URL-token-backed session (see app/auth.py).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from app.auth import (
    verify_login, create_session, get_user_by_session,
    is_valid_zimra_email, is_strong_password, password_requirements_text,
    submit_profile_request, find_active_user_by_email, reset_password_self_service,
    pending_profile_requests, approve_profile_request, reject_profile_request,
)
from app.admin import (
    list_users, list_roles, list_ports, create_user, set_user_active,
    reset_password, delete_user, search_entries, correct_entry,
    audit_trail, detained_goods_with_officer, delete_message,
    list_all_messages, revenue_stats, warehouse_usage_stats, days_until_expiry_report,
    get_user_by_id, update_user,
)
from app.bond_engine import entries_nearing_expiry
from app.theme import render_sidebar, inject_global_css, clear_form_keys
from app.entries import capture_entry, entries_captured_by, active_entries_for_port, get_entry_full_detail
from app.action_requests import (
    request_release_to_owner, request_forfeiture, request_destruction, request_eauction,
    pending_supervisor_review, supervisor_review,
    pending_manager_approval, manager_decide,
    pending_officer_finalization,
    finalize_release_to_owner, finalize_forfeiture, finalize_destruction, finalize_eauction,
)
from app.warehouses import warehouses_for_port, toggle_full, goods_in_warehouse
from app.warehouse_views import rih_list, seizures_list, monthly_summary
from app.revenue import released_and_sold, revenue_summary
from app.db import fetch_all

st.set_page_config(page_title="WMS-Trak", page_icon="🏛️", layout="wide")
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
    </style>
    """,
    unsafe_allow_html=True,
)


def login_screen():
    st.markdown(
        """
        <style>
        .main .block-container {
            max-width: 460px !important;
            margin: 3rem auto !important;
            padding: 0 1rem !important;
        }
        div[data-testid="stImage"] {
            display: flex;
            justify-content: center;
        }
        div.stForm {
            border: 1px solid #e0e0e0;
            border-radius: 18px;
            padding: 2rem 1.5rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
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
        username = st.text_input("Username", label_visibility="collapsed", placeholder="ZIMRA Email (@zimra.co.zw)")
        password = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        submitted = st.form_submit_button("SIGN IN", type="primary", use_container_width=True)
    if submitted:
        if not is_valid_zimra_email(username):
            st.error("Please sign in with a valid ZIMRA email address (@zimra.co.zw).")
        else:
            user = verify_login(username, password)
            if user:
                token = create_session(user["user_id"])
                st.query_params["token"] = token
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials or inactive account.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Request a Profile", use_container_width=True):
            st.session_state.auth_view = "request_profile"
            st.rerun()
    with col2:
        if st.button("Forgot Password?", use_container_width=True):
            st.session_state.auth_view = "forgot_password"
            st.rerun()


def request_profile_screen():
    st.markdown("<h2 style='text-align:center;'>Request a Profile</h2>", unsafe_allow_html=True)
    st.write("Submit your details below, including the password you'd like to use. An Admin will review your request — you'll be able to sign in with this password once it's approved, typically within 24 hours.")

    roles = list_roles()
    ports = list_ports()
    role_names = [r["role_name"] for r in roles if r["role_name"] != "Admin"]
    port_choices = {"All ports / Not applicable": None}
    port_choices.update({p["port_name"]: p["port_code"] for p in ports})

    with st.form("request_profile_form"):
        full_name = st.text_input("Full Name")
        email = st.text_input("ZIMRA Email (@zimra.co.zw)")
        phone_number = st.text_input("Phone Number")
        requested_role = st.selectbox("Requested Role", role_names)
        requested_port_label = st.selectbox("Station", list(port_choices.keys()))
        reason = st.text_area("Reason for Request")
        password = st.text_input("Choose a Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        st.caption(password_requirements_text())
        submitted = st.form_submit_button("Submit Request", type="primary", use_container_width=True)

    if submitted:
        if not full_name or not email or not password:
            st.error("Full name, email, and password are required.")
        elif not is_valid_zimra_email(email):
            st.error("Only @zimra.co.zw email addresses are accepted — gmail and other domains are not allowed.")
        elif password != confirm_password:
            st.error("Passwords do not match.")
        elif not is_strong_password(password):
            st.error(password_requirements_text())
        else:
            try:
                submit_profile_request(
                    full_name, email, phone_number, requested_role,
                    port_choices[requested_port_label], reason, password,
                )
                st.success("Your profile request has been submitted and will be reviewed within 24 hours. You'll be able to sign in with the password you chose once it's approved.")
            except ValueError as e:
                st.error(str(e))

    if st.button("← Back to Sign In"):
        st.session_state.auth_view = None
        st.rerun()


def forgot_password_screen():
    st.markdown("<h2 style='text-align:center;'>Forgot Password</h2>", unsafe_allow_html=True)

    if "reset_verified_user_id" not in st.session_state:
        st.session_state.reset_verified_user_id = None

    if not st.session_state.reset_verified_user_id:
        st.write("Enter your ZIMRA email to continue.")
        with st.form("verify_email_form"):
            email = st.text_input("ZIMRA Email (@zimra.co.zw)")
            verify_submitted = st.form_submit_button("Verify Email", type="primary", use_container_width=True)
        if verify_submitted:
            if not is_valid_zimra_email(email):
                st.error("Please enter a valid @zimra.co.zw email address.")
            else:
                found = find_active_user_by_email(email)
                if found:
                    st.session_state.reset_verified_user_id = found["user_id"]
                    st.session_state.reset_verified_name = found["full_name"]
                    st.rerun()
                else:
                    st.error("No active account found with that email.")
    else:
        st.write(f"Account verified: **{st.session_state.reset_verified_name}**. Enter a new password below.")
        st.caption(password_requirements_text())
        with st.form("new_password_form"):
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            reset_submitted = st.form_submit_button("Reset Password", type="primary", use_container_width=True)
        if reset_submitted:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            elif not is_strong_password(new_password):
                st.error(password_requirements_text())
            else:
                reset_password_self_service(st.session_state.reset_verified_user_id, new_password)
                st.success("Password reset successfully. You can now sign in.")
                st.session_state.reset_verified_user_id = None
                st.session_state.auth_view = None

    if st.button("← Back to Sign In"):
        st.session_state.reset_verified_user_id = None
        st.session_state.auth_view = None
        st.rerun()


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

    form_keys = [
        "cap_storage_choice", "cap_entry_number", "cap_type_number",
        "cap_declared_value", "cap_quantity_units", "cap_goods_description",
        "cap_gross_weight", "cap_net_weight", "cap_weight_unit",
        "cap_rent_per_day", "cap_exchange_rate", "cap_expiry_date",
        "cap_importer_name", "cap_importer_id", "cap_importer_contact",
        "cap_importer_bpn", "cap_importer_address",
        "cap_rih_reason_cat", "cap_rih_reason_narr", "cap_rih_act_clause",
        "cap_nos_ec", "cap_nos_offence", "cap_nos_section", "cap_nos_marks",
        "cap_nos_warning", "cap_nos_signature",
        "cap_veh_reg", "cap_veh_chassis", "cap_veh_engine",
        "cap_veh_make", "cap_veh_model", "cap_veh_colour", "cap_veh_year",
    ]

    with st.form("capture_entry_form"):
        st.markdown(f"**{storage_label} Assignment**")
        storage_choice = st.selectbox(storage_label, list(storage_choices.keys()), key="cap_storage_choice") if storage_choices else None

        st.markdown("**Entry Details**")
        col1, col2 = st.columns(2)
        with col1:
            entry_number = st.text_input("Entry Number", key="cap_entry_number")
            nos_or_rih_number = st.text_input(f"{entry_type} Number", key="cap_type_number")
        with col2:
            declared_value = st.number_input("Declared / Assessed Value (USD)", min_value=0.0, step=0.01, key="cap_declared_value")
            quantity_units = st.text_input("Quantity / Unit of Measure", key="cap_quantity_units")

        goods_description = st.text_area("Exact Description of Goods", key="cap_goods_description")

        col3, col4, col5 = st.columns(3)
        with col3:
            gross_weight = st.number_input("Gross Weight", min_value=0.0, step=0.1, key="cap_gross_weight")
        with col4:
            net_weight = st.number_input("Net Weight", min_value=0.0, step=0.1, key="cap_net_weight")
        with col5:
            weight_unit = st.selectbox("Weight Unit", ["kg", "tonnes", "litres", "grams"], key="cap_weight_unit")

        st.markdown("**Financial & Compliance Details**")
        col6, col7, col8 = st.columns(3)
        with col6:
            rent_charge_per_day = st.number_input("Rent Charge per Day (USD)", min_value=0.0, step=0.01, key="cap_rent_per_day")
        with col7:
            exchange_rate_zwg_usd = st.number_input("Exchange Rate (ZWG to USD)", min_value=0.0, step=0.0001, format="%.4f", key="cap_exchange_rate")
        with col8:
            expiry_date = st.date_input("Expiry Date of Goods (if applicable)", value=None, key="cap_expiry_date")

        st.markdown("**Importer / Owner Details**")
        col9, col10 = st.columns(2)
        with col9:
            importer_name = st.text_input("Full Name of Importer / Owner", key="cap_importer_name")
            importer_id_number = st.text_input("National ID / Passport Number", key="cap_importer_id")
        with col10:
            importer_contact = st.text_input("Contact (Phone / Email)", key="cap_importer_contact")
            importer_bpn_tin = st.text_input("BPN / TIN (if applicable)", key="cap_importer_bpn")
        importer_address = st.text_area("Physical / Postal Address", key="cap_importer_address")

        rih_fields = {}
        nos_fields = {}
        if entry_type == "RIH":
            st.markdown("**RIH — Reason for Detention**")
            rih_fields["reason_category"] = st.selectbox(
                "Reason Category",
                ["failure_to_pay_duty", "missing_permit", "pending_valuation", "other"],
                key="cap_rih_reason_cat",
            )
            rih_fields["reason_narrative"] = st.text_area("Reason (narrative)", key="cap_rih_reason_narr")
            rih_fields["act_clause"] = st.text_input("Applicable Act Clause", key="cap_rih_act_clause")
        else:
            st.markdown("**NOS — Legal Contravention**")
            nos_fields["seizing_officer_ec_number"] = st.text_input("Seizing Officer EC Number", key="cap_nos_ec")
            nos_fields["offence_committed"] = st.text_input("Offence Committed (e.g. Smuggling, Undervaluation)", key="cap_nos_offence")
            nos_fields["act_section_breached"] = st.text_input("Section of Act Breached", key="cap_nos_section")
            nos_fields["marks_and_numbers"] = st.text_input("Marks & Numbers (shipping marks, seal numbers)", key="cap_nos_marks")
            nos_fields["statutory_warning_acknowledged"] = st.checkbox("Statutory warning given to offender", key="cap_nos_warning")
            nos_fields["offender_signature_received"] = st.checkbox("Offender's signature received on NOS", key="cap_nos_signature")

        vehicle_fields = {}
        if is_vehicle:
            st.markdown("**Vehicle Specifics**")
            col11, col12 = st.columns(2)
            with col11:
                vehicle_fields["registration_number"] = st.text_input("Registration Number", key="cap_veh_reg")
                vehicle_fields["chassis_number"] = st.text_input("Chassis Number / VIN", key="cap_veh_chassis")
                vehicle_fields["engine_number"] = st.text_input("Engine Number", key="cap_veh_engine")
            with col12:
                vehicle_fields["make"] = st.text_input("Make", key="cap_veh_make")
                vehicle_fields["model"] = st.text_input("Model", key="cap_veh_model")
                vehicle_fields["colour"] = st.text_input("Colour", key="cap_veh_colour")
            vehicle_fields["year_of_manufacture"] = st.number_input("Year of Manufacture", min_value=1950, max_value=2100, step=1, key="cap_veh_year")

        submitted = st.form_submit_button("Capture Entry", type="primary")

    if submitted:
        if not entry_number or not goods_description or not storage_choice:
            st.error("Entry Number, Goods Description, and a Warehouse/Pound are required. Your other entries have been kept — please fill in what's missing and submit again.")
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
                importer_name=importer_name,
                importer_address=importer_address,
                importer_contact=importer_contact,
                importer_id_number=importer_id_number,
                importer_bpn_tin=importer_bpn_tin,
                quantity_units=quantity_units,
                gross_weight=gross_weight or None,
                net_weight=net_weight or None,
                weight_unit=weight_unit,
                rent_charge_per_day=rent_charge_per_day,
                exchange_rate_zwg_usd=exchange_rate_zwg_usd or None,
                expiry_date=expiry_date,
                is_vehicle=is_vehicle,
                rih_data=rih_fields if entry_type == "RIH" else None,
                nos_data=nos_fields if entry_type == "NOS" else None,
                vehicle_data=vehicle_fields if is_vehicle else None,
            )
            st.success(f"{entry_type} entry {entry_number} captured (ID {entry_id}). Form cleared for the next entry.")
            clear_form_keys(form_keys)
            st.rerun()


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
    st.subheader(f"Request an action — {user['port_code']}")
    active = active_entries_for_port(user["port_code"])
    if not active:
        st.info("No active entries at this port.")
        return

    options = {f"{e['entry_number']} ({e['entry_type']}, status: {e['status']})": e["entry_id"] for e in active}
    action_type = st.selectbox(
        "Action Type",
        ["release_to_owner", "forfeiture", "destruction", "e_auction"],
        format_func=lambda x: x.replace("_", " ").title(),
        key="req_action_type",
    )

    form_keys = [
        "req_entry_choice", "req_notes", "req_ministry_name", "req_letter_ref",
        "req_ph_officer", "req_ph_reference", "req_destruction_reason",
    ]

    with st.form("action_request_form"):
        choice = st.selectbox("Entry", list(options.keys()), key="req_entry_choice")
        notes = st.text_area("Notes", key="req_notes")

        ministry_name = request_letter_reference = None
        port_health_officer_name = port_health_approval_reference = reason_for_destruction = None

        if action_type == "forfeiture":
            st.markdown("**Forfeiture — Ministry Details**")
            ministry_name = st.text_input("Ministry Requesting Appropriation", key="req_ministry_name")
            request_letter_reference = st.text_area("Letter / Document Reference (attach details or reference number)", key="req_letter_ref")
        elif action_type == "destruction":
            st.markdown("**Destruction — Port Health Approval**")
            port_health_officer_name = st.text_input("Approving Port Health Officer", key="req_ph_officer")
            port_health_approval_reference = st.text_input("Port Health Approval Reference", key="req_ph_reference")
            reason_for_destruction = st.text_area("Reason for Destruction (e.g. expired, dangerous, perishable, prohibited)", key="req_destruction_reason")

        req_submitted = st.form_submit_button("Submit Request", type="primary")

    if req_submitted:
        entry_id = options[choice]
        if action_type == "release_to_owner":
            request_release_to_owner(entry_id, user["user_id"], notes)
        elif action_type == "forfeiture":
            if not ministry_name:
                st.error("Ministry name is required for forfeiture. Your other entries have been kept.")
                return
            request_forfeiture(entry_id, user["user_id"], ministry_name, request_letter_reference, notes)
        elif action_type == "destruction":
            if not port_health_officer_name or not reason_for_destruction:
                st.error("Port Health officer and reason for destruction are required. Your other entries have been kept.")
                return
            request_destruction(entry_id, user["user_id"], port_health_officer_name,
                                 port_health_approval_reference, reason_for_destruction, notes)
        elif action_type == "e_auction":
            request_eauction(entry_id, user["user_id"], notes)
        st.success(f"{action_type.replace('_', ' ').title()} request submitted to Supervisor for review. Form cleared.")
        clear_form_keys(form_keys)
        st.rerun()


def officer_finalize_tab(user):
    st.subheader(f"Finalize manager-approved actions — {user['port_code']}")
    rows = pending_officer_finalization(user["port_code"])
    if not rows:
        st.info("Nothing awaiting finalization.")
        return

    for r in rows:
        with st.container(border=True):
            st.write(f"**{r['entry_number']}** ({r['entry_type']}) — {r['action_type'].replace('_', ' ').title()}")
            st.caption(f"{r['goods_description']} · Declared value: {r['declared_value']}")

            if r["action_type"] == "release_to_owner":
                with st.form(f"finalize_release_{r['request_id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        duty_paid = st.number_input("Duty Paid (USD)", min_value=0.0, step=0.01, key=f"duty_{r['request_id']}")
                    with c2:
                        additional_duty = st.number_input("Additional Duty (USD)", min_value=0.0, step=0.01, key=f"adduty_{r['request_id']}")
                    with c3:
                        rent_paid = st.number_input("Rent Paid (USD)", min_value=0.0, step=0.01, key=f"rentpaid_{r['request_id']}")
                    st.caption(f"System rent rate: {r['rent_charge_per_day']} USD/day — actual rent will be auto-calculated from days in warehouse.")
                    receipt_number = st.text_input("Receipt Number", key=f"receipt_{r['request_id']}")
                    y_number = st.text_input("Y Number", key=f"ynum_{r['request_id']}")
                    clearance_details = st.text_area("Further Clearance Details", key=f"clear_{r['request_id']}")
                    submit = st.form_submit_button("Save Final Release", type="primary")
                if submit:
                    if not receipt_number:
                        st.error("Receipt number is required.")
                    else:
                        rent_calc = finalize_release_to_owner(
                            r["request_id"], user["user_id"], duty_paid, additional_duty,
                            rent_paid, receipt_number, y_number, clearance_details,
                        )
                        st.success(f"Release finalized. System-calculated rent: {rent_calc:.2f} USD.")
                        st.rerun()

            elif r["action_type"] == "forfeiture":
                td = r.get("type_detail") or {}
                st.caption(f"Ministry: {td.get('ministry_name')} · Reference: {td.get('request_letter_reference')}")
                with st.form(f"finalize_forfeit_{r['request_id']}"):
                    representative_name = st.text_input("Representative Name", key=f"repname_{r['request_id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        representative_id_number = st.text_input("Representative ID Number", key=f"repid_{r['request_id']}")
                    with c2:
                        representative_occupation = st.text_input("Representative Occupation", key=f"repocc_{r['request_id']}")
                    goods_or_vehicle_finalization_details = st.text_area("Goods / Vehicle Final Details", key=f"gvdet_{r['request_id']}")
                    submit = st.form_submit_button("Save Final Appropriation", type="primary")
                if submit:
                    if not representative_name:
                        st.error("Representative name is required.")
                    else:
                        finalize_forfeiture(
                            r["request_id"], user["user_id"], representative_name,
                            representative_id_number, representative_occupation,
                            goods_or_vehicle_finalization_details,
                        )
                        st.success("Appropriation finalized.")
                        st.rerun()

            elif r["action_type"] == "destruction":
                td = r.get("type_detail") or {}
                st.caption(f"Port Health: {td.get('port_health_officer_name')} · Reason: {td.get('reason_for_destruction')}")
                with st.form(f"finalize_destroy_{r['request_id']}"):
                    destruction_date = st.date_input("Date of Destruction", key=f"ddate_{r['request_id']}")
                    destruction_place = st.text_input("Place of Destruction", key=f"dplace_{r['request_id']}")
                    stakeholders_present = st.text_area(
                        "Stakeholders Present (e.g. Police rep, Port Health rep, Army rep, other officers)",
                        key=f"dstake_{r['request_id']}",
                    )
                    submit = st.form_submit_button("Save Destruction Record", type="primary")
                if submit:
                    if not destruction_place:
                        st.error("Place of destruction is required.")
                    else:
                        finalize_destruction(
                            r["request_id"], user["user_id"], destruction_date,
                            destruction_place, stakeholders_present,
                        )
                        st.success("Destruction finalized.")
                        st.rerun()

            elif r["action_type"] == "e_auction":
                with st.form(f"finalize_auction_{r['request_id']}"):
                    revenue_collected = st.number_input("Revenue Collected (USD)", min_value=0.0, step=0.01, key=f"rev_{r['request_id']}")
                    buyer_details = st.text_area("Buyer Details", key=f"buyer_{r['request_id']}")
                    receipt_number = st.text_input("Receipt Number", key=f"areceipt_{r['request_id']}")
                    submit = st.form_submit_button("Save Sale", type="primary")
                if submit:
                    if not receipt_number:
                        st.error("Receipt number is required.")
                    else:
                        finalize_eauction(r["request_id"], user["user_id"], revenue_collected, buyer_details, receipt_number)
                        st.success("E-Auction sale finalized.")
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
    st.subheader(f"Requests pending review — {user['port_code']}")
    rows = pending_supervisor_review(user["port_code"])
    if not rows:
        st.info("No requests awaiting review.")
    else:
        for r in rows:
            with st.container(border=True):
                st.write(f"**{r['entry_number']}** ({r['entry_type']}) — {r['action_type'].replace('_', ' ').title()}")
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
    st.subheader("Requests pending final approval (all ports)")
    rows = pending_manager_approval()
    if not rows:
        st.info("No requests awaiting your approval.")
    else:
        for r in rows:
            with st.container(border=True):
                st.write(f"**{r['entry_number']}** ({r['entry_type']}) — {r['port_code']} — {r['action_type'].replace('_', ' ').title()}")
                st.caption(f"{r['goods_description']} · Value: {r['declared_value']}")
                st.caption(f"Officer notes: {r['request_notes']} · Supervisor notes: {r['supervisor_notes']}")
                notes = st.text_input("Manager notes", key=f"mgrnotes_{r['request_id']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve", key=f"mgrappr_{r['request_id']}", type="primary"):
                        manager_decide(r["request_id"], user["user_id"], approve=True, notes=notes)
                        st.success("Approved — Officer may now proceed and finalize the details.")
                        st.rerun()
                with c2:
                    if st.button("Reject", key=f"mgrrej_{r['request_id']}"):
                        manager_decide(r["request_id"], user["user_id"], approve=False, notes=notes)
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

def admin_profile_requests_tab(user):
    st.subheader("Profile Requests")

    feedback = st.session_state.pop("admin_profile_feedback", None)
    if feedback:
        kind, message = feedback
        if kind == "success":
            st.success(message)
        else:
            st.error(message)

    rows = pending_profile_requests()
    if not rows:
        st.info("No pending profile requests.")
        return

    roles = list_roles()
    ports = list_ports()
    role_choices = {r["role_name"]: r["role_id"] for r in roles}
    port_choices = {"All ports (Admin/Manager)": None}
    port_choices.update({p["port_name"]: p["port_code"] for p in ports})

    for req in rows:
        with st.container(border=True):
            st.write(f"**{req['full_name']}** ({req['email']})")
            st.caption(f"Requested role: {req['requested_role']} · Phone: {req['phone_number']}")
            st.caption(f"Reason: {req['reason']}")

            default_role_index = list(role_choices.keys()).index(req["requested_role"]) if req["requested_role"] in role_choices else 0

            with st.form(f"approve_form_{req['request_id']}"):
                role_pick = st.selectbox("Assign Role", list(role_choices.keys()), index=default_role_index, key=f"pr_role_{req['request_id']}")
                port_pick = st.selectbox("Assign Port", list(port_choices.keys()), key=f"pr_port_{req['request_id']}")
                notes = st.text_input("Notes (optional)", key=f"pr_notes_{req['request_id']}")
                c1, c2 = st.columns(2)
                with c1:
                    approve_submitted = st.form_submit_button("Approve", type="primary")
                with c2:
                    reject_submitted = st.form_submit_button("Reject")

            if approve_submitted:
                try:
                    approve_profile_request(
                        req["request_id"], user["user_id"], role_choices[role_pick],
                        port_choices[port_pick], notes,
                    )
                    st.session_state.admin_profile_feedback = ("success", f"Profile approved — account created for {req['email']}.")
                except ValueError as e:
                    st.session_state.admin_profile_feedback = ("error", str(e))
                st.rerun()

            if reject_submitted:
                reject_profile_request(req["request_id"], user["user_id"], notes)
                st.session_state.admin_profile_feedback = ("success", f"Request from {req['email']} has been rejected.")
                st.rerun()


def admin_users_tab(user):
    st.subheader("User Management")

    feedback = st.session_state.pop("admin_user_feedback", None)
    if feedback:
        kind, message = feedback
        if kind == "success":
            st.success(message)
        else:
            st.error(message)

    with st.expander("Create a new user"):
        roles = list_roles()
        ports = list_ports()
        role_choices = {r["role_name"]: r["role_id"] for r in roles}
        port_choices = {"All ports (Admin/Manager)": None}
        port_choices.update({p["port_name"]: p["port_code"] for p in ports})
        with st.form("create_user_form"):
            full_name = st.text_input("Full Name", key="cu_full_name")
            username = st.text_input("Username (ZIMRA email, @zimra.co.zw)", key="cu_username")
            plain_password = st.text_input("Temporary Password", type="password", key="cu_password")
            st.caption(password_requirements_text())
            role_pick = st.selectbox("Role", list(role_choices.keys()), key="cu_role")
            port_pick = st.selectbox("Port", list(port_choices.keys()), key="cu_port")
            create_submitted = st.form_submit_button("Create User", type="primary")
        if create_submitted:
            if not full_name or not username or not plain_password:
                st.error("Full name, username, and password are required. Your other entries have been kept.")
            elif not is_valid_zimra_email(username):
                st.error("Username must be a valid @zimra.co.zw email address. Your other entries have been kept.")
            elif not is_strong_password(plain_password):
                st.error(password_requirements_text() + " Your other entries have been kept.")
            else:
                create_user(full_name, username, plain_password, role_choices[role_pick], port_choices[port_pick])
                st.success(f"User {username} created. Form cleared.")
                clear_form_keys(["cu_full_name", "cu_username", "cu_password", "cu_role", "cu_port"])
                st.rerun()

    st.divider()
    rows = list_users()
    if not rows:
        st.info("No users found.")
        return

    st.dataframe(rows, use_container_width=True)
    user_choices = {f"{u['full_name']} ({u['username']})": u["user_id"] for u in rows}
    chosen = st.selectbox("Manage user", list(user_choices.keys()), key="admin_manage_user")
    chosen_id = user_choices[chosen]
    detail = get_user_by_id(chosen_id)

    with st.expander(f"Edit Profile — {detail['full_name']}"):
        roles = list_roles()
        ports = list_ports()
        role_choices = {r["role_name"]: r["role_id"] for r in roles}
        port_choices = {"All ports (Admin/Manager)": None}
        port_choices.update({p["port_name"]: p["port_code"] for p in ports})
        role_names = list(role_choices.keys())
        port_names = list(port_choices.keys())
        current_role_index = role_names.index(detail["role_name"]) if detail["role_name"] in role_names else 0
        current_port_name = next((name for name, code in port_choices.items() if code == detail["port_code"]), port_names[0])
        current_port_index = port_names.index(current_port_name)

        with st.form(f"edit_user_form_{chosen_id}"):
            edit_full_name = st.text_input("Full Name", value=detail["full_name"])
            edit_username = st.text_input("Username (ZIMRA email)", value=detail["username"])
            edit_phone = st.text_input("Phone Number", value=detail["phone_number"] or "")
            edit_role = st.selectbox("Role", role_names, index=current_role_index)
            edit_port = st.selectbox("Port", port_names, index=current_port_index)
            edit_submitted = st.form_submit_button("Save Changes", type="primary")

        if edit_submitted:
            if not edit_full_name or not edit_username:
                st.session_state.admin_user_feedback = ("error", "Full name and username are required.")
            elif not is_valid_zimra_email(edit_username):
                st.session_state.admin_user_feedback = ("error", "Username must be a valid @zimra.co.zw email address.")
            else:
                update_user(chosen_id, edit_full_name, edit_username, role_choices[edit_role], port_choices[edit_port], edit_phone)
                st.session_state.admin_user_feedback = ("success", f"Profile updated for {edit_full_name}.")
            st.rerun()

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Deactivate", key="deactivate_user"):
            set_user_active(chosen_id, False)
            st.session_state.admin_user_feedback = ("success", f"{detail['full_name']} deactivated.")
            st.rerun()
        if st.button("Reactivate", key="reactivate_user"):
            set_user_active(chosen_id, True)
            st.session_state.admin_user_feedback = ("success", f"{detail['full_name']} reactivated.")
            st.rerun()
    with c2:
        new_pw = st.text_input("New password", type="password", key="reset_pw_input")
        if st.button("Reset Password", key="reset_pw_btn") and new_pw:
            if not is_strong_password(new_pw):
                st.session_state.admin_user_feedback = ("error", password_requirements_text())
            else:
                reset_password(chosen_id, new_pw)
                st.session_state.admin_user_feedback = ("success", f"Password reset for {detail['full_name']}.")
            st.rerun()
    with c3:
        if st.button("Delete User", key="delete_user_btn"):
            try:
                delete_user(chosen_id)
                st.session_state.admin_user_feedback = ("success", f"{detail['full_name']} permanently deleted.")
            except ValueError as e:
                st.session_state.admin_user_feedback = ("error", str(e))
            st.rerun()


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
            "Request Action", "Finalize Action", "Released & Sold",
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
        tabs = st.tabs([
            "Profile Requests", "Users", "Entry Correction", "Audit Trail",
            "Messages", "Statistics", "Warehouse Overview",
        ])
        with tabs[0]:
            admin_profile_requests_tab(user)
        with tabs[1]:
            admin_users_tab(user)
        with tabs[2]:
            admin_entry_correction_tab(user)
        with tabs[3]:
            admin_audit_tab(user)
        with tabs[4]:
            admin_messages_tab(user)
        with tabs[5]:
            admin_statistics_tab(user)
        with tabs[6]:
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
    view = st.session_state.get("auth_view")
    if view == "request_profile":
        request_profile_screen()
    elif view == "forgot_password":
        forgot_password_screen()
    else:
        login_screen()
else:
    role_dashboard()
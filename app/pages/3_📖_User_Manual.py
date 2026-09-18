"""
User Manual — how to navigate and use WMS-Trak, organised by role.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import streamlit as st

from app.theme import render_sidebar, inject_global_css

st.set_page_config(page_title="User Manual — WMS-Trak", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("User Manual — How to Use WMS-Trak")

st.markdown("## Navigation")
st.write(
    "The left sidebar always shows the same things, no matter which "
    "role you're logged in as:"
)
st.markdown(
    "- **main** — your Dashboard, with role-specific tabs laid out horizontally\n"
    "- **About the Authors** — project information and the research group\n"
    "- **Notifications** — system updates and chat-style messages\n"
    "- **User Manual** — this page\n"
    "- **Account dropdown** (bottom of sidebar) — your profile, phone number, and Log out"
)
st.write(
    "Once logged in, you stay logged in even if you refresh the page — you "
    "only get signed out by clicking **Log out**."
)

st.divider()

st.markdown("## Logging In")
st.write(
    "Enter your username (usually your ZIMRA email) and password on the "
    "sign-in screen. If your account is inactive or your details are wrong, "
    "you'll see an error — contact an Admin user to check your account status "
    "or reset your password."
)

st.divider()

st.markdown("## Role-by-Role Guide")

with st.expander("👮 Officer", expanded=(user["role_name"] == "Officer")):
    st.markdown(
        "- **Capture Entry**: record a new RIH or NOS entry. Fill in importer/owner "
        "details, goods description, weight (with a kg/tonnes/litres/grams unit "
        "dropdown), rent charge per day, the ZWG-to-USD exchange rate, an expiry "
        "date if applicable, and (for NOS) seizure/legal details, or (for vehicles) "
        "vehicle specifics. Assign it to a Warehouse (A–E) or, if it's a vehicle, a "
        "Pound (A–E).\n"
        "- **My Captured Entries**: see everything you've personally captured, and "
        "view full detail on any of them.\n"
        "- **Warehouses & Pounds**: check occupancy at your station, mark a "
        "warehouse/pound Full or Not Full, and see what's currently stored in each.\n"
        "- **Request Action**: choose one of four pathways for an active entry:\n"
        "    - *Release to Owner* — goods released once duty/fines/rent are settled\n"
        "    - *Forfeiture* — appropriation to the State; specify the requesting "
        "Ministry and letter/document reference\n"
        "    - *Destruction* — for expired, dangerous, perishable, or prohibited "
        "goods; requires the approving Port Health officer and reason\n"
        "    - *E-Auction* — sale via ZIMRA's online auction system\n\n"
        "  Every request goes to your Supervisor for review.\n"
        "- **Finalize Action**: once Manager gives final approval, this is where "
        "the entry actually leaves active tracking. The form shown depends on the "
        "action type: Release to Owner asks for duty paid, additional duty, and "
        "rent paid (the system auto-calculates rent owed from your rent-per-day "
        "rate × days in the warehouse); Forfeiture asks for the receiving "
        "representative's details; Destruction asks for the date, place, and "
        "stakeholders present; E-Auction asks for revenue collected and buyer "
        "details. All require a receipt number where applicable.\n"
        "- **Released & Sold**: see everything that's left active tracking at your "
        "station, plus running revenue totals."
    )

with st.expander("🧭 Supervisor", expanded=(user["role_name"] == "Supervisor")):
    st.markdown(
        "- **Review Requests**: Officer-submitted requests at your station land "
        "here first, regardless of action type. Approve to forward to the "
        "Manager, or reject with a reason.\n"
        "- **Warehouse Overview**: RIH list, Seizures list, and a monthly summary "
        "for your station — filterable by warehouse and date range.\n"
        "- **Released & Sold**: everything finalized at your station, with revenue "
        "totals."
    )

with st.expander("✅ Manager", expanded=(user["role_name"] == "Manager")):
    st.markdown(
        "- **Final Approvals**: requests already approved by a Supervisor land "
        "here, from all ports. Approving here grants **permission** — the entry "
        "moves to 'awaiting finalization,' but stays in active tracking until the "
        "Officer completes the finalization step.\n"
        "- **Warehouse Overview**: same as Supervisor's, but across all ports.\n"
        "- **Released & Sold**: system-wide revenue totals and finalized entries."
    )

with st.expander("🛠️ Admin", expanded=(user["role_name"] == "Admin")):
    st.markdown(
        "- **Users**: create new accounts (Officer, Supervisor, Manager, Admin), "
        "deactivate/reactivate accounts, reset passwords, or delete a user.\n"
        "- **Entry Correction**: search for an entry and fix mistakes (entry number, "
        "description, declared value) — every correction is logged with a reason.\n"
        "- **Audit Trail**: full history of every action taken in the system, plus a "
        "live list of currently detained goods with the officer responsible.\n"
        "- **Messages**: moderate the Messages feed — delete anything inappropriate "
        "or posted in error.\n"
        "- **Statistics**: total revenue collected, warehouse usage across all "
        "stations, and RIH entries sorted by days remaining until expiry.\n"
        "- **Warehouse Overview**: same filterable view available to Manager."
    )

st.divider()

st.markdown("## Notifications")
st.write(
    "Open **Notifications** from the sidebar. It has two tabs:"
)
st.markdown(
    "- **System Notifications**: automatic updates — entries awaiting your action, "
    "approvals, rejections, flags. Mark them read as you go.\n"
    "- **Messages**: a chat-style feed for human communication — send a message to "
    "everyone (ZIMRA-wide announcement), to a specific role, or to one person."
)

st.divider()

st.markdown("## The Release / Disposal Workflow, End to End")
st.markdown(
    "1. **Officer** captures the RIH/NOS entry.\n"
    "2. **Officer** requests one of four actions: **Release to Owner**, "
    "**Forfeiture**, **Destruction**, or **E-Auction** — with any type-specific "
    "details required at request time (e.g. Ministry name for Forfeiture, Port "
    "Health approval for Destruction).\n"
    "3. **Supervisor** reviews the request — approve to forward, or reject.\n"
    "4. **Manager** gives final approval — this grants **permission**, but does "
    "not yet remove the entry from active tracking.\n"
    "5. **Officer** finalizes the action — records the type-specific closing "
    "details (payment breakdown and auto-calculated rent for Release to Owner; "
    "representative details for Forfeiture; destruction date/place/stakeholders "
    "for Destruction; revenue and buyer details for E-Auction). **This step is "
    "what actually effects the action** and removes the entry from active stock.\n"
    "6. The entry now appears in everyone's **Released & Sold** tab within their "
    "jurisdiction, contributing to revenue totals."
)
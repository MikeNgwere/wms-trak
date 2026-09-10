"""
User Manual — how to navigate and use WMS-Trak, organised by role.
"""
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
    "The left sidebar always shows the same three things, no matter which "
    "role you're logged in as:"
)
st.markdown(
    "- **main** — your Dashboard, with role-specific tabs laid out horizontally\n"
    "- **About the Authors** — project information and the research group\n"
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
        "details, goods description, and (for NOS) seizure/legal details, or (for "
        "vehicles) vehicle specifics. Assign it to a Warehouse (A–E) or, if it's a "
        "vehicle, a Pound (A–E).\n"
        "- **My Captured Entries**: see everything you've personally captured, and "
        "view full detail on any of them.\n"
        "- **Warehouses & Pounds**: check occupancy at your station, mark a "
        "warehouse/pound Full or Not Full, and see what's currently stored in each.\n"
        "- **Request Release / Disposal**: once duty/fines/rent are ready to be "
        "settled (release) or a seizure needs disposing of (offhand sale, "
        "appropriation, auction), submit a request here — it goes to your "
        "Supervisor for review.\n"
        "- **Finalize Payment**: once Manager gives final approval, come back here "
        "to record the actual receipt number and amounts (duty, fines, rent) "
        "collected.\n"
        "- **Released & Sold**: see everything that's left active tracking at your "
        "station, plus running revenue totals."
    )

with st.expander("🧭 Supervisor", expanded=(user["role_name"] == "Supervisor")):
    st.markdown(
        "- **Review Requests**: Officer-submitted release/disposal requests at your "
        "station land here first. Approve to forward to the Manager, or reject with "
        "a reason.\n"
        "- **Warehouse Overview**: RIH list, Seizures list, and a monthly summary "
        "for your station — filterable by warehouse and date range.\n"
        "- **Released & Sold**: everything finalized at your station, with revenue "
        "totals."
    )

with st.expander("✅ Manager", expanded=(user["role_name"] == "Manager")):
    st.markdown(
        "- **Final Approvals**: requests already approved by a Supervisor land here, "
        "from all ports. Approving here **effects** the action immediately — the "
        "entry leaves active tracking (released/sold/auctioned/appropriated), but "
        "the full record stays in the audit trail.\n"
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
    "2. **Officer** requests **Release** (goods released once payment is settled) "
    "or **Disposal** (offhand sale, appropriation, or auction).\n"
    "3. **Supervisor** reviews the request — approve to forward, or reject.\n"
    "4. **Manager** gives final approval — this immediately effects the action.\n"
    "5. **Officer** finalizes payment — records the receipt number and amounts "
    "(duty, fines, rent) actually collected.\n"
    "6. The entry now appears in everyone's **Released & Sold** tab within their "
    "jurisdiction, contributing to revenue totals."
)
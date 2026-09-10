"""
About the Authors — project information and group member details,
for easy sharing with the training supervisor.
"""
import streamlit as st

from app.theme import render_sidebar, inject_global_css

st.set_page_config(page_title="About the Authors — WMS-Trak", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("About the Authors")

st.markdown("### Project Title")
st.write(
    "Development of a Digital Reconciliation and Expiry Monitoring System "
    "for State Warehouse Compliance at ZIMRA (WMS-Trak)"
)

st.markdown("### Institution & Programme")
st.write("Zimbabwe Revenue Authority (ZIMRA) — Graduate Trainee Research Programme")

st.markdown("### Problem Scope")
st.write(
    "State Warehouse (RIH) and Notice of Seizure (NOS) goods at ZIMRA are currently "
    "tracked using manual registers. This creates blind spots: overstayed goods are "
    "typically identified only during periodic physical audits rather than in real "
    "time, and there is no consolidated, auditable trail linking capture, approval, "
    "payment, and final disposition of detained goods. WMS-Trak digitises this "
    "process end-to-end for a single-station pilot (Forbes — ZWFB), covering RIH "
    "and NOS entries, warehouse/pound capacity management, a role-based approval "
    "chain (Officer → Supervisor → Manager), payment finalization, and a full "
    "audit trail."
)

st.markdown("### Methodology")
st.write(
    "The project follows a design science research approach: current manual "
    "processes were reviewed against the Customs and Excise Act [Chapter 23:02] "
    "and its General Regulations to extract accurate statutory periods (bond "
    "expiry, seizure appeal windows), followed by iterative design, development, "
    "and testing of the WMS-Trak prototype. The system was built with Python, "
    "PostgreSQL (Supabase), and Streamlit, and deployed for live pilot testing "
    "and supervisor review."
)

st.markdown("### Results")
st.info(
    "To be completed as pilot testing and evaluation progress — summarise "
    "observed outcomes here (e.g. entries tracked, time-to-detect improvements, "
    "user feedback) once available."
)

st.markdown("### Research Group — Graduate Trainees, 2026")
st.table(
    [
        {"Name": "Mike Ngwere", "EC Number": "5474"},
        {"Name": "Tatendaishe Dorcas Mabvure", "EC Number": "5436"},
        {"Name": "Blessing Masunga", "EC Number": "5473"},
        {"Name": "Leanne Monica Mazambani", "EC Number": "5448"},
        {"Name": "Julia Barangwe", "EC Number": "5468"},
    ]
)

st.markdown("### Supervisor")
st.write("Sendra Chihaka — Training Officer, Human Capital Division, ZIMRA")
st.write("Email: schihaka@zimra.co.zw")
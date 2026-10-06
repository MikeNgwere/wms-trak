"""
About the Authors — project name, research group, and supervisor.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.theme import render_sidebar, inject_global_css

st.set_page_config(page_title="About the Authors — Warehouse Management System", layout="wide")
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
    "for State Warehouse Compliance at ZIMRA"
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
"""
Verify Document — public page opened by the QR code printed on every RIH and NOS.
No login needed: it only confirms that the document number exists in the system and
shows a few non-sensitive details so the holder can compare them with the paper.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.db import fetch_one
from app.theme import inject_global_css

st.set_page_config(page_title="Verify Document — ZIMRA", layout="centered")
inject_global_css()


def _mask(name):
    words = [w for w in (name or "").split() if w]
    return " ".join(w[0] + "*" * min(len(w) - 1, 6) for w in words) or "—"


def _lookup(kind, number):
    if kind == "NOS":
        join, col = "JOIN nos_details d ON d.entry_id = e.entry_id", "d.nos_number"
    else:
        join, col = "JOIN rih_details d ON d.entry_id = e.entry_id", "d.rih_number"
    q = f"""SELECT e.entry_number, e.entry_type, e.goods_description, e.date_entered, e.status,
                   e.importer_name, p.port_name, w.warehouse_name, COALESCE({col}, e.entry_number) AS doc_number
            FROM entries e LEFT {join}
            LEFT JOIN ports p ON p.port_code = e.port_code
            LEFT JOIN warehouses w ON w.warehouse_id = e.warehouse_id
            WHERE ({col} = %s OR e.entry_number = %s) AND e.entry_type = %s
            ORDER BY e.entry_id DESC LIMIT 1"""
    return fetch_one(q, (number, number, kind))


st.title("Verify a ZIMRA Document")
st.caption("Receipt for Items Held (RIH) and Notice of Seizure (NOS)")

qp = st.query_params
kind = (qp.get("t") or "RIH").upper()
kind = kind if kind in ("RIH", "NOS") else "RIH"
number = (qp.get("no") or "").strip()

with st.form("verify"):
    c1, c2 = st.columns([1, 2])
    kind_in = c1.selectbox("Document type", ["RIH", "NOS"], index=["RIH", "NOS"].index(kind))
    number_in = c2.text_input("Serial / document number", value=number)
    go = st.form_submit_button("Verify")
if go:
    kind, number = kind_in, number_in.strip()

if number:
    try:
        rec = _lookup(kind, number)
    except Exception:
        rec = None
        st.error("The verification service is unavailable right now. Please try again shortly.")
    else:
        if rec:
            st.success(f"✅ GENUINE — this {kind} number is recorded in the ZIMRA Warehouse Management System.")
            st.markdown(
                f"- **Document:** {'Receipt for Items Held' if kind == 'RIH' else 'Notice of Seizure'} No. **{rec['doc_number']}**\n"
                f"- **Station:** {rec['port_name'] or '—'}\n"
                f"- **Date captured:** {rec['date_entered']:%d %b %Y}\n"
                f"- **Goods:** {(rec['goods_description'] or '—')[:80]}\n"
                f"- **Issued to:** {_mask(rec['importer_name'])}\n"
                f"- **Current status:** {str(rec['status']).replace('_', ' ').title()}"
            )
            st.info("Compare these details with the paper document. If anything differs, do not accept the document.")
        else:
            st.error(f"❌ NOT FOUND — no {kind} numbered “{number}” exists in the system. "
                     "Do not accept this document; report it to the nearest ZIMRA office.")
else:
    st.info("Scan the QR code on the document, or type its serial number above.")
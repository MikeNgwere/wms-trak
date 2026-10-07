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


LABELS = {"RIH": "Receipt for Items Held (RIH)", "NOS": "Notice of Seizure (NOS)",
          "CLOSE": "Closing document (receipt / record / certificate)", "NOTICE": "Notice of E-Auction",
          "TRANSFER": "Warehouse Transfer Note"}
CLOSE_NAMES = {"release_to_owner": "Release Receipt", "forfeiture": "Forfeiture / Appropriation Record",
               "destruction": "Certificate of Destruction", "e_auction": "E-Auction Sale Record"}


def _lookup_other(kind, number):
    """Closing documents (by request number) and auction notices (by notice number)."""
    try:
        n = int(number)
    except ValueError:
        return None
    if kind == "CLOSE":
        r = fetch_one("""SELECT ar.action_type, ar.request_id, e.entry_number, e.entry_type, e.goods_description,
                                p.port_name, COALESCE(ar.effected_at, ar.created_at) AS on_date
                         FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id
                         LEFT JOIN ports p ON p.port_code = e.port_code
                         WHERE ar.request_id = %s AND ar.effected IS TRUE""", (n,))
        if r:
            r["title"] = CLOSE_NAMES.get(r["action_type"], "Closing document")
            r["doc_number"] = f"{r['request_id']:05d}"
        return r
    if kind == "TRANSFER":
        r = fetch_one("""SELECT t.transfer_id, t.moved_at AS on_date, e.entry_number, e.entry_type, e.goods_description,
                                p.port_name, fw.warehouse_name AS from_name, tw.warehouse_name AS to_name
                         FROM transfer_requests t JOIN entries e ON e.entry_id = t.entry_id
                         JOIN warehouses fw ON fw.warehouse_id = t.from_warehouse_id
                         JOIN warehouses tw ON tw.warehouse_id = t.to_warehouse_id
                         LEFT JOIN ports p ON p.port_code = e.port_code
                         WHERE t.transfer_id = %s AND t.status = 'approved'""", (n,))
        if r:
            r["title"] = "Warehouse Transfer Note"
            r["doc_number"] = f"TRF/{r['transfer_id']:05d}"
        return r
    r = fetch_one("""SELECT n.notice_id, n.gazette_date, n.auction_date, e.entry_number, e.entry_type, e.goods_description,
                            p.port_name, n.created_at AS on_date
                     FROM auction_notices n JOIN entries e ON e.entry_id = n.entry_id
                     LEFT JOIN ports p ON p.port_code = e.port_code WHERE n.notice_id = %s""", (n,))
    if r:
        r["title"] = "Notice of E-Auction"
        r["doc_number"] = f"NTC/{r['notice_id']:05d}"
    return r


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
st.caption("Receipt for Items Held, Notice of Seizure, closing documents and auction notices")

qp = st.query_params
kind = (qp.get("t") or "RIH").upper()
kind = kind if kind in LABELS else "RIH"
number = (qp.get("no") or "").strip()

with st.form("verify"):
    c1, c2 = st.columns([1, 2])
    kind_in = c1.selectbox("Document type", list(LABELS), index=list(LABELS).index(kind), format_func=lambda k: LABELS[k])
    number_in = c2.text_input("Serial / document number", value=number)
    go = st.form_submit_button("Verify")
if go:
    kind, number = kind_in, number_in.strip()

if number:
    try:
        rec = _lookup(kind, number) if kind in ("RIH", "NOS") else _lookup_other(kind, number)
    except Exception:
        rec = None
        st.error("The verification service is unavailable right now. Please try again shortly.")
    else:
        if rec and kind in ("CLOSE", "NOTICE", "TRANSFER"):
            st.success(f"✅ GENUINE — this {rec['title']} is recorded in the ZIMRA Warehouse Management System.")
            extra = (f"- **Gazette date / auction date:** {rec['gazette_date']:%d %b %Y} / {rec['auction_date']:%d %b %Y}\n"
                     if kind == "NOTICE" else
                     f"- **Moved:** {rec['from_name']} ➜ {rec['to_name']}\n" if kind == "TRANSFER" else "")
            st.markdown(
                f"- **Document:** {rec['title']} No. **{rec['doc_number']}**\n"
                f"- **Relates to:** {rec['entry_type']} entry {rec['entry_number']}\n"
                f"- **Station:** {rec['port_name'] or '—'}\n"
                f"- **Date:** {rec['on_date']:%d %b %Y}\n"
                f"- **Goods:** {(rec['goods_description'] or '—')[:80]}\n" + extra)
            st.info("Compare these details with the paper document. If anything differs, do not accept the document.")
        elif rec:
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
            st.error(f"❌ NOT FOUND — no {LABELS[kind]} numbered “{number}” exists in the system. "
                     "Do not accept this document; report it to the nearest ZIMRA office.")
else:
    st.info("Scan the QR code on the document, or type its serial number above.")
"""
Stocktake (audit) — ADMIN ONLY counts.

Officers, Supervisors and Managers are the people being audited, so they never
count. They see results through app/stocktake_reports.py.

Scoring (out of 100):
    score = present / (expected + extras) * 100
    100 is the target; a 5% variance is tolerated; score < 95 => FLAGGED for
    potential fraud, and every missing entry is flagged together with the
    responsible officer (and the supervisor / manager who approved it).
"""
import re
from datetime import datetime

from app.db import fetch_all, fetch_one

PASS_MARK = 95.0

# ---------------------------------------------------------------- categories
_CATEGORY_WORDS = [
    ("Drinks", r"beer|wine|whisk(?:e)?y|vodka|gin|rum|brandy|liquor|spirit|juice|soda|cola|water|drink|beverage|lager|cider|energy drink|champagne"),
    ("Clothing", r"cloth|garment|shirt|trouser|jean|dress|shoe|sneaker|boot|jacket|coat|sock|underwear|blanket|fabric|textile|bale|second.?hand|ukay|wig"),
    ("Perishables", r"fruit|vegetable|meat|chicken|beef|pork|fish|egg|milk|cheese|butter|bread|tomato|potato|onion|banana|orange|apple|mango|fresh|frozen|dairy|yoghurt|yogurt|perishable"),
    ("Electronics", r"phone|cellphone|smart.?phone|laptop|computer|tablet|tv|television|radio|speaker|electronic|battery|charger|solar|inverter|camera|printer|router|decoder|tv set"),
    ("Building & Hardware", r"cement|brick|tile|roofing|timber|pipe|paint|steel|iron|wire|nail|tool|generator|machin|pump|tyre|tire|spare|engine|building|hardware"),
    ("Groceries", r"rice|sugar|flour|maize|mealie|cooking oil|salt|grocer|beans|pasta|noodle|sauce|biscuit|sweet|canned|food|wheat"),
    ("Tobacco", r"cigarette|tobacco|cigar|snuff|vape"),
    ("Medicines", r"medic|drug|tablet|pharma|syrup|ointment|capsule|vaccine"),
]
_CATEGORY_RE = [(n, re.compile(r"\b(?:%s)(?:s|es)?\b" % p, re.I)) for n, p in _CATEGORY_WORDS]
CATEGORIES = ["Vehicles", "Drinks", "Clothing", "Perishables", "Electronics",
              "Building & Hardware", "Groceries", "Tobacco", "Medicines", "Other"]


def classify(description, is_vehicle=False, expiry_date=None):
    """Keyword-based category of the goods (Vehicles first; goods with an expiry date are Perishables)."""
    if is_vehicle:
        return "Vehicles"
    text = description or ""
    for name, rx in _CATEGORY_RE:
        if name in ("Drinks", "Clothing") and rx.search(text):
            return name
    if expiry_date:
        return "Perishables"
    for name, rx in _CATEGORY_RE:
        if rx.search(text):
            return name
    return "Other"


def compute_score(expected, present, extras):
    """(score, flagged). No goods at all => (None, False)."""
    denom = (expected or 0) + (extras or 0)
    if denom <= 0:
        return None, False
    score = round(100.0 * (present or 0) / denom, 2)
    return score, score < PASS_MARK


# ---------------------------------------------------------------- data
def open_stocktake(warehouse_id):
    return fetch_one("SELECT * FROM stocktakes WHERE warehouse_id=%s AND status='open'", (warehouse_id,))


def expected_entry_ids(warehouse_id):
    from app.warehouses import goods_in_warehouse
    from app.entry_documents import _resolve_entry_id
    ids = []
    for row in goods_in_warehouse(warehouse_id) or []:
        eid = _resolve_entry_id(row)
        if eid and eid not in ids:
            ids.append(eid)
    return ids


def start_stocktake(warehouse_id, port_code, user_id):
    """Snapshot every expected entry with its category and responsible officer / supervisor / manager."""
    if open_stocktake(warehouse_id):
        raise ValueError("A stocktake is already open for this warehouse.")
    ids = expected_entry_ids(warehouse_id)
    st = fetch_one(
        "INSERT INTO stocktakes (warehouse_id, port_code, started_by) VALUES (%s,%s,%s) RETURNING stocktake_id",
        (warehouse_id, port_code, user_id))
    sid = st["stocktake_id"]
    for eid in ids:
        e = fetch_one(
            """SELECT e.goods_description, e.is_vehicle, e.expiry_date,
                      COALESCE(e.captured_by, e.officer_id) AS officer_id,
                      (SELECT a.supervisor_by FROM action_requests a
                        WHERE a.entry_id = e.entry_id AND a.supervisor_by IS NOT NULL
                        ORDER BY a.request_id DESC LIMIT 1) AS supervisor_id,
                      (SELECT a.manager_by FROM action_requests a
                        WHERE a.entry_id = e.entry_id AND a.manager_by IS NOT NULL
                        ORDER BY a.request_id DESC LIMIT 1) AS manager_id
               FROM entries e WHERE e.entry_id=%s""", (eid,)) or {}
        fetch_one(
            """INSERT INTO stocktake_items
                   (stocktake_id, entry_id, officer_id, supervisor_id, manager_id, category)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING item_id""",
            (sid, eid, e.get("officer_id"), e.get("supervisor_id"), e.get("manager_id"),
             classify(e.get("goods_description"), e.get("is_vehicle"), e.get("expiry_date"))))
    return sid, len(ids)


def items(stocktake_id):
    return fetch_all(
        """SELECT i.item_id, i.found, i.category, e.entry_id, e.entry_number, e.entry_type,
                  e.goods_description, e.date_entered
           FROM stocktake_items i JOIN entries e ON e.entry_id = i.entry_id
           WHERE i.stocktake_id=%s ORDER BY e.entry_number""", (stocktake_id,))


def extras(stocktake_id):
    return fetch_all(
        "SELECT extra_id, description, quantity_text, noted_at FROM stocktake_extras "
        "WHERE stocktake_id=%s ORDER BY extra_id", (stocktake_id,))


def _is_open(stocktake_id):
    return bool(fetch_one("SELECT 1 AS ok FROM stocktakes WHERE stocktake_id=%s AND status='open'", (stocktake_id,)))


def save_counts(stocktake_id, user_id, present_by_item):
    if not _is_open(stocktake_id):
        raise ValueError("This stocktake is closed.")
    for item_id, present in present_by_item.items():
        fetch_one(
            "UPDATE stocktake_items SET found=%s, counted_by=%s, counted_at=NOW() "
            "WHERE item_id=%s AND stocktake_id=%s RETURNING item_id",
            (bool(present), user_id, item_id, stocktake_id))


def add_extra(stocktake_id, user_id, description, quantity_text):
    if not _is_open(stocktake_id):
        raise ValueError("This stocktake is closed.")
    fetch_one(
        "INSERT INTO stocktake_extras (stocktake_id, description, quantity_text, noted_by) "
        "VALUES (%s,%s,%s,%s) RETURNING extra_id", (stocktake_id, description, quantity_text, user_id))


def delete_extra(stocktake_id, extra_id):
    fetch_one("DELETE FROM stocktake_extras WHERE extra_id=%s AND stocktake_id=%s "
              "AND EXISTS (SELECT 1 FROM stocktakes WHERE stocktake_id=%s AND status='open') RETURNING extra_id",
              (extra_id, stocktake_id, stocktake_id))


def summary(stocktake_id):
    r = fetch_one(
        """SELECT COUNT(*) AS expected,
                  COUNT(*) FILTER (WHERE found IS TRUE)  AS present,
                  COUNT(*) FILTER (WHERE found IS NOT TRUE) AS missing
           FROM stocktake_items WHERE stocktake_id=%s""", (stocktake_id,))
    r["extras"] = fetch_one("SELECT COUNT(*) AS n FROM stocktake_extras WHERE stocktake_id=%s", (stocktake_id,))["n"]
    r["score"], r["flagged"] = compute_score(r["expected"], r["present"], r["extras"])
    return r


def _notify_flag(stocktake_id, score):
    """Tell the responsible officers, port supervisors and managers. Best-effort: never blocks closing."""
    try:
        head = fetch_one(
            """SELECT s.port_code, w.warehouse_name FROM stocktakes s
               JOIN warehouses w ON w.warehouse_id = s.warehouse_id WHERE s.stocktake_id=%s""", (stocktake_id,))
        msg = (f"Stocktake #{stocktake_id} at {head['warehouse_name']} scored {score:.1f}/100 — below the {PASS_MARK:.0f} "
               f"pass mark. Missing entries are flagged for investigation.")
        people = fetch_all(
            """SELECT DISTINCT u FROM (
                   SELECT officer_id AS u FROM stocktake_items WHERE stocktake_id=%s AND found IS NOT TRUE
                   UNION SELECT supervisor_id FROM stocktake_items WHERE stocktake_id=%s AND found IS NOT TRUE
                   UNION SELECT manager_id FROM stocktake_items WHERE stocktake_id=%s AND found IS NOT TRUE
                   UNION SELECT us.user_id FROM users us JOIN roles r ON r.role_id = us.role_id
                         WHERE us.is_active AND ((r.role_name='Supervisor' AND us.port_code=%s) OR r.role_name='Manager')
               ) x WHERE u IS NOT NULL""", (stocktake_id, stocktake_id, stocktake_id, head["port_code"]))
        for p in people:
            fetch_one("INSERT INTO notifications (recipient_user_id, notif_type, message, is_read) "
                      "VALUES (%s,'stocktake_flag',%s,FALSE) RETURNING notification_id", (p["u"], msg))
    except Exception:
        pass


def close_stocktake(stocktake_id, user_id, notes=""):
    """Lock the stocktake, store the score and raise the fraud flag if below the pass mark."""
    fetch_one("UPDATE stocktake_items SET found=FALSE WHERE stocktake_id=%s AND found IS NULL RETURNING item_id", (stocktake_id,))
    sm = summary(stocktake_id)
    closed = fetch_one(
        """UPDATE stocktakes SET status='closed', closed_by=%s, closed_at=NOW(), notes=%s,
               score=%s, flagged=%s, expected_count=%s, present_count=%s, missing_count=%s, extra_count=%s
           WHERE stocktake_id=%s AND status='open' RETURNING stocktake_id""",
        (user_id, notes or None, sm["score"], bool(sm["flagged"]), sm["expected"], sm["present"],
         sm["missing"], sm["extras"], stocktake_id))
    if closed and sm["flagged"]:
        _notify_flag(stocktake_id, sm["score"])
    return closed


def history(warehouse_id):
    return fetch_all(
        """SELECT s.stocktake_id, s.started_at, s.closed_at, s.status, s.score, s.flagged,
                  u.full_name AS started_by_name
           FROM stocktakes s LEFT JOIN users u ON u.user_id = s.started_by
           WHERE s.warehouse_id=%s ORDER BY s.stocktake_id DESC LIMIT 25""", (warehouse_id,))


# ---------------------------------------------------------------- Admin UI
def stocktake_tab(user):
    """Counting screen. Only Admin may count."""
    import pandas as pd
    import streamlit as st
    from app.stocktake_reports import build_stocktake_pdf, score_badge

    if user["role_name"] != "Admin":
        st.warning("Stocktakes are audit procedures carried out by the Admin profile only.")
        return

    st.subheader("Stocktake (Audit)")
    st.caption("Count what is physically in a warehouse against what the system says should be there. "
               f"Score = present ÷ (expected + extras) × 100. Below {PASS_MARK:.0f} is flagged as potential fraud.")

    whs = fetch_all("""SELECT w.warehouse_id, w.warehouse_name, w.port_code, COALESCE(p.port_name, w.port_code) AS port_name
                       FROM warehouses w LEFT JOIN ports p ON p.port_code = w.port_code
                       ORDER BY port_name, w.warehouse_name""")
    if not whs:
        st.info("No warehouses found.")
        return
    choices = {f"{w['port_name']} — {w['warehouse_name']}": w for w in whs}
    wh = choices[st.selectbox("Warehouse / Pound", list(choices.keys()), key="stk_wh")]
    wid = wh["warehouse_id"]

    msg = st.session_state.pop("stk_msg", None)
    cur = open_stocktake(wid)
    if not cur:
        if st.button("▶ Start a new stocktake", type="primary", key=f"stk_start_{wid}"):
            try:
                _, n = start_stocktake(wid, wh["port_code"], user["user_id"])
                st.session_state.stk_msg = f"Stocktake started with {n} expected item(s)."
            except ValueError as e:
                st.session_state.stk_msg = str(e)
            st.rerun()
        if msg:
            st.info(msg)
    else:
        sid = cur["stocktake_id"]
        if msg:
            st.success(msg)
        sm = summary(sid)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Expected", sm["expected"]); c2.metric("Ticked present", sm["present"])
        c3.metric("Not yet found", sm["expected"] - sm["present"]); c4.metric("Extra found", sm["extras"])

        rows = items(sid)
        st.markdown("**Tick every item you can physically see. Anything left unticked is reported as MISSING.**")
        df = pd.DataFrame([{"item_id": r["item_id"], "Present": bool(r["found"]), "Entry no.": r["entry_number"],
                            "Type": r["entry_type"], "Category": r["category"], "Goods": r["goods_description"]}
                           for r in rows])
        if df.empty:
            st.info("The system lists no goods in this warehouse.")
        else:
            edited = st.data_editor(df, hide_index=True, use_container_width=True, key=f"stk_editor_{sid}",
                                    column_config={"item_id": None, "Present": st.column_config.CheckboxColumn("Present")},
                                    disabled=["Entry no.", "Type", "Category", "Goods"])
            if st.button("💾 Save count", key=f"stk_save_{sid}"):
                save_counts(sid, user["user_id"], {int(r.item_id): bool(r.Present) for r in edited.itertuples()})
                st.session_state.stk_msg = "Count saved."
                st.rerun()

        st.markdown("**Goods found that are NOT on the system list**")
        with st.form(f"stk_extra_{sid}", clear_on_submit=True):
            d = st.text_input("Description of the goods")
            q = st.text_input("Quantity (optional)")
            if st.form_submit_button("Add extra item") and d.strip():
                add_extra(sid, user["user_id"], d.strip(), q.strip())
                st.rerun()
        for e in extras(sid):
            cc1, cc2 = st.columns([6, 1])
            cc1.write(f"• {e['description']}" + (f" — {e['quantity_text']}" if e["quantity_text"] else ""))
            if cc2.button("Remove", key=f"stk_rmx_{e['extra_id']}"):
                delete_extra(sid, e["extra_id"]); st.rerun()

        st.divider()
        notes = st.text_area("Closing notes (optional)", key=f"stk_notes_{sid}")
        if st.button("✅ Close stocktake and score it", type="primary", key=f"stk_close_{sid}"):
            save_counts(sid, user["user_id"], {int(r.item_id): bool(r.Present) for r in edited.itertuples()}) if not df.empty else None
            close_stocktake(sid, user["user_id"], notes)
            res = summary(sid)
            st.session_state.stk_msg = ("Stocktake closed. " + (score_badge(res["score"]) if res["score"] is not None else "No goods to score."))
            st.rerun()

    st.divider()
    st.markdown("**Stocktake history**")
    hist = history(wid)
    if not hist:
        st.caption("No stocktakes yet for this warehouse.")
    for h in hist:
        with st.container(border=True):
            when = h["closed_at"] or h["started_at"]
            tag = "OPEN" if h["status"] == "open" else (score_badge(h["score"]) if h["score"] is not None else "closed — no goods")
            st.write(f"**#{h['stocktake_id']}** — {when:%d %b %Y %H:%M} — {tag}")
            st.caption(f"Started by {h['started_by_name'] or '—'}")
            if h["status"] == "closed" and st.toggle("Prepare report for download", key=f"stk_tg_{h['stocktake_id']}"):
                st.download_button("⬇ Download report (PDF)", data=build_stocktake_pdf(h["stocktake_id"]),
                                   file_name=f"Stocktake_{h['stocktake_id']}.pdf", mime="application/pdf",
                                   key=f"stk_dl_{h['stocktake_id']}")

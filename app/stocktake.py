"""
Stocktake / reconciliation.

Workflow
  1. Start: the system snapshots every entry it expects in the warehouse.
  2. Count: officers tick what is physically present; anything not ticked is MISSING.
     Goods found that are not on the list are recorded as EXTRA.
  3. Close: the stocktake is locked and a printable reconciliation report is produced.
"""
from datetime import datetime
from io import BytesIO

from app.db import fetch_all, fetch_one

_ENTRY_COLS = "e.entry_id, e.entry_number, e.entry_type, e.goods_description, e.date_entered"


# ---------- data ----------
def open_stocktake(warehouse_id):
    return fetch_one("SELECT * FROM stocktakes WHERE warehouse_id=%s AND status='open'", (warehouse_id,))


def expected_entry_ids(warehouse_id):
    """Entries the system currently shows as held in this warehouse (same source as the occupancy count)."""
    from app.warehouses import goods_in_warehouse
    from app.entry_documents import _resolve_entry_id
    ids = []
    for row in goods_in_warehouse(warehouse_id) or []:
        eid = _resolve_entry_id(row)
        if eid and eid not in ids:
            ids.append(eid)
    return ids


def start_stocktake(warehouse_id, port_code, user_id):
    if open_stocktake(warehouse_id):
        raise ValueError("A stocktake is already open for this warehouse.")
    ids = expected_entry_ids(warehouse_id)
    st = fetch_one(
        "INSERT INTO stocktakes (warehouse_id, port_code, started_by) VALUES (%s,%s,%s) RETURNING stocktake_id",
        (warehouse_id, port_code, user_id),
    )
    for eid in ids:
        fetch_one(
            "INSERT INTO stocktake_items (stocktake_id, entry_id) VALUES (%s,%s) RETURNING item_id",
            (st["stocktake_id"], eid),
        )
    return st["stocktake_id"], len(ids)


def items(stocktake_id):
    return fetch_all(
        f"""SELECT i.item_id, i.found, {_ENTRY_COLS}
            FROM stocktake_items i JOIN entries e ON e.entry_id = i.entry_id
            WHERE i.stocktake_id=%s ORDER BY e.entry_number""",
        (stocktake_id,),
    )


def extras(stocktake_id):
    return fetch_all(
        "SELECT extra_id, description, quantity_text, noted_at FROM stocktake_extras "
        "WHERE stocktake_id=%s ORDER BY extra_id", (stocktake_id,))


def save_counts(stocktake_id, user_id, present_by_item):
    """present_by_item: {item_id: bool}. Refuses to change a closed stocktake."""
    if not fetch_one("SELECT 1 AS ok FROM stocktakes WHERE stocktake_id=%s AND status='open'", (stocktake_id,)):
        raise ValueError("This stocktake is closed.")
    for item_id, present in present_by_item.items():
        fetch_one(
            "UPDATE stocktake_items SET found=%s, counted_by=%s, counted_at=NOW() "
            "WHERE item_id=%s AND stocktake_id=%s RETURNING item_id",
            (bool(present), user_id, item_id, stocktake_id),
        )


def add_extra(stocktake_id, user_id, description, quantity_text):
    if not fetch_one("SELECT 1 AS ok FROM stocktakes WHERE stocktake_id=%s AND status='open'", (stocktake_id,)):
        raise ValueError("This stocktake is closed.")
    fetch_one(
        "INSERT INTO stocktake_extras (stocktake_id, description, quantity_text, noted_by) "
        "VALUES (%s,%s,%s,%s) RETURNING extra_id",
        (stocktake_id, description, quantity_text, user_id),
    )


def delete_extra(stocktake_id, extra_id):
    fetch_one("DELETE FROM stocktake_extras WHERE extra_id=%s AND stocktake_id=%s "
              "AND EXISTS (SELECT 1 FROM stocktakes WHERE stocktake_id=%s AND status='open') RETURNING extra_id",
              (extra_id, stocktake_id, stocktake_id))


def close_stocktake(stocktake_id, user_id, notes=""):
    # anything never ticked is treated as missing
    fetch_one("UPDATE stocktake_items SET found=FALSE WHERE stocktake_id=%s AND found IS NULL RETURNING item_id", (stocktake_id,))
    return fetch_one(
        "UPDATE stocktakes SET status='closed', closed_by=%s, closed_at=NOW(), notes=%s "
        "WHERE stocktake_id=%s AND status='open' RETURNING stocktake_id",
        (user_id, notes or None, stocktake_id),
    )


def summary(stocktake_id):
    r = fetch_one(
        """SELECT COUNT(*) AS expected,
                  COUNT(*) FILTER (WHERE found IS TRUE)  AS present,
                  COUNT(*) FILTER (WHERE found IS FALSE) AS missing,
                  COUNT(*) FILTER (WHERE found IS NULL)  AS uncounted
           FROM stocktake_items WHERE stocktake_id=%s""", (stocktake_id,))
    r["extras"] = fetch_one("SELECT COUNT(*) AS n FROM stocktake_extras WHERE stocktake_id=%s", (stocktake_id,))["n"]
    return r


def history(warehouse_id):
    return fetch_all(
        """SELECT s.stocktake_id, s.started_at, s.closed_at, s.status,
                  u.full_name AS started_by_name, c.full_name AS closed_by_name
           FROM stocktakes s
           LEFT JOIN users u ON u.user_id = s.started_by
           LEFT JOIN users c ON c.user_id = s.closed_by
           WHERE s.warehouse_id=%s ORDER BY s.stocktake_id DESC LIMIT 25""", (warehouse_id,))


def report_data(stocktake_id):
    head = fetch_one(
        """SELECT s.*, w.warehouse_name, p.port_name, u.full_name AS started_by_name, c.full_name AS closed_by_name
           FROM stocktakes s
           JOIN warehouses w ON w.warehouse_id = s.warehouse_id
           LEFT JOIN ports p ON p.port_code = s.port_code
           LEFT JOIN users u ON u.user_id = s.started_by
           LEFT JOIN users c ON c.user_id = s.closed_by
           WHERE s.stocktake_id=%s""", (stocktake_id,))
    return head, items(stocktake_id), extras(stocktake_id), summary(stocktake_id)


# ---------- report PDF ----------
def build_report_pdf(stocktake_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from xml.sax.saxutils import escape
    from app.entry_documents import _find_logo

    head, its, exs, sm = report_data(stocktake_id)
    green = colors.HexColor("#1F4E3D")
    base = ParagraphStyle("b", fontName="Times-Roman", fontSize=9, leading=11)
    bold = ParagraphStyle("k", parent=base, fontName="Times-Bold")
    title = ParagraphStyle("t", fontName="Times-Bold", fontSize=14, alignment=1, leading=17)
    sub = ParagraphStyle("s", fontName="Times-Bold", fontSize=12, alignment=1, textColor=green, leading=15)
    h = ParagraphStyle("h", fontName="Times-Bold", fontSize=10, textColor=green, spaceBefore=8, spaceAfter=3)
    P = lambda t, st=base: Paragraph(escape(str(t if t is not None else "")), st)

    def fmt(d):
        return d.strftime("%d/%m/%Y %H:%M") if hasattr(d, "strftime") else (str(d) if d else "—")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=12*mm, bottomMargin=12*mm,
                            title=f"Stocktake report {stocktake_id}", author="ZIMRA")
    el = []
    logo = _find_logo()
    if logo:
        try:
            im = Image(logo, width=20*mm, height=20*mm, kind="proportional"); im.hAlign = "CENTER"; el.append(im)
        except Exception:
            pass
    el += [Paragraph("ZIMBABWE REVENUE AUTHORITY", title), Paragraph("STOCKTAKE RECONCILIATION REPORT", sub), Spacer(1, 4*mm)]

    info = [
        [P("Warehouse", bold), P(head["warehouse_name"]), P("Station", bold), P(head["port_name"] or head["port_code"])],
        [P("Started", bold), P(f"{fmt(head['started_at'])} by {head['started_by_name'] or '—'}"),
         P("Closed", bold), P(f"{fmt(head['closed_at'])} by {head['closed_by_name'] or '—'}" if head["closed_at"] else "OPEN")],
    ]
    t = Table(info, colWidths=[24*mm, 66*mm, 22*mm, 66*mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [t, Spacer(1, 3*mm)]

    s = [[P("Expected", bold), P("Present", bold), P("MISSING", bold), P("Extra (not on system)", bold)],
         [P(sm["expected"]), P(sm["present"]), P(sm["missing"] + sm["uncounted"]), P(sm["extras"])]]
    t = Table(s, colWidths=[40*mm, 40*mm, 40*mm, 58*mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F5F3"))]))
    el += [t]

    def table(title_txt, rows, header, widths):
        el.append(Paragraph(title_txt, h))
        if not rows:
            el.append(P("None."))
            return
        data = [[P(x, bold) for x in header]] + [[P(c) for c in r] for r in rows]
        tb = Table(data, colWidths=widths, repeatRows=1)
        tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F5F3")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        el.append(tb)

    cols = ["Entry no.", "Type", "Description", "Date entered"]
    w = [30*mm, 14*mm, 98*mm, 32*mm]
    row = lambda r: [r["entry_number"], r["entry_type"], r["goods_description"], fmt(r["date_entered"])[:10]]
    table("MISSING — on the system list but not found in the warehouse",
          [row(r) for r in its if r["found"] is not True], cols, w)
    table("EXTRA — found in the warehouse but not on the system list",
          [[e["description"], e["quantity_text"] or "", fmt(e["noted_at"])] for e in exs],
          ["Description", "Quantity", "Noted"], [110*mm, 32*mm, 32*mm])
    table("PRESENT — confirmed in the warehouse", [row(r) for r in its if r["found"] is True], cols, w)
    if head.get("notes"):
        el += [Paragraph("Notes", h), P(head["notes"])]
    el.append(Spacer(1, 14*mm))
    sig = Table([[P("Counting Officer", base), P("Supervisor", base), P("Manager", base)]], colWidths=[58*mm] * 3)
    sig.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    el += [sig, Spacer(1, 3*mm),
           Paragraph(f"System-generated {datetime.now().strftime('%d/%m/%Y %H:%M')}", ParagraphStyle("f", fontName="Times-Italic", fontSize=7, alignment=1, textColor=colors.grey))]
    doc.build(el)
    return buf.getvalue()


# ---------- UI ----------
def stocktake_tab(user):
    import pandas as pd
    import streamlit as st
    from app.warehouses import warehouses_for_port

    st.subheader("Stocktake / Reconciliation")
    st.caption("Count what is physically in a warehouse against what the system says should be there.")

    scope_port = None if user["role_name"] in ("Manager", "Admin") else user["port_code"]
    if scope_port:
        whs = warehouses_for_port(scope_port)
    else:
        whs = fetch_all("SELECT warehouse_id, warehouse_name FROM warehouses ORDER BY warehouse_name")
    if not whs:
        st.info("No warehouses found.")
        return
    can_count = user["role_name"] in ("Officer", "Supervisor")
    choices = {w["warehouse_name"]: w["warehouse_id"] for w in whs}
    pick = st.selectbox("Warehouse / Pound", list(choices.keys()), key="stk_wh")
    wid = choices[pick]

    cur = open_stocktake(wid)
    if not cur:
        if can_count:
            if st.button("▶ Start a new stocktake", type="primary", key=f"stk_start_{wid}"):
                try:
                    sid, n = start_stocktake(wid, user["port_code"], user["user_id"])
                    st.session_state.stk_msg = f"Stocktake started with {n} expected item(s)."
                except ValueError as e:
                    st.session_state.stk_msg = str(e)
                st.rerun()
        else:
            st.info("No stocktake is open for this warehouse.")
        msg = st.session_state.pop("stk_msg", None)
        if msg:
            st.info(msg)
    else:
        sid = cur["stocktake_id"]
        msg = st.session_state.pop("stk_msg", None)
        if msg:
            st.success(msg)
        sm = summary(sid)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Expected", sm["expected"]); c2.metric("Ticked present", sm["present"])
        c3.metric("Not yet found", sm["expected"] - sm["present"]); c4.metric("Extra found", sm["extras"])

        rows = items(sid)
        if can_count:
            st.markdown("**Tick every item you can physically see. Anything left unticked will be reported as MISSING.**")
            df = pd.DataFrame([{
                "item_id": r["item_id"], "Present": bool(r["found"]), "Entry no.": r["entry_number"],
                "Type": r["entry_type"], "Goods": r["goods_description"],
            } for r in rows])
            if df.empty:
                st.info("The system lists no goods in this warehouse.")
            else:
                edited = st.data_editor(
                    df, hide_index=True, use_container_width=True, key=f"stk_editor_{sid}",
                    column_config={"item_id": None, "Present": st.column_config.CheckboxColumn("Present")},
                    disabled=["Entry no.", "Type", "Goods"],
                )
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
            if st.button("✅ Close stocktake and produce report", type="primary", key=f"stk_close_{sid}"):
                close_stocktake(sid, user["user_id"], notes)
                st.session_state.stk_msg = "Stocktake closed. The report is in the history below."
                st.rerun()
        else:
            st.info("A stocktake is in progress. Officers and Supervisors record the count.")

    st.divider()
    st.markdown("**Stocktake history**")
    hist = history(wid)
    if not hist:
        st.caption("No stocktakes yet for this warehouse.")
    for h in hist:
        sm = summary(h["stocktake_id"])
        with st.container(border=True):
            when = h["closed_at"] or h["started_at"]
            st.write(f"**#{h['stocktake_id']}** — {h['status'].upper()} — {when:%d %b %Y %H:%M}")
            st.caption(f"Expected {sm['expected']} · Present {sm['present']} · Missing {sm['missing'] + sm['uncounted']} · Extra {sm['extras']}"
                       f" · Started by {h['started_by_name'] or '—'}")
            if h["status"] == "closed" and st.toggle("Prepare report for download", key=f"stk_tg_{h['stocktake_id']}"):
                st.download_button("⬇ Download report (PDF)", data=build_report_pdf(h["stocktake_id"]),
                                   file_name=f"Stocktake_{h['stocktake_id']}.pdf", mime="application/pdf",
                                   key=f"stk_dl_{h['stocktake_id']}")

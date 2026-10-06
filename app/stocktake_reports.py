"""
Stocktake results, monthly reports and individual ratings for Officer / Supervisor / Manager / Admin.

Visibility
  Officer     – own rating + all reports for the station
  Supervisor  – ratings of the officers at his station + his own rating (goods he approved)
  Manager     – ratings of every supervisor and officer, all stations
  Admin       – everyone
"""
from datetime import date, datetime, timedelta
from io import BytesIO

from app.db import fetch_all, fetch_one
from app.stocktake import PASS_MARK, CATEGORIES

_ROLE_COL = {"Officer": "officer_id", "Supervisor": "supervisor_id", "Manager": "manager_id"}


def score_badge(score, pdf=False):
    if score is None:
        return "no score"
    bad = "FLAGGED (potential fraud)" if pdf else "⚠ FLAGGED (potential fraud)"
    return f"{float(score):.1f}/100 — " + ("PASS" if float(score) >= PASS_MARK else bad)


def _scope_port(user):
    return user["port_code"] if user["role_name"] in ("Officer", "Supervisor") else None


# ------------------------------------------------------------------ queries
def closed_stocktakes(port=None, start=None, end=None, limit=200):
    """Closed stocktakes (newest first); start inclusive, end exclusive (datetimes)."""
    q = """SELECT s.stocktake_id, s.port_code, s.warehouse_id, s.closed_at, s.score, s.flagged,
                  s.expected_count, s.present_count, s.missing_count, s.extra_count,
                  w.warehouse_name, COALESCE(p.port_name, s.port_code) AS port_name
           FROM stocktakes s JOIN warehouses w ON w.warehouse_id = s.warehouse_id
           LEFT JOIN ports p ON p.port_code = s.port_code
           WHERE s.status='closed'"""
    a = []
    if port:
        q += " AND s.port_code=%s"; a.append(port)
    if start:
        q += " AND s.closed_at >= %s"; a.append(start)
    if end:
        q += " AND s.closed_at < %s"; a.append(end)
    q += " ORDER BY s.closed_at DESC LIMIT %s"; a.append(limit)
    return fetch_all(q, tuple(a))


def latest_per_warehouse(rows):
    seen, out = set(), []
    for r in rows:                      # rows are newest first
        if r["warehouse_id"] not in seen:
            seen.add(r["warehouse_id"]); out.append(r)
    return out


def months_available(port=None):
    q = "SELECT DISTINCT to_char(closed_at,'YYYY-MM') AS m FROM stocktakes WHERE status='closed'"
    a = []
    if port:
        q += " AND port_code=%s"; a.append(port)
    q += " ORDER BY m DESC"
    return [r["m"] for r in fetch_all(q, tuple(a))]


def month_bounds(ym):
    y, m = map(int, ym.split("-"))
    s = datetime(y, m, 1)
    e = datetime(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return s, e


def aggregate(stocktake_ids):
    """Category × RIH/NOS table plus missing items with their responsible people, for the given stocktakes."""
    if not stocktake_ids:
        return {"categories": [], "missing": [], "extras": [], "totals": {"expected": 0, "present": 0, "missing": 0}}
    ids = tuple(stocktake_ids)
    cats = fetch_all(
        """SELECT COALESCE(i.category,'Other') AS category, e.entry_type,
                  COUNT(*) AS expected, COUNT(*) FILTER (WHERE i.found IS TRUE) AS present,
                  COUNT(*) FILTER (WHERE i.found IS NOT TRUE) AS missing
           FROM stocktake_items i JOIN entries e ON e.entry_id = i.entry_id
           WHERE i.stocktake_id IN %s GROUP BY 1,2""", (ids,))
    missing = fetch_all(
        """SELECT i.stocktake_id, e.entry_number, e.entry_type, e.goods_description,
                  COALESCE(i.category,'Other') AS category, w.warehouse_name,
                  uo.full_name AS officer, us.full_name AS supervisor, um.full_name AS manager, s.flagged
           FROM stocktake_items i
           JOIN stocktakes s ON s.stocktake_id = i.stocktake_id
           JOIN warehouses w ON w.warehouse_id = s.warehouse_id
           JOIN entries e ON e.entry_id = i.entry_id
           LEFT JOIN users uo ON uo.user_id = i.officer_id
           LEFT JOIN users us ON us.user_id = i.supervisor_id
           LEFT JOIN users um ON um.user_id = i.manager_id
           WHERE i.stocktake_id IN %s AND i.found IS NOT TRUE
           ORDER BY s.flagged DESC, w.warehouse_name, e.entry_number""", (ids,))
    extras = fetch_all(
        """SELECT x.description, x.quantity_text, w.warehouse_name FROM stocktake_extras x
           JOIN stocktakes s ON s.stocktake_id = x.stocktake_id JOIN warehouses w ON w.warehouse_id = s.warehouse_id
           WHERE x.stocktake_id IN %s ORDER BY w.warehouse_name, x.extra_id""", (ids,))
    t = {"expected": sum(c["expected"] for c in cats), "present": sum(c["present"] for c in cats),
         "missing": sum(c["missing"] for c in cats)}
    return {"categories": cats, "missing": missing, "extras": extras, "totals": t}


def category_table(cats):
    """-> list of rows [category, RIH exp, RIH miss, NOS exp, NOS miss, total exp, total miss] in CATEGORIES order."""
    by = {}
    for c in cats:
        d = by.setdefault(c["category"], {"RIH": [0, 0], "NOS": [0, 0]})
        k = c["entry_type"] if c["entry_type"] in ("RIH", "NOS") else "RIH"
        d[k][0] += c["expected"]; d[k][1] += c["missing"]
    order = [c for c in CATEGORIES if c in by] + [c for c in by if c not in CATEGORIES]
    return [[c, by[c]["RIH"][0], by[c]["RIH"][1], by[c]["NOS"][0], by[c]["NOS"][1],
             by[c]["RIH"][0] + by[c]["NOS"][0], by[c]["RIH"][1] + by[c]["NOS"][1]] for c in order]


def revenue_between(port, start, end):
    q = """SELECT ar.action_type, COUNT(*) AS n,
                  COALESCE(SUM(ar.amount_collected_usd),0) AS usd, COALESCE(SUM(ar.amount_collected_zwg),0) AS zwg
           FROM action_requests ar JOIN entries e ON e.entry_id = ar.entry_id
           WHERE ar.effected IS TRUE AND COALESCE(ar.effected_at, ar.created_at) >= %s
             AND COALESCE(ar.effected_at, ar.created_at) < %s"""
    a = [start, end]
    if port:
        q += " AND e.port_code=%s"; a.append(port)
    q += " GROUP BY ar.action_type ORDER BY ar.action_type"
    rows = fetch_all(q, tuple(a))
    return rows, sum(float(r["usd"]) for r in rows), sum(float(r["zwg"]) for r in rows)


def ratings(role, stocktake_ids, port=None):
    """Per-person rating for one role: items they were responsible for that were found ÷ all such items.
    People with no items are included (items = 0, rating None)."""
    col = _ROLE_COL[role]
    ids = tuple(stocktake_ids) if stocktake_ids else (-1,)
    q = f"""SELECT u.user_id, u.full_name, u.port_code,
                   COUNT(i.item_id) AS items, COUNT(*) FILTER (WHERE i.found IS TRUE) AS present
            FROM users u JOIN roles r ON r.role_id = u.role_id
            LEFT JOIN stocktake_items i ON i.{col} = u.user_id AND i.stocktake_id IN %s
            WHERE r.role_name=%s AND u.is_active"""
    a = [ids, role]
    if port:
        q += " AND u.port_code=%s"; a.append(port)
    q += " GROUP BY u.user_id, u.full_name, u.port_code ORDER BY u.full_name"
    out = []
    for r in fetch_all(q, tuple(a)):
        r = dict(r)
        r["rating"] = round(100.0 * r["present"] / r["items"], 1) if r["items"] else None
        out.append(r)
    return out


def my_rating(user, stocktake_ids):
    col = _ROLE_COL.get(user["role_name"])
    if not col:
        return None
    for r in ratings(user["role_name"], stocktake_ids, port=None):
        if r["user_id"] == user["user_id"]:
            return r
    return None


def visible_ratings(user, stocktake_ids):
    """[(heading, rows)] according to the hierarchy."""
    role = user["role_name"]
    if role == "Officer":
        r = my_rating(user, stocktake_ids)
        return [("Your rating", [r] if r else [])]
    if role == "Supervisor":
        me = my_rating(user, stocktake_ids)
        return [("Officers at your station", ratings("Officer", stocktake_ids, port=user["port_code"])),
                ("Your rating (goods you approved)", [me] if me else [])]
    if role == "Manager":
        me = my_rating(user, stocktake_ids)
        return [("Supervisors", ratings("Supervisor", stocktake_ids)),
                ("Officers", ratings("Officer", stocktake_ids)),
                ("Your rating (goods you approved)", [me] if me else [])]
    return [("Managers", ratings("Manager", stocktake_ids)), ("Supervisors", ratings("Supervisor", stocktake_ids)),
            ("Officers", ratings("Officer", stocktake_ids))]


# ------------------------------------------------------------------ PDF
def _pdf_base():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    green = colors.HexColor("#1F4E3D")
    base = ParagraphStyle("b", fontName="Times-Roman", fontSize=9, leading=11)
    st = dict(
        base=base, bold=ParagraphStyle("k", parent=base, fontName="Times-Bold"),
        title=ParagraphStyle("t", fontName="Times-Bold", fontSize=14, alignment=1, leading=17),
        sub=ParagraphStyle("s", fontName="Times-Bold", fontSize=12, alignment=1, textColor=green, leading=15),
        h=ParagraphStyle("h", fontName="Times-Bold", fontSize=10, textColor=green, spaceBefore=8, spaceAfter=3),
        warn=ParagraphStyle("w", parent=base, fontName="Times-Bold", textColor=colors.HexColor("#B00020")),
        foot=ParagraphStyle("f", fontName="Times-Italic", fontSize=7, alignment=1, textColor=colors.grey),
        green=green)
    return st


def _fmt(d):
    return d.strftime("%d/%m/%Y %H:%M") if hasattr(d, "strftime") else (str(d) if d else "—")


def _build(title_line, info_rows, blocks, doc_title):
    """blocks: list of ('h', text) | ('p', text) | ('warn', text) | ('t', header, rows, widths_mm)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from xml.sax.saxutils import escape
    from app.entry_documents import _find_logo

    S = _pdf_base()
    P = lambda t, st=S["base"]: Paragraph(escape(str(t if t is not None else "")), st)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=12*mm, bottomMargin=12*mm,
                            title=doc_title, author="ZIMRA")
    el = []
    logo = _find_logo()
    if logo:
        try:
            im = Image(logo, width=20*mm, height=20*mm, kind="proportional"); im.hAlign = "CENTER"; el.append(im)
        except Exception:
            pass
    el += [Paragraph("ZIMBABWE REVENUE AUTHORITY", S["title"]), Paragraph(title_line, S["sub"]), Spacer(1, 4*mm)]
    t = Table([[P(k, S["bold"]), P(v)] for k, v in info_rows], colWidths=[40*mm, 138*mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [t]
    for b in blocks:
        if b[0] == "h":
            el.append(Paragraph(escape(b[1]), S["h"]))
        elif b[0] == "p":
            el.append(P(b[1]))
        elif b[0] == "warn":
            el += [Spacer(1, 3*mm), P(b[1], S["warn"])]
        elif b[0] == "t":
            _, header, rows, widths = b
            if not rows:
                el.append(P("None.")); continue
            data = [[P(x, S["bold"]) for x in header]] + [[P(c) for c in r] for r in rows]
            tb = Table(data, colWidths=[w*mm for w in widths], repeatRows=1)
            tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F5F3")),
                                    ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            el.append(tb)
    el += [Spacer(1, 12*mm)]
    sig = Table([[P("Auditor (Admin)"), P("Supervisor"), P("Manager")]], colWidths=[58*mm] * 3)
    sig.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    el += [sig, Spacer(1, 3*mm), Paragraph(f"System-generated {datetime.now():%d/%m/%Y %H:%M}", S["foot"])]
    doc.build(el)
    return buf.getvalue()


def _money(usd, zwg):
    return f"USD {usd:,.2f}  |  ZWG {zwg:,.2f}"


def _blocks_common(agg, flagged_any):
    b = []
    if flagged_any:
        b.append(("warn", f"POTENTIAL FRAUD INDICATOR: one or more stocktakes scored below {PASS_MARK:.0f}/100. "
                          "The missing entries below are flagged together with the responsible officers."))
    b += [("h", "Goods by category — RIH and NOS (expected / missing)"),
          ("t", ["Category", "RIH exp.", "RIH miss.", "NOS exp.", "NOS miss.", "Total exp.", "Total miss."],
           [[str(x) for x in r] for r in category_table(agg["categories"])], [46, 22, 22, 22, 22, 22, 22]),
          ("h", "FLAGGED / MISSING entries and responsible officers"),
          ("t", ["Entry no.", "Type", "Category", "Goods", "Officer", "Supervisor", "Manager"],
           [[m["entry_number"], m["entry_type"], m["category"], m["goods_description"],
             m["officer"] or "—", m["supervisor"] or "—", m["manager"] or "—"] for m in agg["missing"]],
           [22, 13, 25, 48, 25, 22, 23]),
          ("h", "EXTRA goods found that are not on the system"),
          ("t", ["Description", "Quantity", "Warehouse"],
           [[x["description"], x["quantity_text"] or "", x["warehouse_name"]] for x in agg["extras"]], [100, 30, 48])]
    return b


def build_stocktake_pdf(stocktake_id):
    head = fetch_one(
        """SELECT s.*, w.warehouse_name, COALESCE(p.port_name, s.port_code) AS port_name,
                  u.full_name AS started_by_name, c.full_name AS closed_by_name
           FROM stocktakes s JOIN warehouses w ON w.warehouse_id = s.warehouse_id
           LEFT JOIN ports p ON p.port_code = s.port_code
           LEFT JOIN users u ON u.user_id = s.started_by LEFT JOIN users c ON c.user_id = s.closed_by
           WHERE s.stocktake_id=%s""", (stocktake_id,))
    agg = aggregate([stocktake_id])
    info = [("Warehouse", head["warehouse_name"]), ("Station", head["port_name"]),
            ("Started", f"{_fmt(head['started_at'])} by {head['started_by_name'] or '—'}"),
            ("Closed", f"{_fmt(head['closed_at'])} by {head['closed_by_name'] or '—'}" if head["closed_at"] else "OPEN"),
            ("Result", f"Expected {head['expected_count']} · Present {head['present_count']} · Missing "
                       f"{head['missing_count']} · Extra {head['extra_count']}"),
            ("SCORE", score_badge(head["score"], pdf=True))]
    blocks = _blocks_common(agg, bool(head["flagged"]))
    if head.get("notes"):
        blocks += [("h", "Notes"), ("p", head["notes"])]
    return _build("STOCKTAKE (AUDIT) REPORT", info, blocks, f"Stocktake report {stocktake_id}")


def build_period_pdf(label, port_label, rows, start, end, port, rating_sections):
    latest = latest_per_warehouse(rows)
    agg = aggregate([r["stocktake_id"] for r in latest])
    scored = [float(r["score"]) for r in rows if r["score"] is not None]
    avg = round(sum(scored) / len(scored), 1) if scored else None
    rev, usd, zwg = revenue_between(port, start, end)
    info = [("Period", label), ("Station", port_label), ("Stocktakes in period", str(len(rows))),
            ("Average score", score_badge(avg, pdf=True) if avg is not None else "no stocktake"),
            ("Revenue collected", _money(usd, zwg)),
            ("Goods in stock (latest count)", f"{agg['totals']['expected']} entries on the system, "
                                              f"{agg['totals']['present']} confirmed, {agg['totals']['missing']} missing")]
    blocks = [("h", "Stocktake results"),
              ("t", ["Closed", "Warehouse", "Station", "Exp.", "Present", "Missing", "Extra", "Score"],
               [[_fmt(r["closed_at"]), r["warehouse_name"], r["port_name"], r["expected_count"], r["present_count"],
                 r["missing_count"], r["extra_count"],
                 (f"{float(r['score']):.1f}" + (" FLAGGED" if r["flagged"] else "")) if r["score"] is not None else "—"]
                for r in rows], [27, 38, 28, 12, 15, 15, 12, 31]),
              ("h", "Revenue collected by action"),
              ("t", ["Action", "Count", "USD", "ZWG"],
               [[r["action_type"], r["n"], f"{float(r['usd']):,.2f}", f"{float(r['zwg']):,.2f}"] for r in rev],
               [70, 20, 44, 44])]
    blocks += _blocks_common(agg, any(r["flagged"] for r in rows))
    for heading, plist in rating_sections:
        blocks += [("h", f"Ratings — {heading}"),
                   ("t", ["Name", "Station", "Goods audited", "Found", "Rating"],
                    [[p["full_name"], p["port_code"] or "", p["items"], p["present"],
                      f"{p['rating']:.1f}" if p["rating"] is not None else "no goods"] for p in plist],
                    [62, 30, 32, 24, 30])]
    return _build("STOCKTAKE PERIOD REPORT", info, blocks, f"Stocktake report {label}")


# ------------------------------------------------------------------ UI
def _ratings_ui(st, sections):
    import pandas as pd
    for heading, plist in sections:
        st.markdown(f"**{heading}**")
        if not plist:
            st.caption("Nobody to show."); continue
        df = pd.DataFrame([{"Name": p["full_name"], "Station": p["port_code"], "Goods audited": p["items"],
                            "Found": p["present"],
                            "Rating": (f"{p['rating']:.1f}" + ("" if p["rating"] >= PASS_MARK else "  ⚠")) if p["rating"] is not None else "no goods entered"}
                           for p in plist])
        st.dataframe(df, hide_index=True, use_container_width=True)


def _flagged_ui(st, agg):
    import pandas as pd
    flagged = [m for m in agg["missing"] if m["flagged"]]
    other = [m for m in agg["missing"] if not m["flagged"]]
    if flagged:
        st.error(f"⚠ {len(flagged)} entr{'y' if len(flagged)==1 else 'ies'} flagged — stocktake score below {PASS_MARK:.0f}. Potential fraud.")
    for title, lst in (("Flagged entries and responsible officers", flagged), ("Other missing entries", other)):
        if lst:
            st.markdown(f"**{title}**")
            st.dataframe(pd.DataFrame([{"Entry": m["entry_number"], "Type": m["entry_type"], "Category": m["category"],
                                        "Goods": m["goods_description"], "Warehouse": m["warehouse_name"],
                                        "Officer": m["officer"], "Supervisor": m["supervisor"], "Manager": m["manager"]}
                                       for m in lst]), hide_index=True, use_container_width=True)


def stocktake_reports_tab(user):
    import pandas as pd
    import streamlit as st

    port = _scope_port(user)
    st.subheader("Stocktake Results & Reports")
    st.caption("Stocktakes are carried out by the Admin (audit). Results appear here; monthly reports are available "
               "at the end of every month, or on request for the month to date.")

    recent = closed_stocktakes(port=port, limit=10)
    st.markdown("**Recent stocktake results**")
    if not recent:
        st.info("No stocktake has been completed yet.")
    for r in recent:
        with st.container(border=True):
            st.write(f"**{r['port_name']} — {r['warehouse_name']}** · {r['closed_at']:%d %b %Y} · {score_badge(r['score'])}")
            st.caption(f"Expected {r['expected_count']} · Present {r['present_count']} · "
                       f"Missing {r['missing_count']} · Extra {r['extra_count']}")
            if st.toggle("Prepare report", key=f"srt_tg_{r['stocktake_id']}"):
                st.download_button("⬇ Download stocktake report (PDF)", data=build_stocktake_pdf(r["stocktake_id"]),
                                   file_name=f"Stocktake_{r['stocktake_id']}.pdf", mime="application/pdf",
                                   key=f"srt_dl_{r['stocktake_id']}")

    st.divider()
    st.markdown("**Monthly report**")
    cur_m = date.today().strftime("%Y-%m")
    months = months_available(port)
    options = sorted(set(months) | {cur_m}, reverse=True)
    label = lambda m: (datetime.strptime(m, "%Y-%m").strftime("%B %Y") + (" — month to date (on request)" if m == cur_m else ""))
    ym = st.selectbox("Month", options, format_func=label, key="srt_month")
    start, end = month_bounds(ym)
    rows = closed_stocktakes(port=port, start=start, end=end)
    if not rows:
        st.info("No stocktake was completed in this month.")
    port_label = (fetch_one("SELECT port_name FROM ports WHERE port_code=%s", (port,)) or {}).get("port_name", port) if port else "All stations"
    rev, usd, zwg = revenue_between(port, start, end)
    scored = [float(r["score"]) for r in rows if r["score"] is not None]
    avg = round(sum(scored) / len(scored), 1) if scored else None
    latest = latest_per_warehouse(rows)
    agg = aggregate([r["stocktake_id"] for r in latest])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Average score", f"{avg:.1f}/100" if avg is not None else "—")
    c2.metric("Revenue USD", f"{usd:,.2f}"); c3.metric("Revenue ZWG", f"{zwg:,.2f}")
    c4.metric("Goods in stock", agg["totals"]["expected"])
    if rev:
        st.dataframe(pd.DataFrame([{"Action": r["action_type"], "Count": r["n"], "USD": float(r["usd"]), "ZWG": float(r["zwg"])} for r in rev]),
                     hide_index=True, use_container_width=True)
    ct = category_table(agg["categories"])
    if ct:
        st.markdown("**Goods by category**")
        st.dataframe(pd.DataFrame(ct, columns=["Category", "RIH expected", "RIH missing", "NOS expected", "NOS missing",
                                               "Total expected", "Total missing"]), hide_index=True, use_container_width=True)
    _flagged_ui(st, agg)

    stids = [r["stocktake_id"] for r in rows]
    sections = visible_ratings(user, stids)
    st.markdown("**Ratings for this period**")
    _ratings_ui(st, sections)

    if rows and st.toggle("Prepare this month's report for download", key=f"srt_pdf_{ym}"):
        st.download_button("⬇ Download monthly report (PDF)",
                           data=build_period_pdf(label(ym), port_label, rows, start, end, port, sections),
                           file_name=f"Stocktake_Report_{ym}.pdf", mime="application/pdf", key=f"srt_pdfdl_{ym}")


def render_my_rating(user):
    """Dashboard card: individual rating (last 90 days) + latest stocktake results for the station."""
    import streamlit as st

    port = _scope_port(user)
    since = datetime.now() - timedelta(days=90)
    rows = closed_stocktakes(port=port, start=since)
    st.subheader("Stocktake Rating")
    if not rows:
        st.info("No stocktake has been completed in the last 90 days.")
        return
    latest = latest_per_warehouse(rows)
    cols = st.columns(min(len(latest), 4) or 1)
    for col, r in zip(cols, latest[:4]):
        col.metric(f"{r['warehouse_name']}", f"{float(r['score']):.1f}/100" if r["score"] is not None else "—",
                   "FLAGGED" if r["flagged"] else "Pass", delta_color="inverse" if r["flagged"] else "normal")
    role = user["role_name"]
    if role in _ROLE_COL:
        me = my_rating(user, [r["stocktake_id"] for r in rows])
        if not me or not me["items"]:
            st.info({"Officer": "Your stocktake rating: you did not enter goods into this warehouse. "
                                "You can still open the Stocktake Reports tab for the station's reports.",
                     "Supervisor": "Your stocktake rating: no goods that you approved were in the stocktakes. "
                                   "Station reports are in the Stocktake Reports tab.",
                     "Manager": "Your stocktake rating: no goods that you approved were in the stocktakes. "
                                "Reports are in the Stocktake Reports tab."}[role])
        else:
            msg = f"Your rating: **{me['rating']:.1f}/100** ({me['present']} of {me['items']} goods found)"
            (st.success if me["rating"] >= PASS_MARK else st.error)(msg + ("" if me["rating"] >= PASS_MARK else " — below the 95 pass mark"))

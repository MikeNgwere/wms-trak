"""
E-auction notice with Gazette tracking.

Section 39(3) of the Customs and Excise Act [Chapter 23:02] requires at least one month's
notice in the Gazette before goods held as RIH are sold by public auction. For RIH entries the
system therefore refuses to finalize an e-auction until a Gazette notice is recorded and one
calendar month has passed. NOS entries (forfeited under s.193(13)) are not gated.
"""
import calendar
from datetime import date, datetime
from io import BytesIO

from app.db import fetch_all, fetch_one
from app import entry_documents as ed
from app.entry_documents import (W, H, LM, RM, _s, _label, _dotted, _fill, _field, _para, _find_logo,
                                 _header, _goods_table, _draw_stamp, _vehicle_lines, _draw_qr_url, FORM)


def add_one_month(d):
    y, m = (d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def latest_notice(entry_id):
    return fetch_one("SELECT * FROM auction_notices WHERE entry_id=%s ORDER BY notice_id DESC LIMIT 1", (entry_id,))


def requires_gazette(entry_id):
    r = fetch_one("SELECT entry_type FROM entries WHERE entry_id=%s", (entry_id,))
    return bool(r and r["entry_type"] == "RIH")


def notice_status(entry_id, today=None):
    """-> {state, notice, earliest, days_left, required}; state: none | waiting | ready | not_required."""
    today = today or date.today()
    n = latest_notice(entry_id)
    req = requires_gazette(entry_id)
    if not n:
        return {"state": "none" if req else "not_required", "notice": None, "earliest": None, "days_left": None, "required": req}
    earliest = add_one_month(n["gazette_date"])
    gate = max(earliest, n["auction_date"]) if req else n["auction_date"]
    left = (gate - today).days
    state = "ready" if left <= 0 else "waiting"
    if not req:
        state = "ready" if n["auction_date"] <= today else "waiting"
    return {"state": state, "notice": n, "earliest": earliest, "days_left": max(left, 0), "required": req}


def can_finalize_auction(entry_id, today=None):
    s = notice_status(entry_id, today)
    if s["state"] in ("ready", "not_required"):
        return True, "OK"
    if s["state"] == "none":
        return False, "No Gazette notice recorded. Record the Gazette notice first (section 39(3): one month's notice)."
    return False, (f"The one-month Gazette notice period is still running. The sale may not be finalized before "
                   f"{max(s['earliest'], s['notice']['auction_date']):%d %b %Y} ({s['days_left']} day(s) left).")


def create_notice(entry_id, user_id, gazette_date, gazette_reference, auction_date, platform):
    if auction_date < gazette_date:
        raise ValueError("The auction date cannot be before the Gazette date.")
    if requires_gazette(entry_id) and auction_date < add_one_month(gazette_date):
        raise ValueError(f"Section 39(3) requires at least one month's Gazette notice. "
                         f"The earliest auction date is {add_one_month(gazette_date):%d %b %Y}.")
    return fetch_one(
        """INSERT INTO auction_notices (entry_id, gazette_date, gazette_reference, auction_date, auction_platform, created_by)
           VALUES (%s,%s,%s,%s,%s,%s) RETURNING notice_id""",
        (entry_id, gazette_date, gazette_reference or None, auction_date, platform or None, user_id))["notice_id"]


# ------------------------------------------------------------------ PDF
def fetch_notice_data(notice_id):
    return fetch_one(
        """SELECT n.*, e.entry_number, e.entry_type, e.port_code, e.goods_description, e.date_entered,
                  e.is_vehicle, e.quantity_units, p.port_name, w.warehouse_name,
                  rih.rih_number, nos.nos_number,
                  v.registration_number, v.chassis_number, v.engine_number, v.make, v.model, v.colour, v.year_of_manufacture,
                  u.full_name AS created_by_name
           FROM auction_notices n JOIN entries e ON e.entry_id = n.entry_id
           LEFT JOIN ports p ON p.port_code = e.port_code LEFT JOIN warehouses w ON w.warehouse_id = e.warehouse_id
           LEFT JOIN rih_details rih ON rih.entry_id = e.entry_id LEFT JOIN nos_details nos ON nos.entry_id = e.entry_id
           LEFT JOIN vehicle_details v ON v.entry_id = e.entry_id LEFT JOIN users u ON u.user_id = n.created_by
           WHERE n.notice_id = %s""", (notice_id,))


def build_notice_pdf(d):
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Notice of E-Auction NTC/{int(d['notice_id']):05d}")
    c.setAuthor("ZIMRA")
    logo = _find_logo()
    _header(c, "NOTICE OF PUBLIC E-AUCTION", "Notice No.", f"NTC/{int(d['notice_id']):05d}", logo)
    _draw_qr_url(c, f"{ed._base_url()}/Verify_Document?t=NOTICE&no={int(d['notice_id'])}")
    rih = d["entry_type"] == "RIH"
    num = ("RIH No. " + (_s(d.get("rih_number")) or _s(d["entry_number"]))) if rih else \
          ("NOS No. " + (_s(d.get("nos_number")) or _s(d["entry_number"])))
    y = H - 176
    if rih:
        law = ("NOTICE is hereby given in terms of section 39(3) of the Customs and Excise Act [Chapter 23:02] that the goods "
               "described below, which were not entered within the period allowed by the Act, will be sold by public auction ")
    else:
        law = ("NOTICE is hereby given that the goods described below, which have been forfeited to the State in terms of "
               "section 193 of the Customs and Excise Act [Chapter 23:02], will be sold by public auction ")
    plat = _s(d.get("auction_platform")) or "through the ZIMRA e-auction system"
    text = (law + f"on {d['auction_date']:%d %B %Y}, {('through ' + plat) if not plat.lower().startswith('through') else plat}. "
            f"This notice was published in the Government Gazette dated {d['gazette_date']:%d %B %Y}"
            + (f" (Reference: {d['gazette_reference']})" if d.get("gazette_reference") else "") + ".")
    y = _para(c, text, LM, y, RM - LM, 10, lead=13)
    left = _vehicle_lines(d) if d.get("is_vehicle") else [ln for ln in (d.get("goods_description") or "").split("\n") if ln][:5] or [""]
    right = [num.upper(), f"ENTRY NO: {_s(d['entry_number'])}", f"STATION: {_s(d.get('port_name')).upper()}",
             f"STORED AT: {_s(d.get('warehouse_name')).upper()}", f"DETAINED: {_s(d.get('date_entered'))}"]
    bottom = _goods_table(c, y - 24, 7, (_s(d.get("quantity_units")).upper(), left), right, "Goods to be sold")
    y = bottom - 28
    c.setFillColorRGB(*FORM); c.setFont("Times-Bold", 9); c.drawString(LM, y + 10, "AUCTION DETAILS")
    for lab, val in (("Gazette date:", f"{d['gazette_date']:%d/%m/%Y}"), ("Gazette reference:", d.get("gazette_reference")),
                     ("Date of auction:", f"{d['auction_date']:%d/%m/%Y}"), ("Auction platform:", d.get("auction_platform") or "ZIMRA e-auction system")):
        _field(c, LM, y - 6, lab, _s(val), RM); y -= 21
    y = _para(c, "The owner or any person lawfully entitled to the goods may, before the sale, apply to the Station Manager, "
                 f"{_s(d.get('port_name'))}, to claim them on payment of all duty, penalties and State Warehouse rent due. "
                 "Goods not claimed will be sold to the highest bidder.", LM, y - 8, RM - LM, 9.5, lead=12)
    y -= 26
    _label(c, LM, y, "Issued by:", 9); _fill(c, LM + 48, y - 1, _s(d.get("created_by_name")), 10)
    _dotted(c, LM + 50, 280, y - 1)
    _label(c, LM, y - 26, "Signature of Station Manager", 9)
    _dotted(c, LM + 140, 330, y - 27)
    _draw_stamp(c, 500, 190, 40, {"date_entered": d.get("created_at")})
    c.setFont("Times-Italic", 7); c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(W / 2, 12, f"System-generated {datetime.now():%d/%m/%Y %H:%M} · {num} · Entry {d.get('entry_number', '')}")
    c.showPage(); c.save()
    return buf.getvalue()


# ------------------------------------------------------------------ UI
def auction_notice_panel(user, entry_id, key):
    """Gazette tracking for one e-auction. Returns True when the sale may be finalized."""
    import streamlit as st
    s = notice_status(entry_id)
    ok, why = can_finalize_auction(entry_id)
    n = s["notice"]
    st.markdown("**Gazette notice (section 39(3))**" if s["required"] else "**Auction notice**")
    if n:
        st.write(f"Gazette date **{n['gazette_date']:%d %b %Y}**"
                 + (f" · Ref **{n['gazette_reference']}**" if n["gazette_reference"] else "")
                 + f" · Auction date **{n['auction_date']:%d %b %Y}**"
                 + (f" · Earliest lawful sale **{s['earliest']:%d %b %Y}**" if s["required"] else ""))
    (st.success if ok else st.warning)(("✅ Notice period complete — the sale can be finalized." if ok else "⏳ " + why))
    with st.expander("Record / replace Gazette notice" if n else "Record Gazette notice", expanded=not n):
        with st.form(f"gz_{key}"):
            c1, c2 = st.columns(2)
            gd = c1.date_input("Gazette date", value=date.today(), key=f"gzd_{key}")
            ad = c2.date_input("Auction date", value=add_one_month(date.today()), key=f"gza_{key}")
            ref = st.text_input("Gazette reference / notice number", key=f"gzr_{key}")
            plat = st.text_input("Auction platform / venue", value="ZIMRA e-auction system", key=f"gzp_{key}")
            if st.form_submit_button("Save Gazette notice", type="primary"):
                try:
                    create_notice(entry_id, user["user_id"], gd, ref.strip(), ad, plat.strip())
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    if n and st.toggle("📄 View / print Notice of E-Auction", key=f"gzv_{key}"):
        import base64
        import streamlit.components.v1 as components
        pdf = build_notice_pdf(fetch_notice_data(n["notice_id"]))
        b64 = base64.b64encode(ed.pdf_to_png(pdf)).decode()
        components.html(
            f"""<style>@media print{{.np{{display:none}} @page{{size:A4;margin:0}} body{{margin:0}}}}</style>
<div class='np' style='text-align:right;margin-bottom:6px'><button onclick='window.print()' style='padding:6px 16px;background:#1F4E3D;color:#fff;border:0;border-radius:4px;cursor:pointer'>🖨 Print</button></div>
<img src='data:image/png;base64,{b64}' style='width:100%;border:1px solid #ccc'>""", height=1050, scrolling=True)
        st.download_button("⬇ Download Notice (PDF)", data=pdf, file_name=f"Auction_Notice_{n['notice_id']}.pdf",
                           mime="application/pdf", key=f"gzdl_{key}")
    return ok


def auction_tracking_rows(rows):
    """For the dashboard: pending e-auction rows with their Gazette-notice state."""
    out = []
    for r in rows or []:
        r = dict(r)
        if r.get("action_type") != "e_auction":
            continue
        eid = r.get("entry_id") or ed._resolve_entry_id(r)
        if not eid:
            continue
        s = notice_status(eid)
        n = s["notice"]
        out.append({
            "Entry": r.get("entry_number"), "Type": r.get("entry_type"),
            "Gazette date": f"{n['gazette_date']:%d %b %Y}" if n else "—",
            "Earliest lawful sale": f"{s['earliest']:%d %b %Y}" if s["earliest"] and s["required"] else "—",
            "Auction date": f"{n['auction_date']:%d %b %Y}" if n else "—",
            "Status": {"none": "🔴 No Gazette notice", "waiting": f"🟡 Waiting — {s['days_left']} day(s) left",
                       "ready": "🟢 Ready to sell", "not_required": "— (no Gazette required)"}[s["state"]],
        })
    return out

"""
Printable ZIMRA forms generated from an entry:
  RIH -> "Receipt for Items Held"      NOS -> "Notice of Seizure"
Layouts follow the paper forms. Typed values print in blue so they stand apart
from the printed form wording; blanks stay blank for handwriting (signature,
stamp, handover, clearance, disposal).

  fetch_entry_document_data(entry_id) -> dict
  build_entry_pdf(data)               -> PDF bytes (A4, one page)
  render_entry_document(entry_id, key)-> Streamlit widget (View / Print / Download)
"""
import os
from datetime import datetime, date
from io import BytesIO

from app.db import fetch_one

INK = (0.05, 0.15, 0.55)      # typed values
FORM = (0, 0, 0)              # printed form wording

_SQL = """
SELECT e.entry_id, e.entry_number, e.entry_type, e.goods_description, e.declared_value,
       e.date_entered, e.bond_due_date, e.expiry_date, e.status,
       e.importer_name, e.importer_address, e.importer_contact,
       e.is_vehicle, e.quantity_units, e.rent_charge_per_day,
       p.port_name, w.warehouse_name,
       r.rih_number, r.reason_category, r.reason_narrative, r.act_clause,
       iss.full_name AS issuing_officer_name,
       n.nos_number, n.seizing_officer_ec_number, n.offence_committed,
       n.act_section_breached, n.marks_and_numbers,
       sz.full_name AS seizing_officer_name,
       cap.full_name AS captured_by_name,
       v.registration_number, v.chassis_number, v.engine_number, v.make, v.model,
       v.colour, v.year_of_manufacture
FROM entries e
LEFT JOIN ports p            ON p.port_code = e.port_code
LEFT JOIN warehouses w       ON w.warehouse_id = e.warehouse_id
LEFT JOIN users cap          ON cap.user_id = COALESCE(e.captured_by, e.officer_id)
LEFT JOIN rih_details r      ON r.entry_id = e.entry_id
LEFT JOIN users iss          ON iss.user_id = r.issuing_officer_id
LEFT JOIN nos_details n      ON n.entry_id = e.entry_id
LEFT JOIN users sz           ON sz.user_id = n.seizing_officer_id
LEFT JOIN vehicle_details v  ON v.entry_id = e.entry_id
WHERE e.entry_id = %s
"""


def fetch_entry_document_data(entry_id):
    return fetch_one(_SQL, (entry_id,))


def _s(v):
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.strftime("%d/%m/%Y")
    return str(v)


def _find_logo():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in ("assets/zimra_logo.png", "zimra_logo.png", "../assets/zimra_logo.png",
              "../zimra_logo.png", "static/zimra_logo.png"):
        f = os.path.normpath(os.path.join(here, p))
        if os.path.exists(f):
            return f
    root = os.path.dirname(here)
    for dp, dn, files in os.walk(root):
        dn[:] = [d for d in dn if d not in ("venv", ".git", "__pycache__")]
        for fn in files:
            if "logo" in fn.lower() and fn.lower().endswith((".png", ".jpg", ".jpeg")):
                return os.path.join(dp, fn)
    return None


# ---------- low-level drawing ----------
W, H = 595.27, 841.89
LM, RM = 40, 555


def _wrap(c, text, font, size, width):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    out = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split():
            t = (line + " " + word).strip()
            if stringWidth(t, font, size) <= width:
                line = t
            else:
                if line:
                    out.append(line)
                line = word
        out.append(line)
    return out


def _label(c, x, y, text, size=9, font="Times-Bold"):
    c.setFillColorRGB(*FORM)
    c.setFont(font, size)
    c.drawString(x, y, text)
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return x + stringWidth(text, font, size)


def _dotted(c, x1, x2, y):
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.6)
    c.setDash(1, 2)
    c.line(x1, y, x2, y)
    c.setDash()


def _fill(c, x, y, text, size=10, maxw=None):
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Oblique", size)
    if maxw:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        while stringWidth(text, "Helvetica-Oblique", size) > maxw and size > 6:
            size -= 0.5
        c.setFont("Helvetica-Oblique", size)
    c.drawString(x + 3, y + 2, text)


def _field(c, x, y, label, value, x2, size=10):
    """Printed label, dotted leader to x2, typed value sitting on the dots."""
    x0 = _label(c, x, y, label)
    _dotted(c, x0 + 2, x2, y - 1)
    if value:
        _fill(c, x0 + 2, y - 1, value, size, maxw=x2 - x0 - 8)


def _header(c, title, serial_label, serial, logo, left_note=None):
    if left_note:
        c.setFont("Times-Roman", 8)
        c.setFillColorRGB(*FORM)
        c.drawString(LM, H - 34, left_note)
    if logo:
        try:
            c.drawImage(logo, W / 2 - 28, H - 98, width=56, height=56,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    c.setFillColorRGB(*FORM)
    c.setFont("Times-Bold", 11)
    c.drawRightString(RM - 52, H - 72, serial_label)
    c.setFillColorRGB(0.75, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(RM - 48, H - 73, serial)
    c.setFillColorRGB(*FORM)
    c.setFont("Times-Bold", 14)
    c.drawCentredString(W / 2, H - 116, "ZIMBABWE REVENUE AUTHORITY")
    c.setFont("Times-Bold", 14 if "RECEIPT" in title else 18)
    c.drawCentredString(W / 2, H - 140, title)


def _para(c, text, x, y, width, size=8.5, font="Times-Roman", lead=10.5, justify=False):
    c.setFillColorRGB(*FORM)
    c.setFont(font, size)
    for ln in _wrap(c, text, font, size, width):
        c.drawString(x, y, ln)
        y -= lead
    return y


def _goods_table(c, top, rows, left_lines, right_lines, title):
    """Quantity|Description|Quantity|Description grid, `rows` ruled rows."""
    c.setFillColorRGB(*FORM)
    c.setFont("Times-Bold", 8.5)
    c.drawString(LM, top + 6, title)
    xs = [LM, LM + 55, LM + 255, LM + 305, RM]
    rh = 15.5
    head_h = 16
    bottom = top - head_h - rows * rh
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.8)
    c.line(LM, top, RM, top)
    c.setFont("Times-Roman", 9)
    for i, h in enumerate(("Quantity", "Description", "Quantity", "Description")):
        c.drawCentredString((xs[i] + xs[i + 1]) / 2, top - 11.5, h)
    c.setLineWidth(0.5)
    c.line(LM, top - head_h, RM, top - head_h)
    for r in range(1, rows + 1):
        yy = top - head_h - r * rh
        c.setLineWidth(0.35)
        c.line(LM, yy, RM, yy)
    c.setLineWidth(0.6)
    for x in xs[1:4]:
        c.line(x, top - head_h, x, bottom)
    c.line(LM, bottom, RM, bottom)
    # typed content
    def put(lines, xcol, wcol):
        for i, ln in enumerate(lines[:rows]):
            if ln:
                _fill(c, xcol, top - head_h - (i + 1) * rh + 2, ln, 9.5, maxw=wcol - 8)
    c.setFillColorRGB(*INK)
    for qx, txt in ((xs[0], left_lines[0]),):
        if txt:
            _fill(c, xs[0], top - head_h - rh + 2, txt, 9.5, maxw=50)
    put(left_lines[1], xs[1], xs[2] - xs[1])
    put(right_lines, xs[3], xs[4] - xs[3])
    # cross out unused rows (form instruction)
    used = max(len(left_lines[1]), len(right_lines), 1)
    if used < rows:
        y1 = top - head_h - used * rh - 3
        y2 = bottom + 3
        c.setStrokeColorRGB(*INK)
        c.setLineWidth(0.9)
        for a, b in ((xs[1], xs[2]), (xs[3], xs[4])):
            c.line(a + 6, y1, b - 6, y2)
        c.line(xs[0] + 6, y1, xs[1] - 6, y2)
    return bottom


def _draw_stamp(c, cx, cy, r, d):
    """System-generated round date stamp: authority name round the rim, WMS in the
    centre, date the entry was captured beneath."""
    import math
    from reportlab.pdfbase.pdfmetrics import stringWidth
    ink = (0.12, 0.22, 0.62)
    when = d.get("date_entered")
    date_txt = when.strftime("%d %b %Y").upper() if hasattr(when, "strftime") else _s(when)
    c.saveState()
    c.translate(cx, cy)
    c.rotate(-6)
    c.setStrokeColorRGB(*ink)
    c.setFillColorRGB(*ink)
    c.setLineWidth(1.6)
    c.circle(0, 0, r, stroke=1, fill=0)
    c.setLineWidth(0.7)
    c.circle(0, 0, r - 3, stroke=1, fill=0)
    inner = r * 0.62
    c.setLineWidth(1.0)
    c.circle(0, 0, inner, stroke=1, fill=0)
    # text round the rim (reads clockwise from the left, across the top)
    text = "ZIMBABWE REVENUE AUTHORITY"
    size = r * 0.19
    font = "Helvetica-Bold"
    rad = (r + inner) / 2 - size * 0.35
    widths = [stringWidth(ch, font, size) for ch in text]
    total = sum(widths) + 1.2 * size * 0  # arc length
    span = total / rad
    ang = math.pi / 2 + span / 2
    c.setFont(font, size)
    for ch, w in zip(text, widths):
        mid = ang - (w / 2) / rad
        c.saveState()
        c.translate(rad * math.cos(mid), rad * math.sin(mid))
        c.rotate(math.degrees(mid) - 90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
        ang -= w / rad
    # small stars at the bottom of the rim
    c.setFont("Helvetica-Bold", size)
    for a in (-math.pi / 2 - 0.35, -math.pi / 2, -math.pi / 2 + 0.35):
        c.saveState()
        c.translate(rad * math.cos(a), rad * math.sin(a))
        c.rotate(math.degrees(a) + 90)
        c.drawCentredString(0, -size * 0.3, "*")
        c.restoreState()
    # centre
    c.setFont("Helvetica-Bold", r * 0.36)
    c.drawCentredString(0, r * 0.06, "WMS")
    c.setFont("Helvetica-Bold", r * 0.15)
    c.drawCentredString(0, -r * 0.30, date_txt)
    c.restoreState()


def _vehicle_lines(d):
    out = []
    if not d.get("is_vehicle"):
        return out
    mm = " ".join(x for x in (_s(d.get("make")), _s(d.get("model"))) if x)
    if mm:
        out.append(mm.upper())
    for lab, key in (("REG # ", "registration_number"), ("CHS # ", "chassis_number"),
                     ("ENG # ", "engine_number")):
        if d.get(key):
            out.append(lab + _s(d[key]).upper())
    if d.get("year_of_manufacture"):
        out.append("YOM : " + _s(d["year_of_manufacture"]))
    if d.get("colour"):
        out.append("COLOUR : " + _s(d["colour"]).upper())
    return out


def _goods_lines(c, d, width):
    desc = _s(d.get("goods_description")).upper()
    lines = []
    veh = _vehicle_lines(d)
    if veh:
        lines += veh
        if desc:
            lines += _wrap(c, desc, "Helvetica-Oblique", 9.5, width - 8)
    else:
        lines += _wrap(c, desc, "Helvetica-Oblique", 9.5, width - 8)
    return lines


def _qty(d):
    q = _s(d.get("quantity_units"))
    return (q + " X") if q else "1 X"


# ---------- RIH ----------
def _draw_rih(c, d, logo):
    _header(c, "RECEIPT FOR ITEMS HELD", "Serial No.", _s(d.get("rih_number")) or _s(d.get("entry_number")), logo)
    y = H - 178
    x_mid = 330
    _field(c, LM, y, "To (Surname):", _s(d.get("importer_name")), x_mid - 15)
    _label(c, x_mid, y, "Address:")
    _dotted(c, x_mid + 42, RM, y - 1)
    addr = _s(d.get("importer_address"))
    if addr:
        _fill(c, x_mid + 42, y - 1, addr, 9.5, maxw=RM - x_mid - 48)
    y2 = y - 24
    _field(c, LM, y2, "(Other names):", "", x_mid - 15)
    _dotted(c, x_mid, RM, y2 - 1)
    _dotted(c, x_mid, RM, y2 - 25)
    contact = _s(d.get("importer_contact"))
    if contact:
        _fill(c, x_mid, y2 - 25, contact, 9.5, maxw=RM - x_mid - 6)
    txt = ("You are hereby notified that the goods described below have been detained for the stated "
           "reason(s) and the prescribed State Warehouse rent is payable from date of detention. If they "
           "remain uncleared for two months from date of this notice, they will be sold in terms of "
           "section 39 of the Customs and Excise Act [Chapter 23:02]")
    y3 = _para(c, txt, LM + 10, y2 - 52, RM - LM - 10, size=8.8, lead=11)
    # goods
    rows = 12
    top = y3 - 22
    lines = _goods_lines(c, d, 200)
    notes = []
    if d.get("expiry_date"):
        notes.append("EXPIRY DATE: " + _s(d["expiry_date"]))
    if d.get("warehouse_name"):
        notes.append("STORED AT: " + _s(d["warehouse_name"]).upper())
    notes.append("ENTRY NO: " + _s(d.get("entry_number")))
    bottom = _goods_table(c, top, rows, (_qty(d), lines), notes, "GOODS DETAINED")
    c.setFillColorRGB(*FORM)
    c.setFont("Times-Italic", 8)
    c.drawCentredString(W / 2, bottom - 12, "(N.B All unused lines to be crossed out)")
    # reasons
    ry = bottom - 34
    c.setFont("Times-Bold", 8.5)
    c.setFillColorRGB(*FORM)
    c.drawString(LM, ry, "REASON(S) FOR DETENTION")
    reason = " ".join(x for x in (_s(d.get("reason_category")) + ("." if d.get("reason_category") else ""),
                                  _s(d.get("reason_narrative")),
                                  ("(" + _s(d.get("act_clause")) + ")") if d.get("act_clause") else "") if x)
    rl = _wrap(c, reason, "Helvetica-Oblique", 9.5, RM - LM - 8)
    nrows = 5
    for i in range(nrows):
        yy = ry - 17 - i * 16
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.35)
        c.line(LM, yy, RM, yy)
        if i < len(rl):
            _fill(c, LM, yy, rl[i], 9.5)
    # rent note (right of the heading)
    if d.get("rent_charge_per_day") not in (None, ""):
        c.setFont("Times-Roman", 8.5)
        c.setFillColorRGB(*FORM)
        c.drawString(330, ry, "State Warehouse rent per day (USD):")
        _fill(c, 480, ry, _s(d["rent_charge_per_day"]), 9.5)
    # signature block
    sy = 190
    xr = 400
    officer = _s(d.get("issuing_officer_name") or d.get("captured_by_name"))
    _field(c, LM, sy, "Date of Detention", _s(d.get("date_entered")), xr)
    _field(c, LM, sy - 24, "Name of Officer", officer, xr)
    _field(c, LM, sy - 48, "Signature of Officer", "", xr)
    _field(c, LM, sy - 72, "Revenue Office", _s(d.get("port_name")), xr)
    _field(c, LM, sy - 96, "Handover/Takeover", "", xr)
    _field(c, LM, sy - 120, "Clearance Details", "", xr)
    c.setFont("Times-Roman", 9)
    c.drawString(LM + 12, sy - 138, "or")
    x0 = _label(c, LM, sy - 158, "Disposal Details: Lot No:", 9, "Times-Roman")
    _dotted(c, x0 + 2, xr - 40, sy - 159)
    x1 = _label(c, xr - 36, sy - 158, "of 20", 9, "Times-Roman")
    _dotted(c, x1 + 2, xr + 20, sy - 159)
    _draw_stamp(c, 482, sy - 92, 52, d)


# ---------- NOS ----------
def _draw_nos(c, d, logo):
    _header(c, "NOTICE OF SEIZURE", "No.", _s(d.get("nos_number")) or _s(d.get("entry_number")), logo)
    y = H - 168
    c.setFont("Times-Roman", 8.3)
    c.setFillColorRGB(*FORM)
    c.drawString(LM, y, "To: Full names in the case of an individual, or registered name in the case of a company, or other form of organisation)")
    _dotted(c, LM, RM, y - 17)
    _fill(c, LM, y - 17, _s(d.get("importer_name")), 10.5, maxw=RM - LM - 8)
    _field(c, LM, y - 40, "(Other names)", "", RM, 10)
    _field(c, LM, y - 62, "Address", _s(d.get("importer_address")), RM)
    _field(c, LM, y - 84, "Phone/Fax No.", _s(d.get("importer_contact")), RM)
    txt = ("You are hereby notified that the goods described below have been seized in terms of the Customs and "
           "Excise Act [Chapter 23:02], as amended, because there are reasonable grounds for believing that they "
           "are liable for seizure.")
    y2 = _para(c, txt, LM, y - 108, RM - LM, size=8.8, lead=11)
    c.setFont("Times-Bold", 8.5)
    rows = 11
    top = y2 - 18
    lines = _goods_lines(c, d, 200)
    notes = []
    off = _s(d.get("offence_committed"))
    if off:
        notes += _wrap(c, "OFFENCE: " + off.upper(), "Helvetica-Oblique", 9.5, 190)
    if d.get("act_section_breached"):
        notes.append("SECTION BREACHED: " + _s(d["act_section_breached"]).upper())
    if d.get("marks_and_numbers"):
        notes.append("MARKS/NOS: " + _s(d["marks_and_numbers"]).upper())
    if d.get("rent_charge_per_day") not in (None, ""):
        notes.append("STORAGE: USD " + _s(d["rent_charge_per_day"]) + " PER DAY")
    if d.get("warehouse_name"):
        notes.append("STORED AT: " + _s(d["warehouse_name"]).upper())
    bottom = _goods_table(c, top, rows, (_qty(d), lines), notes, "Goods seized:")
    # officer block
    sy = bottom - 22
    officer = _s(d.get("seizing_officer_name") or d.get("captured_by_name"))
    _field(c, LM, sy, "Name of Officer", officer, 300)
    _field(c, 306, sy, "Signature of Officer", "", 470 - 20 + 85)
    _field(c, LM, sy - 22, "Location of Seizure", _s(d.get("port_name")), 250)
    _field(c, 256, sy - 22, "Section", "", 400)
    c.setFont("Times-Italic", 8.3)
    c.setFillColorRGB(*FORM)
    c.drawString(410, sy - 22, "*Major/Minor Seizure")
    _field(c, 430, sy - 44, "Date", _s(d.get("date_entered")), RM)
    # statutory text
    ty = sy - 52
    c.setFont("Times-Roman", 8.5)
    c.setFillColorRGB(*FORM)
    c.drawString(LM, ty, "In terms of section 193 of the Act, the Commissioner General may—")
    ty -= 13
    for t in ("(a)  release these goods from seizure; or", "(b)  declare them to be forfeited; or"):
        c.drawString(LM + 8, ty, t)
        ty -= 12
    ty = _para(c, "(c)  in the case of dangerous or perishable goods, direct that they be sold out of hand or, if they cannot be sold, that they be destroyed or appropriated to the State.",
               LM + 8, ty, 330, size=8.5, lead=10.5)
    _draw_stamp(c, 482, sy - 84, 32, d)
    ty -= 16
    blocks = [
        "If you wish, you may, within three months from the date of this notice, make written representations to the Station Manager of the Station where your goods were seized, stating your reasons why the goods should not be dealt with in the manner prescribed in paragraphs (b) and (c) above.",
        "Additionally or alternatively you may, within the three months from the date of this notice and subject to the submission of written notification 60 days beforehand in terms of section 196 of the Act, institute proceedings for the recovery of the goods from the Commissioner General, or for the payment of compensation in respect of goods which have been disposed of by the Commissioner General.",
        "If the Commissioner General does not release the goods following representations made by you or if you do not institute proceedings in the period specified, any goods declared to be forfeited shall become the property of the State without compensation.",
        "NOTE.—It is imperative that any representations clearly state the full names of the person, company or other form of organisation from whom the goods were seized together with this Notice of Seizure number, date and place of seizure.",
    ]
    for b in blocks:
        ty = _para(c, b, LM, ty, RM - LM, size=8.5, lead=10.5) - 5


def build_entry_pdf(d):
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    title = "Receipt for Items Held" if d["entry_type"] == "RIH" else "Notice of Seizure"
    c.setTitle(f"{title} {d.get('entry_number', '')}")
    c.setAuthor("ZIMRA")
    logo = _find_logo()
    if d["entry_type"] == "RIH":
        _draw_rih(c, d, logo)
    else:
        _draw_nos(c, d, logo)
    c.setFont("Times-Italic", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(W / 2, 12, f"System-generated {datetime.now().strftime('%d/%m/%Y %H:%M')} · Entry {d.get('entry_number', '')}")
    c.showPage()
    c.save()
    return buf.getvalue()


def pdf_to_png(pdf_bytes, zoom=1.6):
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")


# ---------- Streamlit widgets ----------
def _resolve_entry_id(row):
    """Return an entry_id for a list row: use entry_id if present, else look it up by entry_number."""
    if not isinstance(row, dict) and hasattr(row, "keys"):
        row = dict(row)
    if row.get("entry_id"):
        return row["entry_id"]
    num = row.get("entry_number")
    if not num:
        return None
    et = row.get("entry_type")
    if et in ("RIH", "NOS"):
        found = fetch_one("SELECT entry_id FROM entries WHERE entry_number=%s AND entry_type=%s ORDER BY entry_id DESC LIMIT 1", (num, et))
    else:
        found = fetch_one("SELECT entry_id FROM entries WHERE entry_number=%s ORDER BY entry_id DESC LIMIT 1", (num,))
    return found["entry_id"] if found else None


def render_entry_document(entry_id, key):
    """Toggle 'View RIH/NOS' for one entry; the PDF is only built when switched on."""
    import base64
    import streamlit as st
    import streamlit.components.v1 as components

    if not entry_id:
        return
    head = fetch_one("SELECT entry_type, entry_number FROM entries WHERE entry_id=%s", (entry_id,))
    if not head:
        return
    kind = head["entry_type"]
    if not st.toggle(f"📄 View / print {kind} — {head['entry_number']}", key=f"vt_{key}_{entry_id}"):
        return
    d = fetch_entry_document_data(entry_id)
    if not d:
        return
    pdf = build_entry_pdf(d)
    b64 = base64.b64encode(pdf_to_png(pdf)).decode()
    components.html(
        f"""<style>@media print{{.np{{display:none}} @page{{size:A4;margin:0}} body{{margin:0}}}}</style>
<div class='np' style='text-align:right;margin-bottom:6px'>
<button onclick='window.print()' style='padding:6px 16px;background:#1F4E3D;color:#fff;border:0;border-radius:4px;cursor:pointer'>🖨 Print</button></div>
<img src='data:image/png;base64,{b64}' style='width:100%;border:1px solid #ccc'>""",
        height=1050, scrolling=True)
    st.download_button(f"⬇ Download {kind} (PDF)", data=pdf,
                       file_name=f"{kind}_{d.get('entry_number', entry_id)}.pdf",
                       mime="application/pdf", key=f"dl_{key}_{entry_id}")


def render_entry_document_for_row(row, key):
    """For a card/row that represents one entry (or a request about one)."""
    try:
        eid = _resolve_entry_id(row)
    except Exception:
        eid = None
    if eid:
        render_entry_document(eid, key=f"{key}_{eid}")


def entry_document_picker(rows, key, label="📄 Open RIH / NOS document for an entry"):
    """Under a table of entries: choose one entry, then view / print / download its document."""
    import streamlit as st
    try:
        rows = [dict(r) for r in (rows or [])]
    except Exception:
        return
    options = {}
    for r in rows:
        num = r.get("entry_number")
        if num:
            options[f"{num} ({r['entry_type']})" if r.get("entry_type") else str(num)] = r
    if not options:
        return
    pick = st.selectbox(label, list(options.keys()), index=None,
                        placeholder="Select an entry…", key=f"pick_{key}")
    if pick:
        render_entry_document_for_row(options[pick], key=f"pk_{key}")
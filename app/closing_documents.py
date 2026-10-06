"""
Printable closing documents, produced once an action has been FINALIZED:

  release_to_owner -> RELEASE RECEIPT
  forfeiture       -> FORFEITURE / APPROPRIATION RECORD
  destruction      -> CERTIFICATE OF DESTRUCTION
  e_auction        -> E-AUCTION SALE RECORD

  fetch_closing_data(request_id) -> dict
  build_closing_pdf(d)           -> PDF bytes (A4, one page)
  render_closing_document(entry_id, key) -> Streamlit widget (View / Print / Download)
"""
from datetime import datetime, date
from io import BytesIO

from app.db import fetch_one, fetch_all
from app import entry_documents as ed
from app.entry_documents import (W, H, LM, RM, _s, _label, _dotted, _fill, _field, _para, _find_logo,
                                 _header, _goods_table, _draw_stamp, _vehicle_lines, _draw_qr_url,
                                 INK, FORM)

TITLES = {
    "release_to_owner": ("RELEASE RECEIPT", "Receipt No.", "REL"),
    "forfeiture": ("FORFEITURE / APPROPRIATION RECORD", "Ref. No.", "FOR"),
    "destruction": ("CERTIFICATE OF DESTRUCTION", "Ref. No.", "DES"),
    "e_auction": ("E-AUCTION SALE RECORD", "Ref. No.", "AUC"),
}

_SQL = """
SELECT ar.request_id, ar.entry_id, ar.action_type, ar.request_notes, ar.created_at AS requested_at,
       ar.supervisor_at, ar.manager_at, ar.effected_at,
       ar.amount_collected_usd AS ar_usd, ar.amount_collected_zwg AS ar_zwg,
       e.entry_number, e.entry_type, e.port_code, e.goods_description, e.declared_value, e.date_entered,
       e.importer_name, e.importer_address, e.importer_contact, e.importer_id_number,
       e.is_vehicle, e.quantity_units, e.rent_charge_per_day,
       p.port_name, w.warehouse_name,
       rih.rih_number, nos.nos_number,
       requ.full_name AS requested_by_name, sup.full_name AS supervisor_name, mgr.full_name AS manager_name,
       v.registration_number, v.chassis_number, v.engine_number, v.make, v.model, v.colour, v.year_of_manufacture,
       rl.duty_paid_usd, rl.duty_paid_zwg, rl.additional_duty_usd, rl.additional_duty_zwg,
       rl.rent_days_calculated, rl.rent_calculated, rl.rent_paid_usd, rl.rent_paid_zwg,
       rl.receipt_number AS rel_receipt, rl.y_number, rl.clearance_details, rl.finalized_at AS rl_at, rlu.full_name AS rl_by,
       fo.ministry_name, fo.request_letter_reference, fo.representative_name, fo.representative_id_number,
       fo.representative_occupation, fo.goods_or_vehicle_finalization_details,
       fo.finalized_at AS fo_at, fou.full_name AS fo_by,
       ds.port_health_officer_name, ds.port_health_approval_reference, ds.reason_for_destruction,
       ds.destruction_date, ds.destruction_place, ds.stakeholders_present,
       ds.finalized_at AS ds_at, dsu.full_name AS ds_by,
       ea.revenue_collected_usd, ea.revenue_collected_zwg, ea.buyer_details, ea.receipt_number AS ea_receipt,
       ea.finalized_at AS ea_at, eau.full_name AS ea_by
FROM action_requests ar
JOIN entries e ON e.entry_id = ar.entry_id
LEFT JOIN ports p ON p.port_code = e.port_code
LEFT JOIN warehouses w ON w.warehouse_id = e.warehouse_id
LEFT JOIN rih_details rih ON rih.entry_id = e.entry_id
LEFT JOIN nos_details nos ON nos.entry_id = e.entry_id
LEFT JOIN vehicle_details v ON v.entry_id = e.entry_id
LEFT JOIN users requ ON requ.user_id = ar.requested_by
LEFT JOIN users sup ON sup.user_id = ar.supervisor_by
LEFT JOIN users mgr ON mgr.user_id = ar.manager_by
LEFT JOIN release_to_owner_details rl ON rl.request_id = ar.request_id
LEFT JOIN users rlu ON rlu.user_id = rl.finalized_by
LEFT JOIN forfeiture_details fo ON fo.request_id = ar.request_id
LEFT JOIN users fou ON fou.user_id = fo.finalized_by
LEFT JOIN destruction_details ds ON ds.request_id = ar.request_id
LEFT JOIN users dsu ON dsu.user_id = ds.finalized_by
LEFT JOIN eauction_details ea ON ea.request_id = ar.request_id
LEFT JOIN users eau ON eau.user_id = ea.finalized_by
WHERE ar.request_id = %s
"""


def fetch_closing_data(request_id):
    return fetch_one(_SQL, (request_id,))


def effected_request_for_entry(entry_id):
    r = fetch_one("SELECT request_id FROM action_requests WHERE entry_id=%s AND effected IS TRUE "
                  "ORDER BY COALESCE(effected_at, created_at) DESC, request_id DESC LIMIT 1", (entry_id,))
    return r["request_id"] if r else None


def _money(usd, zwg):
    parts = []
    if usd not in (None, "") and float(usd):
        parts.append(f"USD {float(usd):,.2f}")
    if zwg not in (None, "") and float(zwg):
        parts.append(f"ZWG {float(zwg):,.2f}")
    return "  +  ".join(parts) if parts else "—"


def _closed_on(d):
    for k in ("effected_at", "rl_at", "fo_at", "ds_at", "ea_at"):
        if d.get(k):
            return d[k]
    return None


def _ref(d):
    code = TITLES[d["action_type"]][2]
    if d["action_type"] == "release_to_owner" and d.get("rel_receipt"):
        return _s(d["rel_receipt"])
    if d["action_type"] == "e_auction" and d.get("ea_receipt"):
        return _s(d["ea_receipt"])
    return f"{code}/{int(d['request_id']):05d}"


def _entry_no(d):
    if d["entry_type"] == "NOS":
        return "NOS No. " + (_s(d.get("nos_number")) or _s(d["entry_number"]))
    return "RIH No. " + (_s(d.get("rih_number")) or _s(d["entry_number"]))


def _goods_block(c, d, top):
    qty = _s(d.get("quantity_units"))
    if d.get("is_vehicle"):
        left = _vehicle_lines(d)
    else:
        left = [ln for ln in (d.get("goods_description") or "").split("\n") if ln][:5] or [""]
    right = [_entry_no(d).upper(), f"ENTRY NO: {_s(d['entry_number'])}",
             f"STATION: {_s(d.get('port_name')).upper()}",
             f"STORED AT: {_s(d.get('warehouse_name')).upper()}",
             f"DETAINED: {_s(d.get('date_entered'))}"]
    return _goods_table(c, top, 7, (qty.upper(), left), right, "Goods concerned")


def _authority_block(c, d, y):
    """Who requested / approved / finalised, with dates."""
    c.setFillColorRGB(*FORM)
    c.setFont("Times-Bold", 9)
    c.drawString(LM, y, "AUTHORITY AND SIGN-OFF")
    y -= 14
    rows = [("Requested by (Officer)", d.get("requested_by_name"), d.get("requested_at")),
            ("Reviewed by (Supervisor)", d.get("supervisor_name"), d.get("supervisor_at")),
            ("Approved by (Manager)", d.get("manager_name"), d.get("manager_at"))]
    fin = d.get("rl_by") or d.get("fo_by") or d.get("ds_by") or d.get("ea_by")
    rows.append(("Finalized by (Officer)", fin, _closed_on(d)))
    for lab, who, when in rows:
        _field(c, LM, y, lab + ":", _s(who), 330)
        _field(c, 340, y, "Date:", _s(when), RM)
        y -= 20
    return y


def _signatures(c, y, left, right):
    c.setFillColorRGB(*FORM)
    for x, lab in ((LM, left), (290, right)):
        _label(c, x, y, lab, 9)
        _dotted(c, x + 3, x + 170, y - 16)
        _label(c, x, y - 28, "Name / ID No.:", 8.5, "Times-Roman")
        _dotted(c, x + 65, x + 170, y - 29)
        _label(c, x, y - 44, "Date:", 8.5, "Times-Roman")
        _dotted(c, x + 28, x + 170, y - 45)


def _kv(c, y, items, label_w=170, x=LM, x2=RM):
    for lab, val in items:
        _field(c, x, y, lab, _s(val), x2)
        y -= 21
    return y


def _release(c, d, logo):
    _header(c, TITLES["release_to_owner"][0], TITLES["release_to_owner"][1], _ref(d), logo)
    y = H - 172
    _field(c, LM, y, "Released to:", _s(d.get("importer_name")), 330)
    _field(c, 340, y, "ID / Reg. No.:", _s(d.get("importer_id_number")), RM)
    _field(c, LM, y - 22, "Address:", _s(d.get("importer_address")), 330)
    _field(c, 340, y - 22, "Contact:", _s(d.get("importer_contact")), RM)
    _para(c, "The goods described below, held at the State Warehouse, have been released to the person named above "
             "after settlement of the amounts shown. Receipt of the goods is acknowledged below.", LM, y - 50, RM - LM, 9, lead=11)
    bottom = _goods_block(c, d, y - 84)
    y = bottom - 26
    c.setFillColorRGB(*FORM); c.setFont("Times-Bold", 9); c.drawString(LM, y + 10, "PAYMENTS RECEIVED")
    days = d.get("rent_days_calculated")
    rate = d.get("rent_charge_per_day")
    rent_txt = (f"{days} day(s) × USD {float(rate):,.2f} = USD {float(d.get('rent_calculated') or 0):,.2f}"
                if days is not None and rate not in (None, "") else "—")
    items = [("Duty paid:", _money(d.get("duty_paid_usd"), d.get("duty_paid_zwg"))),
             ("Additional duty:", _money(d.get("additional_duty_usd"), d.get("additional_duty_zwg"))),
             ("Rent assessed:", rent_txt),
             ("Rent paid:", _money(d.get("rent_paid_usd"), d.get("rent_paid_zwg"))),
             ("Total received:", _money(d.get("ar_usd"), d.get("ar_zwg"))),
             ("Y-number:", _s(d.get("y_number"))), ("Clearance details:", _s(d.get("clearance_details")))]
    y = _kv(c, y - 8, items)
    y = _authority_block(c, d, y - 8)
    _signatures(c, y - 12, "Signature of person receiving the goods", "Signature of releasing Officer")
    _draw_stamp(c, 516, 140, 36, {"date_entered": _closed_on(d)})


def _forfeiture(c, d, logo):
    _header(c, TITLES["forfeiture"][0], TITLES["forfeiture"][1], _ref(d), logo)
    y = H - 172
    _para(c, "In terms of the Customs and Excise Act [Chapter 23:02] the goods described below have become the "
             "property of the State and have been handed over for appropriation as recorded on this form.",
          LM, y, RM - LM, 9, lead=11)
    bottom = _goods_block(c, d, y - 44)
    y = bottom - 26
    c.setFillColorRGB(*FORM); c.setFont("Times-Bold", 9); c.drawString(LM, y + 10, "HANDOVER DETAILS")
    items = [("Receiving Ministry / Institution:", d.get("ministry_name")),
             ("Request letter reference:", d.get("request_letter_reference")),
             ("Representative's name:", d.get("representative_name")),
             ("Representative's ID No.:", d.get("representative_id_number")),
             ("Occupation / Designation:", d.get("representative_occupation")),
             ("Details of goods / vehicle handed over:", d.get("goods_or_vehicle_finalization_details"))]
    y = _kv(c, y - 8, items)
    y = _authority_block(c, d, y - 8)
    _signatures(c, y - 12, "Signature of receiving representative", "Signature of handing-over Officer")
    _draw_stamp(c, 516, 140, 36, {"date_entered": _closed_on(d)})


def _destruction(c, d, logo):
    _header(c, TITLES["destruction"][0], TITLES["destruction"][1], _ref(d), logo)
    y = H - 172
    _para(c, "This is to certify that the goods described below were destroyed on the date and at the place stated, "
             "under the authority recorded on this certificate and in the presence of the persons named.",
          LM, y, RM - LM, 9, lead=11)
    bottom = _goods_block(c, d, y - 44)
    y = bottom - 26
    c.setFillColorRGB(*FORM); c.setFont("Times-Bold", 9); c.drawString(LM, y + 10, "DESTRUCTION DETAILS")
    items = [("Date of destruction:", d.get("destruction_date")), ("Place of destruction:", d.get("destruction_place")),
             ("Reason for destruction:", d.get("reason_for_destruction")),
             ("Port Health Officer:", d.get("port_health_officer_name")),
             ("Port Health approval ref.:", d.get("port_health_approval_reference")),
             ("Present at destruction:", d.get("stakeholders_present"))]
    y = _kv(c, y - 8, items)
    y = _authority_block(c, d, y - 8)
    _signatures(c, y - 12, "Signature of witnessing Officer", "Signature of Port Health Officer")
    _draw_stamp(c, 516, 140, 36, {"date_entered": d.get("destruction_date") or _closed_on(d)})


def _auction(c, d, logo):
    _header(c, TITLES["e_auction"][0], TITLES["e_auction"][1], _ref(d), logo)
    y = H - 172
    _para(c, "The goods described below were sold through ZIMRA's e-auction system after the statutory notice period "
             "(section 39(3) of the Customs and Excise Act [Chapter 23:02]). The proceeds are recorded below.",
          LM, y, RM - LM, 9, lead=11)
    bottom = _goods_block(c, d, y - 44)
    y = bottom - 26
    c.setFillColorRGB(*FORM); c.setFont("Times-Bold", 9); c.drawString(LM, y + 10, "SALE DETAILS")
    items = [("Revenue collected:", _money(d.get("revenue_collected_usd") or d.get("ar_usd"),
                                         d.get("revenue_collected_zwg") or d.get("ar_zwg"))),
             ("Receipt No.:", d.get("ea_receipt")), ("Buyer details:", d.get("buyer_details")),
             ("Date of sale:", _closed_on(d))]
    y = _kv(c, y - 8, items)
    y = _authority_block(c, d, y - 8)
    _signatures(c, y - 12, "Signature of Officer", "Signature of Station Manager")
    _draw_stamp(c, 516, 140, 36, {"date_entered": _closed_on(d)})


def build_closing_pdf(d):
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    title = TITLES[d["action_type"]][0].title()
    c.setTitle(f"{title} {_ref(d)}")
    c.setAuthor("ZIMRA")
    logo = _find_logo()
    _draw_qr_url(c, f"{ed._base_url()}/Verify_Document?t=CLOSE&no={int(d['request_id'])}")
    {"release_to_owner": _release, "forfeiture": _forfeiture,
     "destruction": _destruction, "e_auction": _auction}[d["action_type"]](c, d, logo)
    c.setFont("Times-Italic", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(W / 2, 12, f"System-generated {datetime.now():%d/%m/%Y %H:%M} · {_entry_no(d)} · Entry {d.get('entry_number', '')}")
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------- Streamlit widgets ----------
def render_closing_document(entry_id, key):
    """Toggle 'View closing document' for an entry whose action has been finalized."""
    import base64
    import streamlit as st
    import streamlit.components.v1 as components

    rid = effected_request_for_entry(entry_id) if entry_id else None
    if not rid:
        st.caption("No finalized action recorded for this entry yet.")
        return
    d = fetch_closing_data(rid)
    if not d or d["action_type"] not in TITLES:
        return
    title = TITLES[d["action_type"]][0].title()
    if not st.toggle(f"📄 View / print {title} — {d['entry_number']}", key=f"cd_{key}_{rid}"):
        return
    pdf = build_closing_pdf(d)
    b64 = base64.b64encode(ed.pdf_to_png(pdf)).decode()
    components.html(
        f"""<style>@media print{{.np{{display:none}} @page{{size:A4;margin:0}} body{{margin:0}}}}</style>
<div class='np' style='text-align:right;margin-bottom:6px'>
<button onclick='window.print()' style='padding:6px 16px;background:#1F4E3D;color:#fff;border:0;border-radius:4px;cursor:pointer'>🖨 Print</button></div>
<img src='data:image/png;base64,{b64}' style='width:100%;border:1px solid #ccc'>""",
        height=1050, scrolling=True)
    st.download_button(f"⬇ Download {title} (PDF)", data=pdf,
                       file_name=f"{title.replace(' ', '_').replace('/', '-')}_{d['entry_number']}.pdf",
                       mime="application/pdf", key=f"cddl_{key}_{rid}")


def closing_document_picker(rows, key, label="🧾 Open closing document (receipt / record / certificate) for an entry"):
    """Under a table of finalized entries: pick one, then view / print / download its closing document."""
    import streamlit as st
    try:
        rows = [dict(r) for r in (rows or [])]
    except Exception:
        return
    options = {}
    for r in rows:
        if r.get("entry_number"):
            tag = f" — {str(r['action_type']).replace('_', ' ').title()}" if r.get("action_type") else ""
            options[f"{r['entry_number']}{tag}"] = r
    if not options:
        return
    pick = st.selectbox(label, list(options.keys()), index=None, placeholder="Select an entry…", key=f"cpick_{key}")
    if pick:
        eid = ed._resolve_entry_id(options[pick])
        if eid:
            render_closing_document(eid, key=f"cp_{key}_{eid}")

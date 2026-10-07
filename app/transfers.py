"""
Movement of goods between warehouses (and vehicles between pounds).

  Officer requests  ->  Supervisor reviews  ->  Manager approves  ->  the entry is MOVED automatically.

Rules
  * same station only; a vehicle/pound moves to another pound, other goods to another warehouse
  * the destination must not be full
  * transfers are paused for a warehouse while a stocktake is open there (the count would be corrupted)
  * the move itself is one atomic statement (request approved and entry re-assigned together)
Movement history = the entry's capture + every approved transfer.
"""
from datetime import datetime
from io import BytesIO

from app.db import fetch_all, fetch_one

FINAL_STATUSES = ("released", "sold", "destroyed", "appropriated")


# ------------------------------------------------------------------ helpers
def is_pound(wh):
    return "pound" in f"{wh.get('warehouse_type') or ''} {wh.get('warehouse_name') or ''}".lower()


def occupancy(warehouse_id):
    try:
        from app.warehouses import goods_in_warehouse
        return len(goods_in_warehouse(warehouse_id) or [])
    except Exception:
        r = fetch_one("SELECT COUNT(*) AS n FROM entries WHERE warehouse_id=%s AND status NOT IN %s",
                      (warehouse_id, FINAL_STATUSES))
        return r["n"] if r else 0


def _stocktake_open(*warehouse_ids):
    try:
        r = fetch_one("SELECT w.warehouse_name FROM stocktakes s JOIN warehouses w ON w.warehouse_id = s.warehouse_id "
                      "WHERE s.status='open' AND s.warehouse_id = ANY(%s) LIMIT 1", (list(warehouse_ids),))
        return r["warehouse_name"] if r else None
    except Exception:
        return None


def eligible_entries(port_code):
    """Entries currently held at this station and assigned to a warehouse/pound, without an open request."""
    return fetch_all(
        """SELECT e.entry_id, e.entry_number, e.entry_type, e.goods_description, e.is_vehicle,
                  w.warehouse_id, w.warehouse_name, w.warehouse_type
           FROM entries e JOIN warehouses w ON w.warehouse_id = e.warehouse_id
           WHERE e.port_code=%s AND e.status NOT IN %s
             AND NOT EXISTS (SELECT 1 FROM transfer_requests t WHERE t.entry_id = e.entry_id AND t.status='pending')
           ORDER BY e.entry_number""", (port_code, FINAL_STATUSES))


def destination_options(entry_id):
    """Other warehouses/pounds at the same station, of the same kind, that are not full."""
    src = fetch_one("""SELECT e.port_code, w.warehouse_id, w.warehouse_name, w.warehouse_type
                       FROM entries e JOIN warehouses w ON w.warehouse_id = e.warehouse_id WHERE e.entry_id=%s""", (entry_id,))
    if not src:
        return []
    out = []
    for w in fetch_all("SELECT * FROM warehouses WHERE port_code=%s AND warehouse_id <> %s ORDER BY warehouse_name",
                       (src["port_code"], src["warehouse_id"])):
        if is_pound(w) != is_pound(src) or w.get("is_full"):
            continue
        cap = w.get("capacity")
        occ = occupancy(w["warehouse_id"])
        if cap and occ >= cap:
            continue
        w = dict(w); w["occupancy"] = occ
        out.append(w)
    return out


def _notify(user_ids, message, entry_id=None):
    for uid in {u for u in user_ids if u}:
        try:
            fetch_one("INSERT INTO notifications (recipient_user_id, notif_type, entry_id, message, is_read) "
                      "VALUES (%s,'transfer',%s,%s,FALSE) RETURNING notification_id", (uid, entry_id, message))
        except Exception:
            pass


def _role_users(role, port=None):
    q = ("SELECT u.user_id FROM users u JOIN roles r ON r.role_id=u.role_id "
         "WHERE r.role_name=%s AND u.is_active")
    a = [role]
    if port:
        q += " AND u.port_code=%s"; a.append(port)
    return [r["user_id"] for r in fetch_all(q, tuple(a))]


# ------------------------------------------------------------------ workflow
def request_transfer(entry_id, to_warehouse_id, reason, user):
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Please give a reason for the transfer.")
    e = fetch_one("""SELECT e.entry_id, e.entry_number, e.port_code, e.warehouse_id, e.status
                     FROM entries e WHERE e.entry_id=%s""", (entry_id,))
    if not e or not e["warehouse_id"]:
        raise ValueError("This entry is not assigned to a warehouse.")
    if e["status"] in FINAL_STATUSES:
        raise ValueError("This entry has already left the warehouse.")
    if e["port_code"] != user["port_code"]:
        raise ValueError("You can only transfer goods held at your own station.")
    if to_warehouse_id not in [w["warehouse_id"] for w in destination_options(entry_id)]:
        raise ValueError("That destination is not available (full, wrong type, or a different station).")
    busy = _stocktake_open(e["warehouse_id"], to_warehouse_id)
    if busy:
        raise ValueError(f"A stocktake is in progress at {busy}. Transfers are paused until it is closed.")
    try:
        tid = fetch_one(
            """INSERT INTO transfer_requests (entry_id, from_warehouse_id, to_warehouse_id, reason, requested_by)
               VALUES (%s,%s,%s,%s,%s) RETURNING transfer_id""",
            (entry_id, e["warehouse_id"], to_warehouse_id, reason, user["user_id"]))["transfer_id"]
    except Exception:
        raise ValueError("This entry already has a transfer request waiting for approval.")
    _notify(_role_users("Supervisor", e["port_code"]),
            f"Transfer request for {e['entry_number']} awaits your review.", entry_id)
    return tid


_LIST_SQL = """
SELECT t.*, e.entry_number, e.entry_type, e.goods_description, e.is_vehicle, e.port_code,
       fw.warehouse_name AS from_name, tw.warehouse_name AS to_name,
       ru.full_name AS requested_by_name, su.full_name AS supervisor_name, mu.full_name AS manager_name
FROM transfer_requests t
JOIN entries e ON e.entry_id = t.entry_id
JOIN warehouses fw ON fw.warehouse_id = t.from_warehouse_id
JOIN warehouses tw ON tw.warehouse_id = t.to_warehouse_id
LEFT JOIN users ru ON ru.user_id = t.requested_by
LEFT JOIN users su ON su.user_id = t.supervisor_by
LEFT JOIN users mu ON mu.user_id = t.manager_by
"""


def pending_for_supervisor(port_code):
    return fetch_all(_LIST_SQL + " WHERE t.status='pending' AND t.supervisor_status='pending' AND e.port_code=%s ORDER BY t.transfer_id",
                     (port_code,))


def pending_for_manager():
    return fetch_all(_LIST_SQL + " WHERE t.status='pending' AND t.supervisor_status='approved' AND t.manager_status='pending' ORDER BY t.transfer_id")


def my_requests(user_id, limit=30):
    return fetch_all(_LIST_SQL + " WHERE t.requested_by=%s ORDER BY t.transfer_id DESC LIMIT %s", (user_id, limit))


def supervisor_decide(transfer_id, user, approve, notes=""):
    if not approve and not (notes or "").strip():
        raise ValueError("Please give a reason for rejecting.")
    r = fetch_one(
        """UPDATE transfer_requests t SET supervisor_status=%s, supervisor_by=%s, supervisor_at=NOW(), supervisor_notes=%s,
                  status = CASE WHEN %s THEN 'pending' ELSE 'rejected' END
           FROM entries e
           WHERE t.transfer_id=%s AND t.status='pending' AND t.supervisor_status='pending'
             AND e.entry_id = t.entry_id AND e.port_code=%s
           RETURNING t.transfer_id, t.entry_id, t.requested_by""",
        ("approved" if approve else "rejected", user["user_id"], notes or None, approve, transfer_id, user["port_code"]))
    if not r:
        raise ValueError("This request is no longer waiting for your review.")
    if approve:
        _notify(_role_users("Manager"), "A transfer request awaits your approval.", r["entry_id"])
    else:
        _notify([r["requested_by"]], f"Your transfer request was rejected by the Supervisor: {notes}", r["entry_id"])
    return r


def manager_decide(transfer_id, user, approve, notes=""):
    """Approve = the goods are moved in the same atomic statement."""
    if not approve:
        if not (notes or "").strip():
            raise ValueError("Please give a reason for rejecting.")
        r = fetch_one(
            """UPDATE transfer_requests SET manager_status='rejected', manager_by=%s, manager_at=NOW(), manager_notes=%s, status='rejected'
               WHERE transfer_id=%s AND status='pending' AND supervisor_status='approved' AND manager_status='pending'
               RETURNING transfer_id, entry_id, requested_by""", (user["user_id"], notes, transfer_id))
        if not r:
            raise ValueError("This request is no longer waiting for your approval.")
        _notify([r["requested_by"]], f"Your transfer request was rejected by the Manager: {notes}", r["entry_id"])
        return r
    t = fetch_one("SELECT entry_id, from_warehouse_id, to_warehouse_id, status, supervisor_status, manager_status "
                  "FROM transfer_requests WHERE transfer_id=%s", (transfer_id,))
    if not t:
        raise ValueError("Request not found.")
    if t["status"] != "pending" or t["manager_status"] != "pending":
        raise ValueError("This request has already been decided.")
    if t["supervisor_status"] != "approved":
        raise ValueError("The Supervisor has not approved this request yet.")
    busy = _stocktake_open(t["from_warehouse_id"], t["to_warehouse_id"])
    if busy:
        raise ValueError(f"A stocktake is in progress at {busy}. Approve after it is closed.")
    dest = fetch_one("SELECT is_full, capacity FROM warehouses WHERE warehouse_id=%s", (t["to_warehouse_id"],))
    if dest and (dest["is_full"] or (dest["capacity"] and occupancy(t["to_warehouse_id"]) >= dest["capacity"])):
        raise ValueError("The destination is now full. Reject this request or choose another destination.")
    r = fetch_one(
        """WITH t AS (
               UPDATE transfer_requests SET manager_status='approved', manager_by=%s, manager_at=NOW(), manager_notes=%s,
                      status='approved', moved_at=NOW()
               WHERE transfer_id=%s AND status='pending' AND supervisor_status='approved' AND manager_status='pending'
                 AND EXISTS (SELECT 1 FROM entries x WHERE x.entry_id = transfer_requests.entry_id
                             AND x.warehouse_id = transfer_requests.from_warehouse_id)
               RETURNING entry_id, to_warehouse_id, requested_by
           ), e AS (
               UPDATE entries SET warehouse_id = t.to_warehouse_id, updated_at = NOW()
               FROM t WHERE entries.entry_id = t.entry_id RETURNING entries.entry_id
           )
           SELECT t.entry_id, t.requested_by, (SELECT COUNT(*) FROM e) AS moved FROM t""",
        (user["user_id"], notes or None, transfer_id))
    if not r or not r["moved"]:
        raise ValueError("The goods are no longer in the original warehouse, or the request was already decided. Nothing was moved.")
    _notify([r["requested_by"]], "Your transfer request was approved and the goods have been moved.", r["entry_id"])
    return r


# ------------------------------------------------------------------ history
def entry_history(entry_id):
    """Chronological list: capture, then each approved transfer."""
    e = fetch_one("""SELECT e.entry_number, e.date_entered, w.warehouse_name AS current_name,
                            cu.full_name AS captured_by_name
                     FROM entries e LEFT JOIN warehouses w ON w.warehouse_id = e.warehouse_id
                     LEFT JOIN users cu ON cu.user_id = COALESCE(e.captured_by, e.officer_id)
                     WHERE e.entry_id=%s""", (entry_id,))
    if not e:
        return []
    moves = fetch_all(_LIST_SQL + " WHERE t.entry_id=%s AND t.status='approved' ORDER BY t.moved_at, t.transfer_id", (entry_id,))
    first = moves[0]["from_name"] if moves else e["current_name"]
    out = [{"when": e["date_entered"], "event": "Captured and stored", "from": None, "to": first,
            "by": e["captured_by_name"], "reason": None}]
    for m in moves:
        out.append({"when": m["moved_at"], "event": "Transferred", "from": m["from_name"], "to": m["to_name"],
                    "by": f"requested {m['requested_by_name'] or '—'}; approved {m['manager_name'] or '—'}", "reason": m["reason"],
                    "transfer_id": m["transfer_id"]})
    return out


def recent_movements(port_code=None, limit=100):
    q = _LIST_SQL + " WHERE t.status='approved'"
    a = []
    if port_code:
        q += " AND e.port_code=%s"; a.append(port_code)
    q += " ORDER BY t.moved_at DESC LIMIT %s"; a.append(limit)
    return fetch_all(q, tuple(a))


# ------------------------------------------------------------------ transfer note (PDF)
def build_transfer_note(transfer_id):
    from reportlab.pdfgen import canvas
    from app import entry_documents as ed
    from app.entry_documents import (W, H, LM, RM, _s, _field, _para, _find_logo, _header, _draw_stamp, _draw_qr_url, _label, _dotted)
    d = fetch_one(_LIST_SQL + " WHERE t.transfer_id=%s", (transfer_id,))
    d["port_name"] = (fetch_one("SELECT port_name FROM ports WHERE port_code=%s", (d["port_code"],)) or {}).get("port_name")
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    ref = f"TRF/{int(d['transfer_id']):05d}"
    c.setTitle(f"Transfer Note {ref}"); c.setAuthor("ZIMRA")
    _header(c, "WAREHOUSE TRANSFER NOTE", "Ref. No.", ref, _find_logo())
    _draw_qr_url(c, f"{ed._base_url()}/Verify_Document?t=TRANSFER&no={int(d['transfer_id'])}")
    y = H - 176
    _para(c, "The goods described below were moved between storage locations after approval by the Manager, "
             "as recorded on this note.", LM, y, RM - LM, 10, lead=13)
    y -= 44
    kind = "Vehicle" if d["is_vehicle"] else "Goods"
    rows = [("Entry:", f"{d['entry_type']} — {d['entry_number']}"), (f"{kind}:", (d["goods_description"] or "")[:90]),
            ("Station:", d.get("port_name")), ("Moved from:", d["from_name"]), ("Moved to:", d["to_name"]),
            ("Reason:", d["reason"]), ("Date moved:", d["moved_at"])]
    for lab, val in rows:
        _field(c, LM, y, lab, _s(val), RM); y -= 22
    y -= 10
    c.setFont("Times-Bold", 9); c.setFillColorRGB(0, 0, 0); c.drawString(LM, y, "AUTHORITY AND SIGN-OFF"); y -= 16
    for lab, who, when in (("Requested by (Officer):", d["requested_by_name"], d["requested_at"]),
                           ("Reviewed by (Supervisor):", d["supervisor_name"], d["supervisor_at"]),
                           ("Approved by (Manager):", d["manager_name"], d["manager_at"])):
        _field(c, LM, y, lab, _s(who), 330); _field(c, 340, y, "Date:", _s(when), RM); y -= 22
    y -= 24
    for x, lab in ((LM, "Signature of releasing Officer"), (290, "Signature of receiving Officer")):
        _label(c, x, y, lab, 9); _dotted(c, x + 3, x + 170, y - 16)
        _label(c, x, y - 30, "Date:", 8.5, "Times-Roman"); _dotted(c, x + 28, x + 170, y - 31)
    _draw_stamp(c, 516, 170, 36, {"date_entered": d["moved_at"]})
    c.setFont("Times-Italic", 7); c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(W / 2, 12, f"System-generated {datetime.now():%d/%m/%Y %H:%M} · Entry {d['entry_number']}")
    c.showPage(); c.save()
    return buf.getvalue()


# ------------------------------------------------------------------ Streamlit UI
def _status_text(t):
    if t["status"] == "approved":
        return f"✅ Moved on {t['moved_at']:%d %b %Y}"
    if t["status"] == "rejected":
        who = "Supervisor" if t["supervisor_status"] == "rejected" else "Manager"
        note = t["supervisor_notes"] if t["supervisor_status"] == "rejected" else t["manager_notes"]
        return f"❌ Rejected by {who}" + (f": {note}" if note else "")
    return "⏳ Awaiting " + ("Supervisor review" if t["supervisor_status"] == "pending" else "Manager approval")


def _note_toggle(st, t, key):
    if t["status"] == "approved" and st.toggle("Prepare transfer note", key=f"tn_{key}_{t['transfer_id']}"):
        st.download_button("⬇ Download Transfer Note (PDF)", data=build_transfer_note(t["transfer_id"]),
                           file_name=f"Transfer_Note_{t['transfer_id']}.pdf", mime="application/pdf",
                           key=f"tndl_{key}_{t['transfer_id']}")


def _card(st, t):
    kind = "🚗" if t["is_vehicle"] else "📦"
    st.write(f"{kind} **{t['entry_number']}** ({t['entry_type']}) — {t['from_name']} ➜ **{t['to_name']}**")
    st.caption(f"{(t['goods_description'] or '')[:90]} · Requested by {t['requested_by_name'] or '—'} on {t['requested_at']:%d %b %Y}")
    st.caption(f"Reason: {t['reason']}")


def transfers_tab(user):
    import pandas as pd
    import streamlit as st

    role = user["role_name"]
    st.subheader("Transfers — Moving Goods Between Warehouses and Pounds")
    if role in ("Officer", "Supervisor") and not user.get("port_code"):
        st.warning("Your profile has no station assigned, so no transfers can be shown. "
                   "Ask the Admin to assign your station (Admin → Users).")
        return
    msg = st.session_state.pop("trf_msg", None)
    if msg:
        st.success(msg)

    # ---- Officer: request
    if role == "Officer":
        st.markdown("**Request a transfer**")
        st.caption("The request goes to your Supervisor, then the Manager. The goods are moved only after the Manager approves.")
        ents = eligible_entries(user["port_code"])
        if not ents:
            st.info("No goods are available to transfer (all have a pending request or none are held).")
        else:
            labels = {f"{e['entry_number']} ({e['entry_type']}) — {(e['goods_description'] or '')[:40]} — now in {e['warehouse_name']}": e for e in ents}
            pick = st.selectbox("Entry to move", list(labels.keys()), index=None, placeholder="Select an entry…", key="trf_entry")
            if pick:
                e = labels[pick]
                opts = destination_options(e["entry_id"])
                if not opts:
                    st.warning("No other " + ("pound" if is_pound(e) else "warehouse") + " at this station has space.")
                else:
                    dest = {f"{w['warehouse_name']} ({w['occupancy']}/{w['capacity'] or '—'})": w for w in opts}
                    with st.form("trf_form", clear_on_submit=True):
                        to = st.selectbox("Move to", list(dest.keys()))
                        reason = st.text_area("Reason for the transfer")
                        if st.form_submit_button("Submit transfer request", type="primary"):
                            try:
                                request_transfer(e["entry_id"], dest[to]["warehouse_id"], reason, user)
                                st.session_state.trf_msg = "Transfer request sent to your Supervisor."
                                st.rerun()
                            except ValueError as ex:
                                st.error(str(ex))
        st.markdown("**My transfer requests**")
        mine = my_requests(user["user_id"])
        if not mine:
            st.caption("You have not requested any transfers.")
        for t in mine:
            with st.container(border=True):
                _card(st, t)
                st.write(_status_text(t))
                _note_toggle(st, t, "mine")

    # ---- Supervisor / Manager: decide
    if role in ("Supervisor", "Manager"):
        rows = pending_for_supervisor(user["port_code"]) if role == "Supervisor" else pending_for_manager()
        st.markdown("**Waiting for your " + ("review" if role == "Supervisor" else "approval") + "**")
        if not rows:
            st.info("Nothing waiting.")
        for t in rows:
            with st.container(border=True):
                _card(st, t)
                if role == "Manager":
                    st.caption(f"Supervisor {t['supervisor_name'] or '—'} approved on {t['supervisor_at']:%d %b %Y}"
                               + (f": {t['supervisor_notes']}" if t["supervisor_notes"] else ""))
                notes = st.text_input("Notes (required to reject)", key=f"trf_n_{t['transfer_id']}")
                c1, c2 = st.columns(2)
                act = None
                if c1.button("✅ Approve" + (" and move the goods" if role == "Manager" else ""), key=f"trf_a_{t['transfer_id']}", type="primary"):
                    act = True
                if c2.button("❌ Reject", key=f"trf_r_{t['transfer_id']}"):
                    act = False
                if act is not None:
                    try:
                        (supervisor_decide if role == "Supervisor" else manager_decide)(t["transfer_id"], user, act, notes)
                        st.session_state.trf_msg = ("Approved and forwarded to the Manager." if role == "Supervisor" and act else
                                                    "Approved — the goods have been moved." if act else "Request rejected.")
                        st.rerun()
                    except ValueError as ex:
                        st.error(str(ex))

    # ---- everyone: history
    st.divider()
    st.markdown("**Movement history**")
    port = user["port_code"] if role in ("Officer", "Supervisor") else None
    recent = recent_movements(port, 50)
    if recent:
        st.dataframe(pd.DataFrame([{
            "Moved": f"{m['moved_at']:%d %b %Y %H:%M}", "Entry": m["entry_number"], "Type": m["entry_type"],
            "From": m["from_name"], "To": m["to_name"], "Requested by": m["requested_by_name"],
            "Approved by": m["manager_name"], "Reason": m["reason"]} for m in recent]),
            hide_index=True, use_container_width=True)
        labels = {f"{m['entry_number']} ({m['entry_type']})": m["entry_id"] for m in recent}
        pick = st.selectbox("Full history of one entry", list(labels.keys()), index=None, placeholder="Select an entry…", key="trf_hist")
        if pick:
            st.dataframe(pd.DataFrame([{
                "When": f"{h['when']:%d %b %Y %H:%M}" if h["when"] else "—", "Event": h["event"], "From": h["from"] or "—",
                "To": h["to"], "By": h["by"], "Reason": h["reason"] or ""} for h in entry_history(labels[pick])]),
                hide_index=True, use_container_width=True)
        with st.expander("Print transfer notes (latest 10)"):
            for m in recent[:10]:
                st.write(f"**{m['entry_number']}** — {m['from_name']} ➜ {m['to_name']} ({m['moved_at']:%d %b %Y})")
                _note_toggle(st, m, "hist")
    else:
        st.caption("No goods have been moved yet.")
"""
Notifications tab: automated system updates (acquittal-style events,
flags, approvals) plus a chat-style Messages feed for human-composed
communications — announcements, updates, general ZIMRA communication.
"""
import streamlit as st

from app.notifications import get_notifications_for, mark_read
from app.messages import send_message, get_messages_for
from app.db import fetch_all
from app.theme import render_sidebar, inject_global_css

st.set_page_config(page_title="Notifications — WMS-Trak", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("Notifications")

tab_system, tab_messages = st.tabs(["System Notifications", "Messages"])

# ---------------- System Notifications ----------------
with tab_system:
    show_unread_only = st.checkbox("Show unread only", value=False)
    rows = get_notifications_for(
        user["user_id"], user["role_name"], user["port_code"], unread_only=show_unread_only
    )
    if not rows:
        st.info("No system notifications.")
    else:
        for n in rows:
            icon = "🔵" if not n["is_read"] else "⚪"
            with st.container(border=True):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"{icon} **{n['notif_type'].replace('_', ' ').title()}**")
                    st.write(n["message"])
                    st.caption(f"{n['created_at']}" + (f" · Entry #{n['entry_id']}" if n["entry_id"] else ""))
                with col2:
                    if not n["is_read"]:
                        if st.button("Mark read", key=f"read_{n['notification_id']}"):
                            mark_read(n["notification_id"])
                            st.rerun()

# ---------------- Messages (chat-style) ----------------
with tab_messages:
    with st.expander("Compose a message"):
        scope = st.selectbox("Send to", ["ZIMRA-wide announcement", "A specific role", "A specific person"], key="msg_scope")
        recipient_role = None
        recipient_port = None
        recipient_user_id = None

        if scope == "A specific role":
            recipient_role = st.selectbox("Role", ["Agent", "Officer", "Supervisor", "Manager"], key="msg_role")
            scope_to_port = st.checkbox("Limit to my port only", value=False, key="msg_scope_port")
            if scope_to_port:
                recipient_port = user["port_code"]
        elif scope == "A specific person":
            people = fetch_all("SELECT user_id, full_name, username FROM users WHERE is_active = TRUE ORDER BY full_name")
            person_choices = {f"{p['full_name']} ({p['username']})": p["user_id"] for p in people}
            chosen_person = st.selectbox("Person", list(person_choices.keys()), key="msg_person")
            recipient_user_id = person_choices.get(chosen_person)

        with st.form("compose_message"):
            subject = st.text_input("Subject (optional)")
            body = st.text_area("Message")
            send = st.form_submit_button("Send", type="primary")

        if send:
            if not body.strip():
                st.error("Message cannot be empty.")
            else:
                scope_map = {
                    "ZIMRA-wide announcement": "all",
                    "A specific role": "role",
                    "A specific person": "user",
                }
                send_message(
                    sender_id=user["user_id"],
                    body=body,
                    subject=subject or None,
                    recipient_scope=scope_map[scope],
                    recipient_user_id=recipient_user_id,
                    recipient_role=recipient_role,
                    recipient_port=recipient_port,
                )
                st.success("Message sent.")
                st.rerun()

    st.divider()
    msgs = get_messages_for(user["user_id"], user["role_name"], user["port_code"])
    if not msgs:
        st.info("No messages yet.")
    else:
        for m in msgs:
            with st.container(border=True):
                st.markdown(f"**{m['sender_name']}** ({m['sender_role']}) · {m['created_at']}")
                if m["subject"]:
                    st.markdown(f"*{m['subject']}*")
                st.write(m["body"])
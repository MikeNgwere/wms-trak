"""
Forces a user to choose a new password at first sign-in (or after an admin reset).

Call enforce(user) at the very top of render_sidebar(); every page that shows the
sidebar then stays locked until the password has been changed.
"""
import bcrypt
import streamlit as st

from app.db import fetch_one, execute
from app.auth import is_strong_password, password_requirements_text, delete_session

PILOT_DEFAULT = "Zimra2026#"


def needs_change(user_id) -> bool:
    key = f"pw_ok_{user_id}"
    if st.session_state.get(key):
        return False
    try:
        row = fetch_one("SELECT must_change_password FROM users WHERE user_id = %s", (user_id,))
    except Exception:
        return False  # column not created yet: never lock everyone out
    if row and row["must_change_password"]:
        return True
    st.session_state[key] = True
    return False


def enforce(user) -> None:
    """Show the change-password screen and stop the page if a change is required."""
    if not user or not needs_change(user["user_id"]):
        return
    st.markdown("## Choose a new password")
    st.info("For your security you must replace your temporary password before you continue.")
    st.caption(password_requirements_text())
    with st.form("force_pw_form"):
        new_pw = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        go = st.form_submit_button("Save new password", type="primary")
    if go:
        if new_pw != confirm:
            st.error("The two passwords do not match.")
        elif new_pw == PILOT_DEFAULT:
            st.error("Please choose a password different from the temporary one.")
        elif not is_strong_password(new_pw):
            st.error(password_requirements_text())
        else:
            hashed = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            execute("UPDATE users SET password_hash = %s, must_change_password = FALSE WHERE user_id = %s",
                    (hashed, user["user_id"]))
            st.session_state[f"pw_ok_{user['user_id']}"] = True
            st.success("Password changed. Thank you.")
            st.rerun()
    if st.button("Sign out"):
        try:
            delete_session(st.query_params.get("token"))
        except Exception:
            pass
        st.query_params.clear()
        st.session_state.user = None
        st.session_state.auth_view = None
        st.rerun()
    st.stop()
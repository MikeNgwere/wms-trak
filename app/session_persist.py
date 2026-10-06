"""
Keeps a signed-in user signed in across page refreshes and page changes.

The session token lives in the URL (?token=...). Streamlit drops query
parameters when you move between pages, so on every page run we:
  1. restore the user from the URL token if the browser session is empty
     (this is what happens after a refresh), and
  2. put the token back in the URL if a page change removed it.
Called from inject_global_css(), which every page already calls first.
"""
import streamlit as st

from app.auth import get_user_by_session


def persist_session():
    url_token = st.query_params.get("token")
    user = st.session_state.get("user")

    if user is None:
        if url_token:
            restored = get_user_by_session(url_token)
            if restored:
                st.session_state.user = restored
                st.session_state.session_token = url_token
        else:
            # signed out: forget any remembered token
            st.session_state.pop("session_token", None)
        return

    token = st.session_state.get("session_token") or url_token
    if token:
        st.session_state.session_token = token
        if url_token != token:
            st.query_params["token"] = token

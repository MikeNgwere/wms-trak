"""
Shared ZIMRA-style theme: sidebar CSS, logo, and account dropdown
(profile info, phone number, logout). Every page calls render_sidebar()
at the top so the sidebar looks and behaves identically everywhere.
"""
import streamlit as st

from app.db import execute

ZIMRA_GREEN = "#4CAF50"
ZIMRA_GREEN_DARK = "#3d8b40"


def inject_global_css():
    st.markdown(
        f"""
        <style>
        /* Sidebar base */
        section[data-testid="stSidebar"] {{
            background-color: #FAFCFA;
            border-right: 1px solid #e5e5e5;
        }}
        /* Nav links */
        section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {{
            border-radius: 8px;
            margin: 2px 8px;
            font-weight: 500;
        }}
        section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover {{
            background-color: #E8F5E9;
        }}
        section[data-testid="stSidebar"] a[aria-current="page"] {{
            background-color: {ZIMRA_GREEN} !important;
            color: white !important;
        }}
        section[data-testid="stSidebar"] a[aria-current="page"] span {{
            color: white !important;
        }}
        /* Primary buttons everywhere */
        button[kind="primary"], div[data-testid="stFormSubmitButton"] button {{
            background-color: {ZIMRA_GREEN} !important;
            color: white !important;
            border: none !important;
        }}
        button[kind="primary"]:hover, div[data-testid="stFormSubmitButton"] button:hover {{
            background-color: {ZIMRA_GREEN_DARK} !important;
        }}
        /* Account card at bottom of sidebar */
        .zimra-account-card {{
            border-top: 1px solid #e5e5e5;
            margin-top: 1rem;
            padding-top: 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(user: dict):
    """Logo + Account dropdown (profile, phone number, logout). Call on every page."""
    inject_global_css()

    with st.sidebar:
        st.image("app/assets/zimra_logo.png", width=140)
        st.markdown("<div class='zimra-account-card'></div>", unsafe_allow_html=True)

        with st.expander(f"👤 {user['full_name']}", expanded=False):
            st.write(f"**Username:** {user['username']}")
            st.write(f"**Role:** {user['role_name']}")
            st.write(f"**Port:** {user['port_code'] or 'All ports'}")

            new_phone = st.text_input(
                "Phone number", value=user.get("phone_number") or "", key="phone_input"
            )
            if st.button("Save phone number", key="save_phone"):
                execute(
                    "UPDATE users SET phone_number = %s WHERE user_id = %s",
                    (new_phone, user["user_id"]),
                )
                st.session_state.user["phone_number"] = new_phone
                st.success("Phone number updated.")

            st.divider()
            if st.button("Log out", key="logout_btn", use_container_width=True):
                st.session_state.user = None
                st.rerun()
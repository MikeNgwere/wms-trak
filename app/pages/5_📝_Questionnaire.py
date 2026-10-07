"""
Pilot-test Questionnaire: 15 Likert-scale (1-5) items grouped under 3 research questions.

Two ways in:
  * Guest (no login): introduction -> full name + ZIMRA email -> questionnaire. One response
    per email; a repeat attempt is refused before any questions are shown.
  * Logged-in user: unchanged. One response per account; saving again updates it.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import streamlit as st

from app.theme import render_sidebar, inject_global_css
from app.questionnaire import QUESTIONS, submit_response, response_count, get_response_for_user
from app.guest_questionnaire import (ALLOWED_DOMAINS, clean_email, email_problem,
                                     email_already_responded, submit_guest_response,
                                     guest_response_for_user)

user = st.session_state.get("user")
st.set_page_config(page_title="Questionnaire — Warehouse Management System",
                   layout="wide" if user else "centered")
inject_global_css()

SCALE = "**1 = Strongly Disagree · 2 = Disagree · 3 = Neutral · 4 = Agree · 5 = Strongly Agree**"


def _questions_block(defaults=None):
    answers = {}
    for rq_title, qset in QUESTIONS.items():
        st.markdown(f"### {rq_title}")
        for qkey, qtext in qset.items():
            default_val = defaults[qkey] if defaults else 3
            answers[qkey] = st.radio(qtext, [1, 2, 3, 4, 5], horizontal=True,
                                     index=default_val - 1, key=qkey)
        st.divider()
    return answers


# --------------------------------------------------------------------------- logged-in
if user:
    render_sidebar(user)
    st.title("Pilot Test Questionnaire")

    existing = get_response_for_user(user["user_id"])
    if not existing and guest_response_for_user(user["user_id"]):
        st.success("You have already completed this questionnaire (as a guest). Thank you — "
                   "each person can respond only once.")
        st.stop()
    if existing:
        st.info("You've already submitted a response. Editing and saving below will update it.")
    else:
        st.write(
            "Thank you for testing the Warehouse Management System. Please rate each statement below on a "
            "scale of 1 (Strongly Disagree) to 5 (Strongly Agree), comparing your "
            "experience with the previous manual process against the new system "
            "where relevant."
        )
    st.caption(f"{response_count()} responses collected so far.")

    with st.form("questionnaire_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            respondent_name = st.text_input("Your Name", value=existing["respondent_name"] if existing else user.get("full_name", ""))
        with col2:
            respondent_station = st.text_input("Station", value=existing["respondent_station"] if existing else (user.get("port_code") or ""))
        with col3:
            respondent_role = st.text_input("Role", value=existing["respondent_role"] if existing else user.get("role_name", ""))

        st.markdown(SCALE)
        answers = _questions_block(existing)
        comments = st.text_area("Any additional comments or suggestions?", value=existing["comments"] if existing and existing["comments"] else "")
        submitted = st.form_submit_button("Update My Response" if existing else "Submit Questionnaire", type="primary")

    if submitted:
        if not respondent_name:
            st.error("Please enter your name.")
        else:
            was_update = submit_response(respondent_name, respondent_station, respondent_role, user["user_id"], answers, comments)
            if was_update:
                st.success("Your response has been updated. Thank you for your continued feedback.")
            else:
                st.success("Your response has been saved. Thank you for participating in the pilot test.")
            st.rerun()
    st.stop()

# --------------------------------------------------------------------------- guest
st.title("Pilot Test Questionnaire")

if st.session_state.get("gq_done"):
    st.success("Thank you — your response has been recorded.")
    st.markdown(
        "### Want to see the system for yourself?\n"
        "You are welcome to **log in and test the Warehouse Management System**. "
        "Use the login page of this app with the test account details given to you by the "
        "research team (ask them if you do not have one yet). Your feedback after trying the "
        "system helps us improve it."
    )
    st.stop()

st.markdown("## About this project")
st.markdown(
    "State warehouses at ZIMRA border posts hold goods under a **Receipt for Items Held (RIH)**, "
    "which must be cleared within **60 days**, and goods under a **Notice of Seizure (NOS)**, which "
    "must be dealt with within **3 months**. Today these deadlines, the rent owed, the stock actually "
    "on the floor and the approvals behind every release, forfeiture, destruction or auction are "
    "tracked on paper and spreadsheets. That makes it easy to miss a deadline, lose track of goods, "
    "or lose revenue."
)
st.markdown(
    "Our research group built the **Warehouse Management System** to fix this:\n"
    "- **Officers** capture each RIH/NOS with a printable, QR-verifiable document.\n"
    "- **Automatic alerts** for approaching deadlines and perishable goods expiring.\n"
    "- **Supervisor and Manager approval** for every release, forfeiture, destruction, e-auction "
    "and transfer between warehouses, with printable closing documents.\n"
    "- **Monthly stocktakes** that score each warehouse and flag possible losses.\n"
    "- A complete **audit trail** of who did what and when."
)
st.success(
    "🔒 **Your information is private.** This research is carried out with the **authority of "
    "ZIMRA**. Your name and email are collected solely for this research, to record your "
    "response and to prevent duplicate submissions. They are kept confidential within ZIMRA, "
    "are not published or shared outside the research, and are not used for any other purpose."
)
st.info(
    "**Why your answers matter.** This is a pilot study. Your honest ratings decide whether the system "
    "is improved, and are used in our research findings. It takes about **5 minutes**, there are no "
    "right or wrong answers, and results are reported as combined figures, not by individual."
)

st.divider()
st.markdown("## Step 1 — Who is responding?")
st.caption("Authorised by ZIMRA. Your name and ZIMRA email are private and used solely for this "
           "research: to record your response and to make sure each person responds once.")

if not st.session_state.get("gq_ident"):
    with st.form("gq_ident_form"):
        g_name = st.text_input("Full name *")
        g_email = st.text_input(f"ZIMRA email * (ending in @{ALLOWED_DOMAINS[0]})")
        c1, c2 = st.columns(2)
        with c1:
            g_station = st.text_input("Station (optional)")
        with c2:
            g_role = st.text_input("Role / position (optional)")
        go = st.form_submit_button("Continue to the questionnaire", type="primary")
    if go:
        if not g_name.strip() or len(g_name.strip().split()) < 2:
            st.error("Please enter your full name (first name and surname).")
        elif email_problem(g_email):
            st.error(email_problem(g_email))
        elif email_already_responded(g_email):
            st.warning("A response from this email address has already been recorded. "
                       "Each person can respond only once — thank you for taking part.")
        else:
            st.session_state["gq_ident"] = {"name": g_name.strip(), "email": clean_email(g_email),
                                            "station": g_station.strip(), "role": g_role.strip()}
            st.rerun()
    st.stop()

ident = st.session_state["gq_ident"]
st.success(f"Responding as **{ident['name']}** ({ident['email']})")
if st.button("Not you? Change details"):
    st.session_state.pop("gq_ident", None)
    st.rerun()

st.markdown("## Step 2 — Questionnaire")
st.write("Please rate each statement from 1 (Strongly Disagree) to 5 (Strongly Agree), comparing "
         "your experience with the previous manual process against the new system where relevant.")
with st.form("gq_form"):
    st.markdown(SCALE)
    answers = _questions_block()
    comments = st.text_area("Any additional comments or suggestions?")
    sent = st.form_submit_button("Submit Questionnaire", type="primary")

if sent:
    saved = submit_guest_response(ident["name"], ident["email"], ident["station"], ident["role"],
                                  answers, comments)
    if saved:
        st.session_state["gq_done"] = True
        st.session_state.pop("gq_ident", None)
        st.rerun()
    else:
        st.session_state.pop("gq_ident", None)
        st.warning("A response from this email address has already been recorded, so this one was "
                   "not saved. Each person can respond only once.")
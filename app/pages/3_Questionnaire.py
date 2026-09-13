"""
Pilot-test Questionnaire: 15 Likert-scale (1-5) items grouped under
3 research questions. One response per person — resubmitting updates
your existing answers rather than creating a duplicate.
"""
import streamlit as st

from app.theme import render_sidebar, inject_global_css
from app.questionnaire import QUESTIONS, submit_response, response_count, get_response_for_user

st.set_page_config(page_title="Questionnaire — WMS-Trak", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("Pilot Test Questionnaire")

existing = get_response_for_user(user["user_id"])
if existing:
    st.info("You've already submitted a response. Editing and saving below will update it.")
else:
    st.write(
        "Thank you for testing WMS-Trak. Please rate each statement below on a "
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

    st.markdown("**1 = Strongly Disagree · 2 = Disagree · 3 = Neutral · 4 = Agree · 5 = Strongly Agree**")

    answers = {}
    for rq_title, qset in QUESTIONS.items():
        st.markdown(f"### {rq_title}")
        for qkey, qtext in qset.items():
            default_val = existing[qkey] if existing else 3
            answers[qkey] = st.radio(
                qtext, [1, 2, 3, 4, 5], horizontal=True,
                index=default_val - 1, key=qkey,
            )
        st.divider()

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
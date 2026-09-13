"""
Pilot-test Questionnaire: 15 Likert-scale (1-5) items grouped under
3 research questions, for officers/supervisors/managers who used
WMS-Trak during pilot testing.
"""
import streamlit as st

from app.theme import render_sidebar, inject_global_css
from app.questionnaire import QUESTIONS, submit_response, response_count

st.set_page_config(page_title="Questionnaire — WMS-Trak", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("Pilot Test Questionnaire")
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
        respondent_name = st.text_input("Your Name", value=user.get("full_name", ""))
    with col2:
        respondent_station = st.text_input("Station", value=user.get("port_code") or "")
    with col3:
        respondent_role = st.text_input("Role", value=user.get("role_name", ""))

    st.markdown("**1 = Strongly Disagree · 2 = Disagree · 3 = Neutral · 4 = Agree · 5 = Strongly Agree**")

    answers = {}
    for rq_title, qset in QUESTIONS.items():
        st.markdown(f"### {rq_title}")
        for qkey, qtext in qset.items():
            answers[qkey] = st.radio(qtext, [1, 2, 3, 4, 5], horizontal=True, index=2, key=qkey)
        st.divider()

    comments = st.text_area("Any additional comments or suggestions?")
    submitted = st.form_submit_button("Submit Questionnaire", type="primary")

if submitted:
    if not respondent_name:
        st.error("Please enter your name.")
    else:
        submit_response(respondent_name, respondent_station, respondent_role, user["user_id"], answers, comments)
        st.success("Thank you — your response has been recorded.")
        st.rerun()
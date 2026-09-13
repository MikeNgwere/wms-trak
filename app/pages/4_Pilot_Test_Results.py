"""
Pilot Test Results: visualizations and statistical analysis of the
pilot-test questionnaire — pie/bar charts of response distributions,
per-RQ reliability (Cronbach's alpha), and a paired t-test comparing
manual-process weaknesses (RQ1) against digital-system effectiveness
(RQ2), for direct use in the research paper's results section.
"""
import streamlit as st
import plotly.express as px
import pandas as pd

from app.theme import render_sidebar, inject_global_css
from app.questionnaire import QUESTIONS, response_count
from app.pilot_stats import (
    get_dataframe, rq_mean_per_respondent, cronbach_alpha,
    paired_ttest, question_mean_scores, overall_response_distribution, rq_question_keys,
)

st.set_page_config(page_title="Pilot Test Results — WMS-Trak", layout="wide")
inject_global_css()

user = st.session_state.get("user")
if not user:
    st.warning("Please log in first.")
    st.stop()
render_sidebar(user)

st.title("Pilot Test Results")

df = get_dataframe()
n = response_count()

if df.empty or n < 2:
    st.info(
        f"{n} response(s) collected so far. At least 2 responses are needed "
        "for statistical analysis — encourage more pilot testers to complete "
        "the Questionnaire tab."
    )
    st.stop()

st.metric("Total Respondents", n)

st.divider()

# ---------------- Per-RQ mean scores ----------------
st.markdown("## Mean Scores by Research Question")
rq_means = {}
for rq_title in QUESTIONS:
    rq_means[rq_title] = rq_mean_per_respondent(df, rq_title)

col1, col2, col3 = st.columns(3)
for col, (rq_title, series) in zip([col1, col2, col3], rq_means.items()):
    with col:
        st.metric(rq_title.split(" — ")[0], f"{series.mean():.2f} / 5")
        st.caption(rq_title.split(" — ")[1])

# Bar chart: mean score per question, coloured by RQ
qmeans_df = question_mean_scores(df)
fig_bar = px.bar(
    qmeans_df, x="Question", y="Mean Score", color="Research Question",
    hover_data=["Text"], title="Mean Score per Question (1-5 scale)",
    range_y=[0, 5],
)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ---------------- Overall response distribution ----------------
st.markdown("## Overall Response Distribution")
dist = overall_response_distribution(df)
fig_pie = px.pie(
    names=[f"{i} — " + ["Strongly Disagree","Disagree","Neutral","Agree","Strongly Agree"][i-1] for i in dist.index],
    values=dist.values,
    title="Distribution of All Likert Responses (all 15 questions combined)",
)
st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ---------------- Reliability: Cronbach's alpha ----------------
st.markdown("## Scale Reliability (Cronbach's Alpha)")
st.write(
    "Cronbach's alpha measures internal consistency — whether the questions "
    "within each research question genuinely measure the same underlying "
    "construct. Values above 0.7 are generally considered acceptable."
)
alpha_cols = st.columns(3)
for col, rq_title in zip(alpha_cols, QUESTIONS):
    keys = rq_question_keys(rq_title)
    alpha = cronbach_alpha(df[keys])
    with col:
        st.metric(rq_title.split(" — ")[0] + " α", f"{alpha:.3f}" if pd.notna(alpha) else "N/A")

st.divider()

# ---------------- Key hypothesis test: RQ2 vs RQ1 ----------------
st.markdown("## Statistical Test: Does WMS-Trak Improve on the Manual Process?")
st.write(
    "A paired t-test compares each respondent's average agreement with "
    "**RQ1 (manual process weaknesses)** against their average agreement "
    "with **RQ2 (digital system effectiveness)**. A significantly higher "
    "RQ2 score (p < 0.05) supports the conclusion that WMS-Trak addresses "
    "the weaknesses identified in the manual process."
)
rq1_scores = rq_means["RQ1 — Manual Process Weaknesses"]
rq2_scores = rq_means["RQ2 — Digital System Effectiveness"]
t_stat, p_value = paired_ttest(rq1_scores, rq2_scores)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("RQ1 Mean (Manual Weaknesses)", f"{rq1_scores.mean():.2f}")
with col2:
    st.metric("RQ2 Mean (System Effectiveness)", f"{rq2_scores.mean():.2f}")
with col3:
    st.metric("t-statistic", f"{t_stat:.3f}")

st.metric("p-value", f"{p_value:.4f}")
if p_value < 0.05:
    st.success(
        "The difference is statistically significant (p < 0.05) — respondents "
        "rated the manual process's weaknesses and the digital system's "
        "effectiveness as meaningfully different, supporting the case that "
        "WMS-Trak addresses the identified problems."
    )
else:
    st.warning(
        "The difference is not statistically significant at the p < 0.05 "
        "level with the current sample size — consider collecting more "
        "responses before drawing strong conclusions."
    )

st.divider()

# ---------------- Usability (RQ3) ----------------
st.markdown("## Usability & Perceived Impact (RQ3)")
rq3_scores = rq_means["RQ3 — Usability & Perceived Impact"]
fig_rq3 = px.histogram(
    rq3_scores, nbins=10, title="Distribution of Average RQ3 Scores per Respondent",
    labels={"value": "Average Score (1-5)"},
)
st.plotly_chart(fig_rq3, use_container_width=True)
st.metric("RQ3 Mean", f"{rq3_scores.mean():.2f} / 5")

st.divider()

# ---------------- Raw data ----------------
with st.expander("View raw response data"):
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download as CSV", csv, "pilot_test_responses.csv", "text/csv")
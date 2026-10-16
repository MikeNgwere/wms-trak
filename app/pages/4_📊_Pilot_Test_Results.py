"""
Pilot Test Results: visualizations and statistical analysis of the
pilot-test questionnaire — sample adequacy against the study population,
pie/bar charts of response distributions, per-RQ reliability (Cronbach's alpha),
agreement tested against the neutral midpoint of the scale, and a paired
comparison of manual-process weaknesses (RQ1) with digital-system
effectiveness (RQ2), for direct use in the research paper's results section.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import streamlit as st
import plotly.express as px
import pandas as pd

from app.theme import render_sidebar, inject_global_css
from app.questionnaire import QUESTIONS, response_count
from app.pilot_stats import (
    get_dataframe, rq_mean_per_respondent, cronbach_alpha,
    paired_ttest, question_mean_scores, overall_response_distribution, rq_question_keys,
    POPULATION_SIZE, TARGET_MARGIN, NEUTRAL, required_sample, margin_of_error, vs_neutral, verdict,
)

st.set_page_config(page_title="Pilot Test Results — Warehouse Management System", layout="wide")
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

# ---------------- Sample adequacy ----------------
st.markdown("## Sample Adequacy")
need = required_sample()
moe = margin_of_error(n)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Responses received", n)
c2.metric("Target population", POPULATION_SIZE)
c3.metric("Response rate", f"{100 * n / POPULATION_SIZE:.1f}%")
c4.metric("Margin of error (95%)", f"±{100 * moe:.1f}%")
st.progress(min(n / need, 1.0))
if n >= need:
    st.success(
        f"Target reached: {n} responses meets the {need} needed for a ±{TARGET_MARGIN * 100:.0f}% "
        f"margin of error at 95% confidence (population {POPULATION_SIZE})."
    )
else:
    st.info(
        f"**{need - n} more responses** are needed to reach the ±{TARGET_MARGIN * 100:.0f}% target "
        f"({need} responses for a population of {POPULATION_SIZE}, 95% confidence, "
        "finite-population correction)."
    )

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

# ---------------- Main test: agreement against the neutral midpoint ----------------
st.markdown("## Statistical Test: Do Respondents Agree? (against the neutral midpoint)")
st.write(
    f"Each respondent's average for a research question is compared with the neutral midpoint "
    f"(**{NEUTRAL}** = 'Neutral') using a one-sample t-test and, because Likert data are ordinal, "
    "a Wilcoxon signed-rank test as a check. A mean significantly **above** 3 (p < 0.05) means "
    "respondents, as a group, agree with that research question's statements. "
    "**d** is the effect size (0.2 small, 0.5 medium, 0.8 large)."
)
rows = []
for rq_title, series in rq_means.items():
    r = vs_neutral(series)
    rows.append({
        "Research question": rq_title,
        "n": r["n"],
        "Mean": round(r["mean"], 2),
        "SD": round(r["sd"], 2) if pd.notna(r["sd"]) else None,
        "95% CI": f"{r['ci_low']:.2f} – {r['ci_high']:.2f}" if pd.notna(r["ci_low"]) else "—",
        "t": round(r["t"], 2) if pd.notna(r["t"]) else None,
        "p (t-test)": "<0.001" if pd.notna(r["p_t"]) and r["p_t"] < 0.001 else (round(r["p_t"], 3) if pd.notna(r["p_t"]) else None),
        "p (Wilcoxon)": "<0.001" if pd.notna(r["p_wilcoxon"]) and r["p_wilcoxon"] < 0.001 else (round(r["p_wilcoxon"], 3) if pd.notna(r["p_wilcoxon"]) else None),
        "d": round(r["d"], 2) if pd.notna(r["d"]) else None,
        "Conclusion": verdict(r),
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ---------------- Descriptive comparison: RQ2 vs RQ1 ----------------
st.markdown("## Comparison: Manual Process Weaknesses (RQ1) vs System Effectiveness (RQ2)")
st.write(
    "A paired t-test checks whether each respondent's average agreement differs between "
    "**RQ1 (manual process weaknesses)** and **RQ2 (digital system effectiveness)**. These are two "
    "different constructs, so a non-significant difference is **not** evidence against the system: "
    "if respondents agree strongly that the manual process is weak *and* that the system is effective, "
    "the two averages will be close. Use this as a descriptive comparison and rely on the "
    "agreement tests above for the main conclusion."
)
rq1_scores = rq_means["RQ1 — Manual Process Weaknesses"]
rq2_scores = rq_means["RQ2 — Digital System Effectiveness"]
t_stat, p_value = paired_ttest(rq1_scores, rq2_scores)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("RQ1 Mean (Manual Weaknesses)", f"{rq1_scores.mean():.2f}")
with col2:
    st.metric("RQ2 Mean (System Effectiveness)", f"{rq2_scores.mean():.2f}")
with col3:
    st.metric("t-statistic", f"{t_stat:.3f}")
with col4:
    st.metric("p-value", f"{p_value:.4f}")
if p_value < 0.05:
    st.info("The two averages differ significantly (p < 0.05): respondents rated "
            "the manual process's weaknesses and the system's effectiveness differently.")
else:
    st.info("The two averages are not significantly different (p ≥ 0.05): respondents rated "
            "the manual process's weaknesses and the system's effectiveness similarly. "
            "This is expected when both are rated highly, and does not count against the system.")

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
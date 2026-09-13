"""
Statistical helpers for the Pilot Test Results page: per-RQ scores,
Cronbach's alpha (scale reliability), and a paired t-test comparing
RQ1 (manual process weaknesses) against RQ2 (digital system
effectiveness) — the core evidence for "does WMS-Trak improve on the
manual process" in the research paper.
"""
import pandas as pd
import numpy as np
from scipy import stats

from app.questionnaire import QUESTIONS, all_responses

ALL_QUESTION_KEYS = [f"q{i}" for i in range(1, 16)]


def get_dataframe() -> pd.DataFrame:
    rows = all_responses()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def rq_question_keys(rq_title: str) -> list:
    return list(QUESTIONS[rq_title].keys())


def rq_mean_per_respondent(df: pd.DataFrame, rq_title: str) -> pd.Series:
    keys = rq_question_keys(rq_title)
    return df[keys].mean(axis=1)


def cronbach_alpha(item_df: pd.DataFrame) -> float:
    """Standard Cronbach's alpha for internal consistency of a scale."""
    item_vars = item_df.var(axis=0, ddof=1)
    total_var = item_df.sum(axis=1).var(ddof=1)
    n_items = item_df.shape[1]
    if total_var == 0 or n_items < 2:
        return float("nan")
    alpha = (n_items / (n_items - 1)) * (1 - item_vars.sum() / total_var)
    return alpha


def paired_ttest(series_a: pd.Series, series_b: pd.Series):
    """Paired t-test: is series_b (e.g. RQ2) significantly different from series_a (RQ1)?"""
    if len(series_a) < 2:
        return float("nan"), float("nan")
    t_stat, p_value = stats.ttest_rel(series_b, series_a)
    return t_stat, p_value


def question_mean_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Mean score per question, with question text, for bar charts."""
    rows = []
    for rq_title, qset in QUESTIONS.items():
        for qkey, qtext in qset.items():
            rows.append({
                "Research Question": rq_title,
                "Question": qkey.upper(),
                "Text": qtext,
                "Mean Score": df[qkey].mean(),
            })
    return pd.DataFrame(rows)


def overall_response_distribution(df: pd.DataFrame) -> pd.Series:
    """Flattened distribution of all 1-5 responses across all 15 questions."""
    all_values = pd.concat([df[k] for k in ALL_QUESTION_KEYS])
    return all_values.value_counts().sort_index()
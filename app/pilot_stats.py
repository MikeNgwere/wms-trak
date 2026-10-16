"""
Statistical helpers for the Pilot Test Results page: per-RQ scores,
Cronbach's alpha (scale reliability), and a paired t-test comparing
RQ1 (manual process weaknesses) against RQ2 (digital system
effectiveness) — the core evidence for "does Warehouse Management System improve on the
manual process" in the research paper.
"""
import math

import pandas as pd
import numpy as np
from scipy import stats

from app.questionnaire import QUESTIONS, all_responses

ALL_QUESTION_KEYS = [f"q{i}" for i in range(1, 16)]

# Study design: target population and the precision we want to reach.
POPULATION_SIZE = 120
TARGET_MARGIN = 0.05     # +/-5 % at 95 % confidence
Z_95 = 1.96
NEUTRAL = 3              # midpoint of the 1-5 Likert scale


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


# ---------------------------------------------------------------- sample size / precision
def required_sample(population=POPULATION_SIZE, margin=TARGET_MARGIN, z=Z_95, p=0.5) -> int:
    """Responses needed for the target margin of error (Cochran with finite-population correction)."""
    n0 = (z ** 2) * p * (1 - p) / (margin ** 2)
    return math.ceil(n0 / (1 + (n0 - 1) / population))


def margin_of_error(n, population=POPULATION_SIZE, z=Z_95, p=0.5) -> float:
    """Margin of error (as a fraction) for n responses from a finite population."""
    if n <= 0:
        return float("nan")
    if n >= population:
        return 0.0
    return math.sqrt((z ** 2) * p * (1 - p) / n * (population - n) / (population - 1))


# ---------------------------------------------------------------- agreement vs neutral
def vs_neutral(series: pd.Series, mu=NEUTRAL) -> dict:
    """Is average agreement different from the neutral midpoint? t-test, Wilcoxon, effect size, 95% CI."""
    x = series.dropna().astype(float)
    n = len(x)
    out = {"n": n, "mean": float(x.mean()) if n else float("nan"), "sd": float("nan"),
           "ci_low": float("nan"), "ci_high": float("nan"), "t": float("nan"),
           "p_t": float("nan"), "p_wilcoxon": float("nan"), "d": float("nan")}
    if n < 2:
        return out
    sd = float(x.std(ddof=1))
    out["sd"] = sd
    se = sd / math.sqrt(n)
    tcrit = stats.t.ppf(0.975, n - 1)
    out["ci_low"], out["ci_high"] = out["mean"] - tcrit * se, out["mean"] + tcrit * se
    if sd > 0:
        t, p = stats.ttest_1samp(x, mu)
        out["t"], out["p_t"] = float(t), float(p)
        out["d"] = (out["mean"] - mu) / sd
    try:
        out["p_wilcoxon"] = float(stats.wilcoxon(x - mu, zero_method="wilcox").pvalue)
    except ValueError:
        pass  # every value equals the midpoint
    return out


def verdict(res: dict, alpha=0.05) -> str:
    p = res["p_t"]
    if p != p:  # NaN
        return "Not enough data"
    if p < alpha:
        return "Significantly above neutral (agree)" if res["mean"] > NEUTRAL else "Significantly below neutral (disagree)"
    return "Not different from neutral"
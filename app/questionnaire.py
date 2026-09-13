"""
Pilot-test questionnaire: 15 Likert-scale (1-5) items grouped under
3 research questions, plus statistical summary helpers for the
Pilot Test Results page. One response per person — resubmitting
updates the existing row rather than creating a duplicate.

RQ1 (Q1-Q5):  Manual process weaknesses (baseline, pre-WMS-Trak)
RQ2 (Q6-Q10): Digital system effectiveness (WMS-Trak)
RQ3 (Q11-Q15): Usability & perceived impact
"""
from app.db import fetch_all, fetch_one, execute

QUESTIONS = {
    "RQ1 — Manual Process Weaknesses": {
        "q1": "The manual (paper-based) system made it difficult to track how long goods had been in the warehouse.",
        "q2": "Overstayed RIH/NOS goods were often discovered late using the manual register.",
        "q3": "Reconciling physical stock with records was time-consuming under the manual system.",
        "q4": "It was difficult to get a consolidated view of warehouse compliance status using manual records.",
        "q5": "Errors or lost records were common with the manual/paper-based process.",
    },
    "RQ2 — Digital System Effectiveness": {
        "q6": "WMS-Trak makes it easier to track RIH/NOS goods and their bond/appeal deadlines.",
        "q7": "The system improves accuracy in recording and reconciling warehouse goods.",
        "q8": "WMS-Trak helps identify overstayed or flagged goods faster than the manual process.",
        "q9": "The Officer→Supervisor→Manager approval workflow improves accountability compared to manual sign-offs.",
        "q10": "The system provides a more reliable audit trail than paper records.",
    },
    "RQ3 — Usability & Perceived Impact": {
        "q11": "WMS-Trak is easy to navigate and use in my daily work.",
        "q12": "I am confident using the system without needing frequent assistance.",
        "q13": "The system positively impacts revenue collection and reporting accuracy.",
        "q14": "I would recommend wider rollout of WMS-Trak to other stations.",
        "q15": "Overall, WMS-Trak is an improvement over the manual system.",
    },
}

ALL_QUESTION_KEYS = [f"q{i}" for i in range(1, 16)]


def get_response_for_user(user_id: int):
    return fetch_one("SELECT * FROM questionnaire_responses WHERE submitted_by_user_id = %s", (user_id,))


def submit_response(respondent_name: str, respondent_station: str, respondent_role: str,
                     submitted_by_user_id: int, answers: dict, comments: str = "") -> bool:
    """
    answers: dict of q1..q15 -> int (1-5).
    Inserts a new response, or updates the existing one for this user
    (one response per person). Returns True if this was an update
    (existing response), False if it was a fresh insert.
    """
    existing = get_response_for_user(submitted_by_user_id)
    cols = ALL_QUESTION_KEYS
    values = [answers[k] for k in cols]

    if existing:
        set_clause = ", ".join(f"{k} = %s" for k in cols)
        execute(
            f"""
            UPDATE questionnaire_responses
            SET respondent_name = %s, respondent_station = %s, respondent_role = %s,
                {set_clause}, comments = %s, submitted_at = now()
            WHERE submitted_by_user_id = %s
            """,
            [respondent_name, respondent_station, respondent_role] + values + [comments, submitted_by_user_id],
        )
        return True
    else:
        col_list = ", ".join(cols)
        placeholders = ", ".join(["%s"] * 15)
        execute(
            f"""
            INSERT INTO questionnaire_responses (
                respondent_name, respondent_station, respondent_role,
                submitted_by_user_id, {col_list}, comments
            )
            VALUES (%s, %s, %s, %s, {placeholders}, %s)
            """,
            [respondent_name, respondent_station, respondent_role, submitted_by_user_id] + values + [comments],
        )
        return False


def all_responses():
    return fetch_all("SELECT * FROM questionnaire_responses ORDER BY submitted_at DESC")


def response_count():
    row = fetch_one("SELECT COUNT(*) AS n FROM questionnaire_responses")
    return row["n"] if row else 0
"""Guest (no-login) questionnaire helpers: email validation and one-response-per-email."""
import re
from app.db import fetch_one

ALLOWED_DOMAINS = ("zimra.co.zw",)
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@([A-Za-z0-9\-]+\.)+[A-Za-z]{2,}$")


def clean_email(email):
    return (email or "").strip().lower()


def email_problem(email):
    """Return an error message if the email is unacceptable, else None."""
    e = clean_email(email)
    if not e:
        return "Please enter your ZIMRA email address."
    if not _EMAIL_RE.match(e):
        return "That does not look like a valid email address."
    if e.split("@", 1)[1] not in ALLOWED_DOMAINS:
        return "Please use your ZIMRA email address (ending in @" + ALLOWED_DOMAINS[0] + ")."
    return None


def email_already_responded(email):
    return fetch_one(
        "SELECT response_id FROM questionnaire_responses WHERE LOWER(respondent_email) = %s",
        (clean_email(email),)) is not None


def submit_guest_response(name, email, station, role, answers, comments):
    """Insert one guest response. Returns True if saved, False if that email already responded."""
    cols = sorted(answers, key=lambda k: int(k[1:]))
    sql = (
        "INSERT INTO questionnaire_responses (respondent_name, respondent_email, respondent_station, "
        "respondent_role, submitted_by_user_id, " + ", ".join(cols) + ", comments, submitted_at) "
        "VALUES (%s, %s, %s, %s, NULL, " + ", ".join(["%s"] * len(cols)) + ", %s, NOW()) "
        "ON CONFLICT DO NOTHING RETURNING response_id"
    )
    params = [name.strip(), clean_email(email), (station or "").strip(), (role or "").strip() or "Guest"]
    params += [answers[c] for c in cols] + [(comments or "").strip()]
    return fetch_one(sql, tuple(params)) is not None

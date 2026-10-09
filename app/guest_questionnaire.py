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


_HAS_USER_EMAIL = None


def _user_match_sql():
    """SQL fragment matching users whose username (or email column, if present) equals %s."""
    global _HAS_USER_EMAIL
    if _HAS_USER_EMAIL is None:
        r = fetch_one("SELECT 1 AS ok FROM information_schema.columns "
                      "WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'email'")
        _HAS_USER_EMAIL = bool(r)
    return ("(LOWER(username) = %s OR LOWER(email) = %s)", 2) if _HAS_USER_EMAIL else ("LOWER(username) = %s", 1)


def email_already_responded(email):
    """True if this email has a guest response, or belongs to an account that has responded."""
    e = clean_email(email)
    if fetch_one("SELECT 1 AS ok FROM questionnaire_responses WHERE LOWER(respondent_email) = %s LIMIT 1", (e,)):
        return True
    try:
        cond, n = _user_match_sql()
        return fetch_one(
            "SELECT 1 AS ok FROM questionnaire_responses r WHERE r.submitted_by_user_id IN "
            "(SELECT user_id FROM users WHERE " + cond + ") LIMIT 1", (e,) * n) is not None
    except Exception:
        return False  # account lookup unavailable: the guest-email check above still applies


def guest_response_for_user(user_id):
    """A guest-mode response previously given under this logged-in user's email, if any."""
    try:
        u = fetch_one("SELECT username" + (", email" if _user_match_sql()[1] == 2 else "") +
                      " FROM users WHERE user_id = %s", (user_id,))
        for e in {clean_email(v) for v in (u or {}).values() if v}:
            r = fetch_one("SELECT response_id FROM questionnaire_responses WHERE LOWER(respondent_email) = %s", (e,))
            if r:
                return r
    except Exception:
        pass
    return None


def submit_guest_response(name, email, station, role, answers, comments):
    """Insert one guest response. Returns True if saved, False if that email already responded."""
    if email_already_responded(email):
        return False
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


def submit_anonymous_response(answers, comments):
    """Store a response with no name or email, recorded as 'Anonymous N'."""
    cols = sorted(answers, key=lambda k: int(k[1:]))
    sql = (
        "INSERT INTO questionnaire_responses (respondent_name, respondent_email, respondent_station, "
        "respondent_role, submitted_by_user_id, is_anonymous, " + ", ".join(cols) + ", comments, submitted_at) "
        "VALUES ('Anonymous ' || nextval('questionnaire_anon_seq'), NULL, '', 'Anonymous', NULL, TRUE, "
        + ", ".join(["%s"] * len(cols)) + ", %s, NOW()) RETURNING response_id"
    )
    params = [answers[c] for c in cols] + [(comments or "").strip()]
    return fetch_one(sql, tuple(params)) is not None
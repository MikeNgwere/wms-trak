"""
Bond / transit period engine.

Reads allowed periods from the `bond_rules` table (not hardcoded), so the
group can adjust figures as the Act review is finalised, without touching
application code.

Core responsibilities:
1. Compute `bond_due_date` for a new entry based on entry_type + load_condition.
2. Identify entries approaching or past their due date (for alerts/flags).
3. Drive the RIH forfeiture-flag workflow and the NOS seizure -> disposal workflow.
"""
from datetime import timedelta

from app.db import fetch_one, fetch_all, execute

# NOS appeal window: 3 months from notice of seizure (C&E Act s.193(12)).
# If no proceedings are instituted within this window, goods vest for
# forfeiture and disposal per s.193(13). See docs/LEGAL_FRAMEWORK.md §4.
NOS_APPEAL_WINDOW_DAYS = 90

# Minimum Gazette notice required before a public auction of forfeited/
# unentered goods (C&E Act s.39(3)).
AUCTION_MIN_NOTICE_DAYS = 30


def get_allowed_days(entry_type: str, load_condition: str | None = None) -> int | None:
    row = fetch_one(
        """
        SELECT allowed_days FROM bond_rules
        WHERE entry_type = %s
          AND (load_condition = %s OR (%s IS NULL AND load_condition IS NULL))
        """,
        (entry_type, load_condition, load_condition),
    )
    return row["allowed_days"] if row else None


def compute_due_date(date_entered, entry_type: str, load_condition: str | None = None):
    days = get_allowed_days(entry_type, load_condition)
    if days is None:
        return None
    return date_entered + timedelta(days=days)


def entries_nearing_expiry(warning_window_days: int = 2):
    """Entries not yet acquitted/closed, due within the warning window or overdue."""
    return fetch_all(
        """
        SELECT entry_id, entry_number, entry_type, port_code, bond_due_date, status
        FROM entries
        WHERE status IN ('in_warehouse','in_transit','in_bond')
          AND bond_due_date IS NOT NULL
          AND bond_due_date <= now() + (%s || ' days')::interval
        ORDER BY bond_due_date ASC
        """,
        (warning_window_days,),
    )


def flag_overdue_entries():
    """
    Run periodically (e.g. via a scheduled GitHub Action or cron script).
    Flags entries whose bond period has lapsed without acquittal/payment.
    RIH entries flagged this way become forfeiture candidates after the
    configured allowed_days (default 90 / 3 months) with no payment recorded.
    """
    overdue = fetch_all(
        """
        SELECT entry_id, entry_number, entry_type
        FROM entries
        WHERE status IN ('in_warehouse','in_transit','in_bond')
          AND bond_due_date IS NOT NULL
          AND bond_due_date < now()
        """
    )
    for e in overdue:
        execute(
            "UPDATE entries SET status = 'flagged', updated_at = now() WHERE entry_id = %s",
            (e["entry_id"],),
        )
        execute(
            """
            INSERT INTO audit_log (entry_id, entry_number, action, notes)
            VALUES (%s, %s, 'AUTO_FLAGGED_OVERDUE', 'Bond/transit period lapsed without acquittal')
            """,
            (e["entry_id"], e["entry_number"]),
        )
    return len(overdue)


def mark_ready_for_disposal_if_no_appeal():
    """
    NOS workflow: once appeal_deadline has passed with no pending appeal,
    mark the seizure ready_for_disposal = TRUE so a Manager can approve
    offhand sale / appropriation / auction.
    """
    candidates = fetch_all(
        """
        SELECT s.seizure_id, s.entry_id, e.entry_number
        FROM seizures s
        JOIN entries e ON e.entry_id = s.entry_id
        WHERE s.ready_for_disposal = FALSE
          AND s.appeal_status IN ('none','rejected')
          AND s.appeal_deadline IS NOT NULL
          AND s.appeal_deadline < now()
        """
    )
    for c in candidates:
        execute(
            "UPDATE seizures SET ready_for_disposal = TRUE WHERE seizure_id = %s",
            (c["seizure_id"],),
        )
        execute(
            """
            INSERT INTO audit_log (entry_id, entry_number, action, notes)
            VALUES (%s, %s, 'READY_FOR_DISPOSAL', 'No appeal within window; awaiting manager approval')
            """,
            (c["entry_id"], c["entry_number"]),
        )
    return len(candidates)
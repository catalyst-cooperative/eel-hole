"Centralized logging configuration."

import logging
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from flask_login import current_user


def user_info_adder(logger, log_method, event_dict):
    """Add user information to log if available.

    When there is no user in context (such as during app startup),
    `user_id` and `user_domain` will not be added to the log event.

    When there is a user in context but the user is anonymous,
    `user_id` and `user_domain` will be added to the log event,
    but with value `null`.

    Must be added to processor list *before* JSONRenderer, otherwise event_dict
    will be rendered to string already.
    """
    if current_user:
        event_dict["user_id"] = current_user.get_id()
        event_dict["user_domain"] = (
            current_user.get_domain() if current_user.get_id() else None
        )
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        user_info_adder,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()


EventName = Literal[
    "log_in",
    "search",
    "preview",
    "duckdb_preview",
    "duckdb_csv",
    "duckdb_other",
    "privacy-policy",
    "verify-email-requested",
    "verify-email-failed",
    "refresh-email-verification-failed",
]


@dataclass(frozen=True)
class EventSpec:
    """How an analytics event is logged: its level and its keyword fields."""

    level: Literal["info", "warning"]
    fields: frozenset[str]


# Every analytics event the app logs. pudl-usage-metrics parses these logs and routes
# each event by its exact name, and expects exactly these fields plus ``event``,
# ``timestamp`` and the ``user_id`` and ``user_domain`` that ``user_info_adder`` adds
# to every event. Names must be lower-case slugs and changes here must be mirrored
# there; tests/unit/test_logging_contract.py enforces both.
EVENTS: dict[str, EventSpec] = {
    "log_in": EventSpec("info", frozenset({"next_url", "is_new_user"})),
    "search": EventSpec("info", frozenset({"url", "query"})),
    "preview": EventSpec("info", frozenset({"package", "table_name", "partition"})),
    "duckdb_preview": EventSpec("info", frozenset({"url", "params"})),
    "duckdb_csv": EventSpec("info", frozenset({"url", "params"})),
    "duckdb_other": EventSpec("info", frozenset({"url", "params"})),
    "privacy-policy": EventSpec(
        "info", frozenset({"accepted", "outreach", "newsletter"})
    ),
    "verify-email-requested": EventSpec("info", frozenset()),
    "verify-email-failed": EventSpec("warning", frozenset({"status_code"})),
    "refresh-email-verification-failed": EventSpec(
        "warning", frozenset({"status_code"})
    ),
}


def log_event(event: EventName, **fields: Any) -> None:
    """Log an analytics event that pudl-usage-metrics will pick up.

    Use this, not ``log``, for anything that should show up in usage metrics. ``log``
    is for operational messages (prose). The event name must be in ``EVENTS`` and the
    fields must be the ones it lists; the contract tests check both at every call site.
    """
    getattr(log, EVENTS[event].level)(event, **fields)

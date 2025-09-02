"Centralized logging configuration."

import logging

import structlog
from flask_login import current_user


def user_id_adder(logger, log_method, event_dict):
    """Add user ID to log if available.

    Must be added to processor list *before* JSONRenderer, otherwise event_dict
    will be rendered to string already.
    """
    if current_user:
        event_dict["user_id"] = current_user.get_id()
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        user_id_adder,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()

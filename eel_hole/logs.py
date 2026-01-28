"Centralized logging configuration."

import logging

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

"""Helper functions for using feature flags."""

from flask import has_request_context, request, session, current_app, abort
from functools import wraps


def is_flag_enabled(flag_name):
    """Basic flag logic using query string, fallback to config."""
    flag_from_config = current_app.config.get("FEATURE_FLAGS", {}).get(flag_name, False)
    if has_request_context():
        return request.args.get(flag_name) == "true" or flag_from_config
    return flag_from_config


def require_feature_flag(flag_name, value="true"):
    """Route-level decorator for flag-based gating."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if request.args.get(flag_name) != value:
                return abort(404)
            return f(*args, **kwargs)

        return wrapped

    return decorator

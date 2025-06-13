"""Helper functions for using feature flags."""

from flask import has_request_context, request, session, current_app, abort
from functools import wraps
from collections.abc import Callable


def _coerce_flag_value(value: bool | int | str) -> bool:
    """
    Convert feature flag values to a boolean.

    Acceptable inputs:
      - Booleans: True, False
      - Integers: 1 (True), 0 (False)
      - Strings: "true", "false" (case-insensitive)

    Raises:
        ValueError: If the input is not a valid flag representation.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise ValueError(
            f"Invalid int for feature flag: {value!r}. Only 0 or 1 are allowed."
        )
    if isinstance(value, str):
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
    raise ValueError(
        f"Invalid feature flag value: {value!r}. Must be a boolean, 0/1, or 'true'/'false' string."
    )


def is_flag_enabled(flag_name: str) -> bool:
    """
    Determine if a feature flag is enabled.

    1. Query string takes priority (and updates session).
    2. Session stores user-specific flag.
    3. Fallback to config default.
    """
    flag_from_config = current_app.config.get("FEATURE_FLAGS", {}).get(flag_name, False)
    coerced_flag_from_config = _coerce_flag_value(flag_from_config)

    if has_request_context():
        if flag_name in request.args:
            value = _coerce_flag_value(request.args[flag_name])
            session[flag_name] = value
            return value
        if flag_name in session:
            return session[flag_name]

    return coerced_flag_from_config


def require_feature_flag(flag_name: str, value: str = "true") -> Callable:
    """Route-level decorator that enforces feature flags using session or query params."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            expected = _coerce_flag_value(value)
            if is_flag_enabled(flag_name) != expected:
                return abort(404)
            return f(*args, **kwargs)

        return wrapped

    return decorator

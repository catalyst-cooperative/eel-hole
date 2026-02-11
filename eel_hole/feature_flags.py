"""Helper functions for using feature flags."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps

from flask import abort, current_app, request, session


@dataclass
class FeatureVariants:
    default: str
    variants: set[str]

    def is_valid(self, variant: str) -> bool:
        return (variant != "") and (variant in self.variants)


def get_variant(feature_name: str) -> str:
    """Determine what variant a feature has been set to.

    Draws from the following sources, higher in the list overrides lower.

    * URL param in current request
    * URL param in previous request in this session
    * Flask config under `FEATURE_FLAGS`

    The URL param should be of the format
    `?variants=<flag_name>:<variant>,<other_flag>:<other_variant>`.

    All feature variants must be defined in the config as FeatureVariants.

    Returns:
        str: the variant under question.

    Raises:
        404: If the feature flag is not defined in the config.
    """
    config = current_app.config.get("FEATURE_VARIANTS", {})
    if feature_name not in config:
        abort(404)
    feature_config = config[feature_name]

    current_request_variants_raw = request.args.get("variants")
    if current_request_variants_raw is None:
        pass
    else:
        kv_pairs = current_request_variants_raw.split(",")
        try:
            current_request_variants = {
                key: value for key, value in [pair.split(":") for pair in kv_pairs]
            }
        except ValueError:
            abort(404)
        current_request_variant = current_request_variants.get(feature_name, "")

        if not feature_config.is_valid(current_request_variant):
            abort(404)
        if session.get("variants"):
            session["variants"] |= {feature_name: current_request_variant}
        else:
            session["variants"] = {feature_name: current_request_variant}
        return current_request_variant

    session_variant = session.get("variants", {}).get(feature_name)
    if feature_config.is_valid(session_variant):
        return session_variant

    return feature_config.default


def require_feature_flag(flag_name: str, value: str = "true") -> Callable:
    """Route-level decorator for flag-based gating."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if request.args.get(flag_name) != value:
                return abort(404)
            return f(*args, **kwargs)

        return wrapped

    return decorator

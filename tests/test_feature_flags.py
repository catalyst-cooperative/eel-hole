import pytest
from flask import Flask
from eel_hole.feature_flags import (
    is_flag_enabled,
    require_feature_flag,
    _coerce_flag_value,
)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True
    app.config["FEATURE_FLAGS"] = {"foo": True, "bar": False}

    @app.route("/test_flag")
    def test_flag():
        return "enabled" if is_flag_enabled("foo") else "disabled"

    @app.route("/gated")
    @require_feature_flag("foo")
    def gated_route():
        return "allowed"

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.mark.parametrize(
    "input_value,expected",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("TRUE", True),
        ("false", False),
        ("FALSE", False),
    ],
)
def test_coerce_flag_value_valid(input_value, expected):
    assert _coerce_flag_value(input_value) is expected


@pytest.mark.parametrize(
    "input_value",
    [
        "yes",
        "no",
        "enabled",
        "0",
        "1",
        2,
        -1,
        [],
        {},
        None,
    ],
)
def test_coerce_flag_value_invalid(input_value):
    with pytest.raises(ValueError):
        _coerce_flag_value(input_value)


def test_is_flag_enabled_with_query_string(client):
    response = client.get("/test_flag?foo=true")
    assert response.data == b"enabled"


def test_is_flag_enabled_from_config(client):
    response = client.get("/test_flag")
    assert response.data == b"enabled"  # from config


def test_is_flag_disabled_when_false(client, app):
    # Patch config to make 'foo' false
    app.config["FEATURE_FLAGS"]["foo"] = False
    response = client.get("/test_flag")
    assert response.data == b"disabled"


def test_require_feature_flag_blocks_without_query(client, app):
    app.config["FEATURE_FLAGS"]["foo"] = False
    response = client.get("/gated")
    assert response.status_code == 404


def test_require_feature_flag_allows_with_query(client):
    response = client.get("/gated?foo=true")
    assert response.status_code == 200
    assert b"allowed" in response.data


def test_flag_persists_in_session(client):
    with client:
        client.get("/test_flag?foo=false")  # Set session value
        response = client.get("/test_flag")
        assert response.data == b"disabled"  # Persisted session state


def test_session_overrides_config(client, app):
    app.config["FEATURE_FLAGS"]["foo"] = False
    with client:
        client.get("/test_flag?foo=true")  # sets session flag to true
        response = client.get("/test_flag")
        assert response.data == b"enabled"  # session overrides config


def test_unset_flag_via_false_query(client):
    with client:
        client.get("/test_flag?foo=true")
        response = client.get("/test_flag")
        assert response.data == b"enabled"

        client.get("/test_flag?foo=false")
        response = client.get("/test_flag")
        assert response.data == b"disabled"


def test_unknown_flag_defaults_to_false(client):
    @client.application.route("/unknown_flag")
    def unknown_flag():
        return "enabled" if is_flag_enabled("unknown") else "disabled"

    response = client.get("/unknown_flag")
    assert response.data == b"disabled"


def test_require_flag_value_mismatch(client):
    @client.application.route("/false_only")
    @require_feature_flag("foo", value="false")
    def only_when_false():
        return "should not be allowed"

    with client:
        client.get("/test_flag?foo=true")  # sets session
        response = client.get("/false_only")
        assert response.status_code == 404

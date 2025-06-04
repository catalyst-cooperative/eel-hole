import pytest
from flask import Flask
from eel_hole.feature_flags import is_flag_enabled, require_feature_flag


@pytest.fixture
def app():
    app = Flask(__name__)
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


def test_require_feature_flag_blocks_without_query(client):
    response = client.get("/gated")
    assert response.status_code == 404


def test_require_feature_flag_allows_with_query(client):
    response = client.get("/gated?foo=true")
    assert response.status_code == 200
    assert b"allowed" in response.data

import pytest
from flask import Flask
from flask.testing import FlaskClient

from eel_hole.feature_variants import FeatureVariants, get_variant


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.config["TESTING"] = True
    app.config["FEATURE_VARIANTS"] = {
        "foo": FeatureVariants(default="default", variants={"a", "b", "default"}),
        "bar": FeatureVariants(default="default", variants={"A", "B", "default"}),
    }

    @app.route("/test_variant/<feature_name>")
    def test_variant(feature_name):
        return get_variant(feature_name)

    return app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_get_variant_from_query_string(client: FlaskClient):
    response = client.get("/test_variant/foo?variants=foo:a")
    assert response.text == "a"


def test_get_variants_from_query_string(client: FlaskClient):
    response = client.get("/test_variant/foo?variants=foo:a,bar:B")
    assert response.text == "a"
    response = client.get("/test_variant/bar?variants=foo:a,bar:B")
    assert response.text == "B"


def test_get_variant_from_config(client: FlaskClient):
    response = client.get("/test_variant/foo")
    assert response.text == "default"


def test_get_variant_no_feature_found(client: FlaskClient):
    response = client.get("/test_variant/baz")
    assert response.status_code == 404

    response = client.get("/test_variant/baz?variants=baz:default")
    assert response.status_code == 404


def test_get_variant_no_variant_found(client: FlaskClient):
    response = client.get("/test_variant/foo?variants=foo:invalid")
    assert response.status_code == 404


def test_get_variant_from_query_string_persists_in_session(app: Flask):
    first_client = app.test_client()
    response = first_client.get("/test_variant/foo?variants=foo:a")
    assert response.text == "a"

    response = first_client.get("/test_variant/foo")
    assert response.text == "a"

    # second client doesn't know about first client's variant
    second_client = app.test_client()
    response = second_client.get("/test_variant/foo")
    assert response.text == "default"

    response = second_client.get("/test_variant/foo?variants=foo:b")
    assert response.text == "b"

    response = second_client.get("/test_variant/foo")
    assert response.text == "b"

    response = second_client.get("/test_variant/foo?variants=foo:a")
    assert response.text == "a"

    response = second_client.get("/test_variant/foo")
    assert response.text == "a"

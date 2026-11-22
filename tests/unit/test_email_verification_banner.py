from unittest.mock import Mock

import pytest
from flask import Flask
from flask.testing import FlaskClient

import eel_hole
from eel_hole.models import User, db


@pytest.fixture
def app(monkeypatch) -> Flask:
    """Stub out the side-effecting bits of real app setup for unit test.

    - hooking up to auth0
    - connecting to postgres
    - accessing search index
    - building autocomplete index
    - loading dashboards

    Also, add a fake user so we have someone to be logged in as while we look
    at the banner state.
    """
    monkeypatch.setenv("PUDL_VIEWER_SECRET_KEY", "test-secret")
    monkeypatch.setattr(eel_hole, "__init_auth0", lambda _app: Mock())

    def init_test_db(_db, app: Flask):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        _db.init_app(app)

    monkeypatch.setattr(eel_hole, "__init_db", init_test_db)
    monkeypatch.setattr(
        eel_hole, "build_or_load_search_index", lambda _dir: ([], Mock())
    )
    monkeypatch.setattr(
        eel_hole, "build_autocomplete_name_index", lambda _resources: {}
    )
    monkeypatch.setattr(eel_hole, "load_dashboards_config", lambda _path: [])

    app = eel_hole.create_app()
    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()
        db.session.add(
            User(
                auth0_id="auth0|user-123",
                email="unit-test@catalyst.coop",
                username="user",
                accepted_privacy_policy=True,
                email_verified=False,
            )
        )
        db.session.commit()

    return app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


@pytest.fixture
def management_client(mocker):
    client = mocker.Mock()
    mocker.patch.object(
        eel_hole,
        "get_auth0_management_client",
        return_value=client,
    )
    return client


def test_verify_email_shows_confirmation_after_success(
    client: FlaskClient, management_client
):
    management_client.request_verification_email.return_value = Mock(
        ok=True,
        status_code=200,
    )

    response = client.post("/verify-email")

    assert response.status_code == 200
    assert "We've requested a verification email. Check your inbox" in response.text
    assert "refresh status" in response.text


def test_verify_email_shows_error_after_failure(client: FlaskClient, management_client):
    management_client.request_verification_email.return_value = Mock(
        ok=False,
        status_code=502,
    )

    response = client.post("/verify-email")

    # we swallow the error code and spit out 200 instead so HTMX knows to swap in the "oops" text.
    assert response.status_code == 200
    assert "Oops! An error occurred." in response.text
    assert "hello@catalyst.coop" in response.text

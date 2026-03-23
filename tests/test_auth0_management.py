from unittest.mock import call

import pytest

from eel_hole.auth0_management import Auth0ManagementAPIClient


@pytest.fixture
def client(mocker):
    mocker.patch.object(
        Auth0ManagementAPIClient,
        "_get_access_token",
        return_value="fresh-token",
    )
    return Auth0ManagementAPIClient(
        domain="example.auth0.com",
        client_id="client-id",
        client_secret="client-secret",
    )


def test_request_verification_email_reuses_cached_token(mocker, client):
    ok_response = mocker.Mock(status_code=200, content=b"")
    post_mock = mocker.patch.object(
        client,
        "_post_verification_email",
        return_value=ok_response,
    )

    client.request_verification_email("auth0|user-123")
    client.request_verification_email("auth0|user-123")

    assert client._cached_access_token == "fresh-token"
    post_mock.assert_has_calls(
        [
            call(auth0_user_id="auth0|user-123", access_token="fresh-token"),
            call(auth0_user_id="auth0|user-123", access_token="fresh-token"),
        ]
    )


def test_request_verification_email_refreshes_token_after_401(mocker, client):
    client._cached_access_token = "expired-token"
    unauthorized_response = mocker.Mock(status_code=401, content=b"")
    ok_response = mocker.Mock(status_code=200, content=b"")
    post_mock = mocker.patch.object(
        client,
        "_post_verification_email",
        side_effect=[unauthorized_response, ok_response],
    )

    client.request_verification_email("auth0|user-123")

    assert client._cached_access_token == "fresh-token"
    post_mock.assert_has_calls(
        [
            call(auth0_user_id="auth0|user-123", access_token="expired-token"),
            call(auth0_user_id="auth0|user-123", access_token="fresh-token"),
        ]
    )

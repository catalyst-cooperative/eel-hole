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
    request_mock = mocker.patch.object(
        client,
        "_make_authenticated_request",
        return_value=ok_response,
    )

    client.request_verification_email("auth0|user-123")
    client.request_verification_email("auth0|user-123")

    assert client._cached_access_token == "fresh-token"
    request_mock.assert_has_calls(
        [
            call(
                http_method="post",
                endpoint="jobs/verification-email",
                json={"user_id": "auth0|user-123"},
            ),
            call(
                http_method="post",
                endpoint="jobs/verification-email",
                json={"user_id": "auth0|user-123"},
            ),
        ]
    )


def test_get_user_calls_authenticated_request(mocker, client):
    ok_response = mocker.Mock(status_code=200, content=b"")
    request_mock = mocker.patch.object(
        client,
        "_make_authenticated_request",
        return_value=ok_response,
    )

    response = client.get_user("auth0|user-123")

    assert response is ok_response
    request_mock.assert_called_once_with(
        http_method="get",
        endpoint="users/auth0|user-123",
    )

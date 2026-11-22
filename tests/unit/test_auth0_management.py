import pytest

from eel_hole.auth0_management import Auth0ManagementAPIClient


def assert_email_verification(request_call, *, token: str, user_id: str) -> None:
    """Only write down the things that are relevant to behavior under test."""
    url = "https://example.auth0.com/api/v2/jobs/verification-email"
    json = {"user_id": user_id}
    args, kwargs = request_call
    assert args == ("post", url)
    assert kwargs["headers"] == {"authorization": f"Bearer {token}"}
    assert kwargs["json"] == json


@pytest.fixture
def client(mocker):
    token_counter = 0

    def get_access_token() -> str:
        nonlocal token_counter
        access_token = f"token-{token_counter}"
        token_counter += 1
        return access_token

    mocker.patch.object(
        Auth0ManagementAPIClient,
        "_get_access_token",
        side_effect=get_access_token,
    )
    return Auth0ManagementAPIClient(
        domain="example.auth0.com",
        client_id="client-id",
        client_secret="client-secret",
    )


def test_request_verification_email_reuses_cached_token(mocker, client):
    ok_response = mocker.Mock(status_code=200, content=b"")
    request_mock = mocker.patch.object(
        client.http_session,
        "request",
        return_value=ok_response,
    )

    user_id = "auth0|user-123"
    client.request_verification_email(user_id)
    client.request_verification_email(user_id)

    assert request_mock.call_count == 2
    for request_call in request_mock.call_args_list:
        assert_email_verification(request_call, token="token-0", user_id=user_id)


def test_request_verification_email_refreshes_expired_token(mocker, client):
    invalid_token_response = mocker.Mock(status_code=401, content=b"")
    ok_response = mocker.Mock(status_code=200, content=b"")
    request_mock = mocker.patch.object(
        client.http_session,
        "request",
        side_effect=[invalid_token_response, ok_response, ok_response],
    )

    user_id = "auth0|user-123"

    client.request_verification_email(user_id)
    client.request_verification_email(user_id)

    assert request_mock.call_count == 3
    expired, fresh, cached = request_mock.call_args_list
    assert_email_verification(expired, token="token-0", user_id=user_id)
    assert_email_verification(fresh, token="token-1", user_id=user_id)
    assert_email_verification(cached, token="token-1", user_id=user_id)


def test_get_user_calls_authenticated_request(mocker, client):
    ok_response = mocker.Mock(status_code=200, content=b"")
    request_mock = mocker.patch.object(
        client.http_session,
        "request",
        return_value=ok_response,
    )

    user_id = "auth0|user-123"
    response = client.get_user(user_id)

    assert response is ok_response
    args, kwargs = request_mock.call_args
    assert ("get", f"https://example.auth0.com/api/v2/users/{user_id}") == args
    assert kwargs["headers"]["authorization"] == "Bearer token-0"

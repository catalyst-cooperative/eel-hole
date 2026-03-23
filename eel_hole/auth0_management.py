"""Helpers for calling the Auth0 Management API."""

import requests


class Auth0ManagementAPIClient:
    """Talk to Auth0 Management API.

    Needs the client ID and client secret from a machine-to-machine application
    from the Auth0 dashboard.

    NOTE(2026-03-23): Currently only sends email verification emails.
    """

    def __init__(
        self,
        domain: str,
        client_id: str,
        client_secret: str,
    ):
        self.domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.http_session = requests.Session()
        self._cached_access_token = self._get_access_token()

    def request_verification_email(self, auth0_user_id: str) -> requests.Response:
        """Ask Auth0 to send a new verification email to a logged-in user."""
        return self._make_authenticated_request(
            http_method="post",
            endpoint="jobs/verification-email",
            json={"user_id": auth0_user_id},
        )

    def get_user(self, auth0_user_id: str) -> requests.Response:
        """Get one Auth0 user profile by Auth0 user ID."""
        return self._make_authenticated_request(
            http_method="get",
            endpoint=f"users/{auth0_user_id}",
        )

    def _get_access_token(self) -> str:
        """Request a fresh Auth0 Management API token."""
        token_response = self.http_session.post(
            f"https://{self.domain}/oauth/token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "audience": f"https://{self.domain}/api/v2/",
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        return access_token

    def _make_authenticated_request(
        self,
        http_method: str,
        endpoint: str,
        **kwargs,
    ) -> requests.Response:
        """Make one authenticated Auth0 Management API request.

        We optimistically try the cached token first, then refresh and retry
        once if Auth0 responds with 401.
        """
        response = self.http_session.request(
            http_method,
            f"https://{self.domain}/api/v2/{endpoint}",
            headers={"authorization": f"Bearer {self._cached_access_token}"},
            timeout=10,
            **kwargs,
        )

        if response.status_code == 401:
            self._cached_access_token = self._get_access_token()
            response = self.http_session.request(
                http_method,
                f"https://{self.domain}/api/v2/{endpoint}",
                headers={"authorization": f"Bearer {self._cached_access_token}"},
                timeout=10,
                **kwargs,
            )

        return response


_auth0_management_client: "Auth0ManagementAPIClient | None" = None


def get_auth0_management_client(
    *,
    domain: str | None,
    client_id: str | None,
    client_secret: str | None,
) -> Auth0ManagementAPIClient:
    """Return shared Auth0 management API client.

    We only want one of these cached tokens floating around in this process.
    """
    global _auth0_management_client
    if _auth0_management_client is None:
        _auth0_management_client = Auth0ManagementAPIClient(
            domain=domain,
            client_id=client_id,
            client_secret=client_secret,
        )
    return _auth0_management_client

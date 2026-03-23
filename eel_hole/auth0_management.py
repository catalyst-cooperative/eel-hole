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
        """Ask Auth0 to send a new verification email to a logged-in user.

        If we get a 401, get a new token and try again.
        """
        token = self._cached_access_token
        response = self._post_verification_email(
            auth0_user_id=auth0_user_id,
            access_token=token,
        )

        if response.status_code == 401:
            token = self._get_access_token()
            self._cached_access_token = token
            response = self._post_verification_email(
                auth0_user_id=auth0_user_id,
                access_token=token,
            )

        return response

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

    def _post_verification_email(
        self,
        auth0_user_id: str,
        access_token: str,
    ) -> requests.Response:
        """POST the verification-email job request."""
        return self.http_session.post(
            f"https://{self.domain}/api/v2/jobs/verification-email",
            headers={"authorization": f"Bearer {access_token}"},
            json={"user_id": auth0_user_id},
            timeout=10,
        )


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

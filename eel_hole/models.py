"""DB model definitions."""

from flask_login import UserMixin

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import false

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """It's the user.

    The auth0_id is a unique ID that comes from auth0. This lets us figure out
    if the user's been created before, and also lets us avoid getting weird
    duplicate-key errors if e.g. email is re-used.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    auth0_id: Mapped[str] = mapped_column(unique=True)
    username: Mapped[str]
    email: Mapped[str]
    accepted_privacy_policy: Mapped[bool] = mapped_column(server_default=false())
    do_individual_outreach: Mapped[bool] = mapped_column(server_default=false())
    send_newsletter: Mapped[bool] = mapped_column(server_default=false())
    email_verified: Mapped[bool] = mapped_column(server_default=false())

    def get_domain(self) -> str:
        return self.email.partition("@")[-1]

    def should_verify_email(self) -> bool:
        """Should we nag this person about verifying their email?

        Auth0 connects to Google and Microsoft OAuth providers ("google-oauth2",
        "windowslive") , which automatically have verified emails. So Auth0 will 400 if
        you try to get them to send a verification email to these guys.

        However, we *do* want to know if a user used Auth0's native email auth
        (i.e. the "auth0" provider) so we can show them the "please verify your email"
        banner.
        """
        return self.auth0_id.lower().startswith("auth0|") and not self.email_verified

    @staticmethod
    def get(user_id):
        return User.query.get(int(user_id))

    @staticmethod
    def from_userinfo(userinfo):
        """Build our User object from Auth0's profile payload."""
        return User(
            auth0_id=userinfo["sub"],
            email=userinfo["email"],
            username=userinfo.get(
                "preferred_username", userinfo["email"].split("@")[0]
            ),
            email_verified=userinfo.get("email_verified", False),
        )

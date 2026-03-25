from playwright.sync_api import Page, expect
from sqlalchemy import text


def test_email_verification_banner_only_visible_when_unverified(
    page: Page, integration_test_db
):
    # integration test user *starts* verified by default (for improved
    # development experience), so we expect it to not show the banner until we
    # un-verify it.

    page.goto("http://localhost:8080/login")
    expect(page).to_have_url("http://localhost:8080/search")
    banner = page.locator("#verify-email-notification")
    expect(banner).to_have_count(0)

    with integration_test_db.connect() as conn:
        conn.execute(
            text('UPDATE "user" SET email_verified = false WHERE email = :email'),
            {"email": "integration_test@catalyst.coop"},
        )
        conn.commit()

    page.reload()
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("integration_test@catalyst.coop")


def test_email_verification_banner_only_visible_when_id_starts_with_auth0(
    page: Page, integration_test_db
):
    # integration test user's auth0 ID starts with `auth0|`, which indicates it's using auth0's email-based auth.
    # we should not show the banner if the user ID starts with, e.g., `google-oauth2|`

    page.goto("http://localhost:8080/login")
    expect(page).to_have_url("http://localhost:8080/search")
    with integration_test_db.connect() as conn:
        conn.execute(
            text('UPDATE "user" SET email_verified = false WHERE email = :email'),
            {"email": "integration_test@catalyst.coop"},
        )
        conn.commit()
    page.reload()
    expect(page).to_have_url("http://localhost:8080/search")
    banner = page.locator("#verify-email-notification")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("integration_test@catalyst.coop")

    page.reload()
    with integration_test_db.connect() as conn:
        conn.execute(
            text('UPDATE "user" SET auth0_id = :auth0_id WHERE email = :email'),
            {
                "auth0_id": "google-oauth2|integration_test@catalyst.coop",
                "email": "integration_test@catalyst.coop",
            },
        )
        conn.commit()
    page.reload()
    expect(banner).to_have_count(0)

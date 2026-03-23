from playwright.sync_api import Page, expect
from sqlalchemy import text


def test_email_verification_banner_disappears_after_verification(
    page: Page, integration_test_db
):
    """Banner shows for unverified users and disappears once verification is synced."""
    page.goto("http://localhost:8080/search")
    page.get_by_text("Log in or sign up to preview / export as CSV").first.click()
    expect(page).to_have_url("http://localhost:8080/search")

    banner = page.locator("#verify-email-notification")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("integration_test@catalyst.coop")

    with integration_test_db.connect() as conn:
        conn.execute(
            text('UPDATE "user" SET email_verified = true WHERE email = :email'),
            {"email": "integration_test@catalyst.coop"},
        )
        conn.commit()

    page.reload()

    expect(banner).to_have_count(0)

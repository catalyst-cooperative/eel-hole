import os

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import create_engine, text


@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_user():
    """Clean up integration test user before and after each test using direct SQL."""

    def delete_test_user():
        """Delete the test user directly via SQLAlchemy Core."""
        username = os.getenv("PUDL_VIEWER_DB_USERNAME", "pudl_viewer")
        password = os.getenv("PUDL_VIEWER_DB_PASSWORD", "pudl_viewer")
        database = os.getenv("PUDL_VIEWER_DB_NAME", "pudl_viewer")
        port = os.getenv("PUDL_VIEWER_DB_PORT", "5432")

        # Use localhost directly since we're connecting from the host machine
        db_uri = f"postgresql://{username}:{password}@localhost:{port}/{database}"
        engine = create_engine(db_uri)

        with engine.connect() as conn:
            conn.execute(
                text('DELETE FROM "user" WHERE email = :email'),
                {"email": "integration_test@catalyst.coop"},
            )
            conn.commit()

    delete_test_user()
    yield
    delete_test_user()


def test_login_logout_flow(page: Page):
    """Test the complete login/logout flow and UI state changes."""
    # Start logged out at /search
    page.goto("http://localhost:8080/search")

    # Verify we see "Login or sign up" buttons, not "Preview / export as CSV"
    expect(
        page.get_by_text("Log in or sign up to preview / export as CSV").first
    ).to_be_visible()
    expect(
        page.get_by_role("button").filter(
            has_text="Preview / export as CSV", has_not_text="Log in"
        )
    ).to_have_count(0)

    # Should redirect back to /search after login
    page.get_by_text("Log in or sign up to preview / export as CSV").first.click()
    expect(page).to_have_url("http://localhost:8080/search")

    # Now we should see "Preview / export as CSV" buttons
    expect(
        page.get_by_role("button")
        .filter(has_text="Preview / export as CSV", has_not_text="Log in")
        .first
    ).to_be_visible()
    expect(
        page.get_by_text("Log in or sign up to preview / export as CSV")
    ).to_have_count(0)

    # Click logout (redirects to home which then redirects to search)
    page.get_by_text("Log out of integration_test").click()
    page.wait_for_url("http://localhost:8080/search")

    # Buttons should be back to initial logged-out state
    expect(
        page.get_by_text("Log in or sign up to preview / export as CSV").first
    ).to_be_visible()
    expect(page.get_by_role("button", name="Preview / export as CSV")).to_have_count(0)

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_user():
    """Clean up integration test user before and after each test."""
    import os
    from eel_hole.models import db, User
    from eel_hole import create_app

    # Override DB host to use localhost instead of docker service name
    original_db_host = os.environ.get('PUDL_VIEWER_DB_HOST')
    os.environ['PUDL_VIEWER_DB_HOST'] = 'localhost'

    try:
        app = create_app()
        with app.app_context():
            # Clean up before test
            user = User.query.filter_by(email='integration_test@catalyst.coop').first()
            if user:
                db.session.delete(user)
                db.session.commit()

        yield

        with app.app_context():
            # Clean up after test
            user = User.query.filter_by(email='integration_test@catalyst.coop').first()
            if user:
                db.session.delete(user)
                db.session.commit()
    finally:
        # Restore original DB host
        if original_db_host is not None:
            os.environ['PUDL_VIEWER_DB_HOST'] = original_db_host
        elif 'PUDL_VIEWER_DB_HOST' in os.environ:
            del os.environ['PUDL_VIEWER_DB_HOST']


def test_login_logout_flow(page: Page):
    """Test the complete login/logout flow and UI state changes."""
    # Start logged out at /search
    page.goto("http://localhost:8080/search")

    # Verify we see "Login or sign up" buttons, not "Preview / export as CSV"
    expect(page.get_by_text("Log in or sign up to preview / export as CSV").first).to_be_visible()
    expect(page.get_by_role("button", name="Preview / export as CSV")).to_have_count(0)

    # Click login button
    page.get_by_text("Log in or sign up to preview / export as CSV").first.click()

    # Should redirect back to /search after login
    expect(page).to_have_url("http://localhost:8080/search")

    # Now we should see "Preview / export as CSV" buttons
    expect(page.get_by_role("button", name="Preview / export as CSV").first).to_be_visible()
    expect(page.get_by_text("Log in or sign up to preview / export as CSV")).to_have_count(0)

    # Verify navbar shows logout with username
    expect(page.get_by_text("Log out of integration_test")).to_be_visible()

    # Click logout (redirects to home which then redirects to search)
    page.get_by_text("Log out of integration_test").click()

    # Wait for redirect to complete (home redirects to search)
    page.wait_for_url("http://localhost:8080/search")

    # Buttons should be back to initial logged-out state
    expect(page.get_by_text("Log in or sign up to preview / export as CSV").first).to_be_visible()
    expect(page.get_by_role("button", name="Preview / export as CSV")).to_have_count(0)

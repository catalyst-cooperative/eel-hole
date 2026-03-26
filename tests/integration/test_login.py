from playwright.sync_api import Page, expect


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

    # Should redirect back to / after login
    page.get_by_text("Log in or sign up to preview / export as CSV").first.click()
    expect(page).to_have_url("http://localhost:8080/search")

    # should see preview buttons, but no login buttons
    expect(
        page.get_by_text("Preview / export as CSV").filter(has_not_text="Log in").first
    ).to_be_visible()
    expect(
        page.get_by_text("Log in or sign up to preview / export as CSV")
    ).to_have_count(0)

    # Click logout (redirects to home which then redirects to search)
    page.get_by_text("Log out of integration_test").click()
    page.wait_for_url("http://localhost:8080/")

    # We should see the login button again
    login_buttons = page.get_by_role("link", name="Log in or sign up")
    expect(login_buttons).to_have_count(1)
    expect(login_buttons.first).to_be_visible()

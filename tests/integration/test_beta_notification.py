from playwright.sync_api import Page, expect


def test_notification_banner_dismiss(page: Page):
    """Notification banner is visible and can be dismissed by clicking delete button."""
    page.goto("http://localhost:8080/search")

    notification = page.locator("#beta-notification")
    expect(notification).to_be_visible()

    delete_button = notification.locator("#beta-dismiss")
    delete_button.click()

    expect(notification).not_to_be_visible()


def test_notification_banner_persistence(page: Page):
    """Notification banner dismiss state persists across page loads."""
    page.goto("http://localhost:8080/search")

    notification = page.locator("#beta-notification")
    expect(notification).to_be_visible()

    # Dismiss the notification
    delete_button = notification.locator("#beta-dismiss")
    delete_button.click()
    expect(notification).not_to_be_visible()

    # Navigate to another page
    page.goto("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")
    expect(notification).not_to_be_visible()

    # Navigate back to search
    page.goto("http://localhost:8080/search")
    expect(notification).not_to_be_visible()

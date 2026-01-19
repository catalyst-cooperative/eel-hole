from playwright.sync_api import Page, expect


def test_notification_banner_dismiss(page: Page):
    """Notification banner is visible and can be dismissed by clicking delete button."""
    page.goto("http://localhost:8080/search")

    notification = page.locator(".notification")
    expect(notification).to_be_visible()

    delete_button = notification.locator(".delete")
    delete_button.click()

    expect(notification).not_to_be_visible()

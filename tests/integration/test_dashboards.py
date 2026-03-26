from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from eel_hole.dashboards_config import DashboardConfig, load_dashboards_config


@pytest.fixture(scope="module")
def configured_dashboards() -> list[DashboardConfig]:
    dashboards = load_dashboards_config(Path("eel_hole/dashboards.yaml"))
    assert dashboards, (
        "Need at least one configured dashboard for integration coverage."
    )
    return dashboards


def test_dashboards_gallery_reflects_config(
    page: Page, configured_dashboards: list[DashboardConfig]
):
    page.goto("http://localhost:8080/dashboards")

    for idx, dashboard in enumerate(configured_dashboards):
        dashboard_card = page.locator(".card").filter(has_text=dashboard.title).first
        title_link = dashboard_card.get_by_role("link", name=dashboard.title)
        screenshot = dashboard_card.get_by_role(
            "img", name=dashboard.thumbnail_alt_text
        )
        screenshot_link = dashboard_card.locator(".card-image a")

        expect(dashboard_card).to_be_visible()
        expect(title_link).to_have_attribute("href", f"/dashboards/{dashboard.slug}/")
        expect(screenshot_link).to_have_attribute(
            "href", f"/dashboards/{dashboard.slug}/"
        )
        expect(screenshot).to_be_visible()
        expect(screenshot).to_have_attribute("src", dashboard.thumbnail_path)
        expect(page.get_by_text(dashboard.description)).to_be_visible()


def test_clicking_dashboard_link_loads_iframe(
    page: Page, configured_dashboards: list[DashboardConfig]
):
    dashboard = configured_dashboards[0]

    page.goto("http://localhost:8080/dashboards")

    page.get_by_role("link", name=dashboard.title).first.click()
    page.wait_for_url(f"http://localhost:8080/dashboards/{dashboard.slug}/")

    iframe = page.locator("iframe")
    expect(iframe).to_have_count(1)
    expect(iframe).to_have_attribute("src", dashboard.url)


def test_direct_dashboard_url_loads_iframe(
    page: Page, configured_dashboards: list[DashboardConfig]
):
    dashboard = configured_dashboards[0]

    response = page.goto(f"http://localhost:8080/dashboards/{dashboard.slug}/")
    assert response is not None
    assert response.status == 200

    iframe = page.locator("iframe")
    expect(iframe).to_have_count(1)
    expect(iframe).to_have_attribute("src", dashboard.url)


def test_dashboard_invalid_slug_returns_404(page: Page):
    response = page.request.get("http://localhost:8080/dashboards/not-a-real-slug/")
    assert response.status == 404

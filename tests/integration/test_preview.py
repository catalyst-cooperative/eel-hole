import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


def test_preview_page(page: Page):
    """Test that the preview page shows the data table immediately with only the requested table's metadata."""
    page.goto("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")

    # Verify the page has a header with the table name
    header = page.get_by_test_id("metadata-table-name")
    expect(header).to_be_visible()
    expect(header).to_contain_text("core_pudl__codes_datasources")

    # Verify there is no search bar on the preview page
    search_bar = page.locator("input[type='search']")
    expect(search_bar).not_to_be_visible()

    # Data table should be visible immediately (no need to click preview button)
    data_table = page.locator("#data-table")
    expect(data_table).to_be_visible()

    # Verify the data table contains expected data
    page.locator("#data-table").get_by_text("epacems").wait_for(state="visible")

    # Verify the sidebar metadata only contains the core_pudl__codes_datasources table
    table_metadata = page.get_by_test_id("core_pudl__codes_datasources")
    expect(table_metadata).to_be_visible()
    expect(table_metadata).to_contain_text("Primary key")

    # Verify only one table is shown in the sidebar (not multiple like in search view)
    expect(page.locator("#sidebar > *")).to_have_count(1)


def test_preview_loading_indicator(page: Page):
    """The AG Grid loading overlay should be visible on initial data load, so we look for it
    immediately after page load - in theory it's possible to finish all the initialization
    before we check, but unlikely."""
    page.goto("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")

    loading_overlay = page.locator(".ag-overlay-loading-center")
    expect(loading_overlay).to_be_visible()

    page.locator("#data-table").get_by_text("epacems").wait_for(state="visible")
    expect(loading_overlay).not_to_be_visible()

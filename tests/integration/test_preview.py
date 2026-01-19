from playwright.sync_api import Page, expect


def test_preview_page(page: Page):
    """We should show the data table immediately, with its metadata."""
    page.goto("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")

    header = page.get_by_test_id("metadata-table-name")
    expect(header).to_be_visible()
    expect(header).to_contain_text("core_pudl__codes_datasources")

    # should be no search bar
    search_bar = page.locator("input[type='search']")
    expect(search_bar).not_to_be_visible()

    # table should be visible
    data_table = page.locator("#data-table")
    expect(data_table).to_be_visible()

    # data should exist
    page.locator("#data-table").get_by_text("epacems").wait_for(state="visible")

    # only this one table's metadata
    table_metadata = page.get_by_test_id("core_pudl__codes_datasources")
    expect(table_metadata).to_be_visible()
    expect(table_metadata).to_contain_text("Primary key")
    expect(page.locator("#sidebar > *")).to_have_count(1)


def test_preview_loading_indicator(page: Page):
    """The AG Grid loading overlay should be visible on initial data load.

    We look for it immediately after page load - in theory it's possible to
    finish all the initialization before we check, but unlikely."""

    page.goto("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")

    loading_overlay = page.locator(".ag-overlay-loading-center")
    expect(loading_overlay).to_be_visible()

    page.locator("#data-table").get_by_text("epacems").wait_for(state="visible")
    expect(loading_overlay).not_to_be_visible()


def test_preview_narrow_viewport(page: Page):
    """The data table should remain visible at narrow viewports.

    At narrow viewports (<=768px), Bulma stacks columns vertically instead of
    side-by-side. The table should still be visible with adequate height."""
    iphone_width = 375
    iphone_height = 667
    page.set_viewport_size({"width": iphone_width, "height": iphone_height})
    page.goto("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")

    ag_root = page.locator("#data-table .ag-root-wrapper")
    expect(ag_root).to_be_visible()
    ag_box = ag_root.bounding_box()
    assert ag_box is not None
    assert ag_box["height"] > iphone_height * 0.5

"""Integration tests for EQR partition preview functionality."""

import re

from playwright.sync_api import Page, expect


def test_preview_button_navigates_with_partition(page: Page):
    """Clicking Preview button should navigate to /pudl/<table_name>/<partition_name>."""
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto(
        "http://localhost:8080/search?q=name:core_ferceqr__quarterly_identity"
    )

    table_card = page.get_by_test_id("core_ferceqr__quarterly_identity")
    dropdown = table_card.locator("select#partition")

    _ = dropdown.select_option(index=0)
    selected_partition = dropdown.input_value()

    preview_button = table_card.get_by_role("link").and_(
        table_card.get_by_text("Preview")
    )
    preview_button.click()

    page.wait_for_url(
        f"/preview/pudl/core_ferceqr__quarterly_identity/{selected_partition}"
    )


def test_preview_page_shows_partitioned_data(page: Page):
    """Preview page for a partition should show the data table with actual data."""
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto(
        "http://localhost:8080/preview/pudl/core_ferceqr__quarterly_identity/2024q1"
    )

    # Metadata should be visible
    header = page.get_by_test_id("metadata-table-name")
    expect(header).to_be_visible()
    expect(header).to_contain_text("core_ferceqr__quarterly_identity")

    # Data table should be visible
    data_table = page.locator("#data-table")
    expect(data_table).to_be_visible()

    # Verify there's actual content in the grid
    page.locator("#data-table .ag-cell").first.wait_for(state="visible", timeout=30000)
    cells = page.locator("#data-table .ag-cell")
    cells_count = cells.count()
    assert cells_count > 0


def test_different_partitions_load_different_data(page: Page):
    """Different partition selections should load different data."""
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto(
        "http://localhost:8080/preview/pudl/core_ferceqr__quarterly_identity/2024q1"
    )

    page.locator("#data-table .ag-cell").first.wait_for(state="visible", timeout=30000)
    expect(
        page.locator("#data-table .ag-cell[col-id='year_quarter']").first
    ).to_have_text("2024q1")

    _ = page.goto(
        "http://localhost:8080/preview/pudl/core_ferceqr__quarterly_identity/2024q2"
    )

    page.locator("#data-table .ag-cell").first.wait_for(state="visible", timeout=30000)
    expect(
        page.locator("#data-table .ag-cell[col-id='year_quarter']").first
    ).to_have_text("2024q2")

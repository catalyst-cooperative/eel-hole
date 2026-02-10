"""Integration tests for EQR partition preview functionality."""

from playwright.sync_api import Page, expect


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


def test_preview_page_download_link_includes_partition(page: Page):
    """Download as parquet button on preview page should link to partition-specific file."""
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto(
        "http://localhost:8080/preview/pudl/core_ferceqr__quarterly_identity/2024q1"
    )

    download_button = page.locator("a").filter(
        has_text="Download full table as Parquet"
    )
    expect(download_button).to_be_visible()

    href = download_button.get_attribute("href")
    assert href.endswith("2024q1.parquet")


def test_return_to_search(page: Page):
    """Test that the return to search button works appropriately."""
    # Test return to search with no query
    _ = page.goto("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")
    page.get_by_text("Return to Search").click()
    page.wait_for_url("http://localhost:8080/search")

    _ = page.goto("http://localhost:8080/preview/pudl/core_ferceqr__quarterly_identity")
    page.get_by_text("Return to Search").click()
    page.wait_for_url("http://localhost:8080/search")

    # Test return to search with query
    _ = page.goto(
        "http://localhost:8080/preview/pudl/core_pudl__codes_datasources?return_q=query"
    )
    page.get_by_text("Return to Search").click()
    page.wait_for_url("http://localhost:8080/search?q=query")


def test_partitioned_resource_without_partition_shows_selector_page(page: Page):
    """Partitioned resource without partition shows selector UI with metadata, not data table."""
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto("http://localhost:8080/preview/pudl/core_ferceqr__quarterly_identity")

    expect(page.locator("select#partition")).to_be_visible()
    expect(page.locator("label[for='partition']")).to_contain_text(
        "Select a partition to preview or download"
    )
    expect(page.locator("#data-table")).not_to_be_visible()
    expect(page.locator("h2.title")).to_contain_text("core_ferceqr__quarterly_identity")

    expect(
        page.locator("[data-testid='core_ferceqr__quarterly_identity']")
    ).to_be_visible()
    expect(page.locator("summary").filter(has_text="Columns")).to_be_visible()
    expect(page.locator("[data-testid='column']").first).to_be_visible()


def test_partitioned_resource_trailing_slash_works(page: Page):
    """Trailing slash on partitioned resource URL should not 404."""
    _ = page.goto("http://localhost:8080/login")
    response = page.goto(
        "http://localhost:8080/preview/pudl/core_ferceqr__quarterly_identity/"
    )

    assert response.status == 200
    expect(page.locator("select#partition")).to_be_visible()

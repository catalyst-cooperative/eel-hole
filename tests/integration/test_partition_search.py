"""Integration tests for EQR partition search functionality."""

from playwright.sync_api import Page, expect


def test_eqr_tables_have_partition_dropdowns(page: Page):
    """Search for EQR tables should show 4 cards, each with a partition dropdown."""
    _ = page.goto("http://localhost:8080/search?q=name:core_ferceqr__")

    page.get_by_test_id("core_ferceqr__quarterly_identity").wait_for(
        state="visible", timeout=5000
    )

    # NOTE (2026-01-21): If we add more EQR tables for any reason this will fail but we should just update the test.
    eqr_tables = page.locator("#search-results > *")
    expect(eqr_tables).to_have_count(4)

    for i in range(4):
        card = eqr_tables.nth(i)
        dropdown = card.locator("select#partition")
        expect(dropdown).to_be_visible()
        expect(dropdown).to_have_attribute("id", "partition")
        expect(dropdown).to_have_value("")


def test_partition_dropdown_has_correct_options(page: Page):
    """Partition dropdown should contain the available partitions for each table."""
    _ = page.goto(
        "http://localhost:8080/search?q=name:core_ferceqr__quarterly_identity"
    )

    table_card = page.get_by_test_id("core_ferceqr__quarterly_identity")
    expect(table_card).to_be_visible(timeout=5000)

    dropdown = table_card.locator("select#partition")
    expect(dropdown).to_be_visible(timeout=5000)

    # NOTE (2026-01-21): EQR tables should have at least 49 partitions - that's 2013q1 through 2025q2
    options = dropdown.locator("option")
    options_count = options.count()
    assert options_count >= 49, (
        f"Expected partition dropdown to have at least 49 options, but found {options_count}"
    )

    first_option_text = options.first.text_content()
    assert first_option_text is not None and len(first_option_text.strip()) > 0


def test_changing_partition_does_not_navigate(page: Page):
    """Updating the partition dropdown should NOT trigger preview navigation.

    The dropdown change should update which partition will be previewed when the
    Preview button is clicked, but shouldn't navigate anywhere by itself.
    """
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto(
        "http://localhost:8080/search?q=name:core_ferceqr__quarterly_identity"
    )

    table_card = page.get_by_test_id("core_ferceqr__quarterly_identity")
    dropdown = table_card.locator("select#partition")

    initial_url = page.url

    selected_partition = dropdown.select_option(index=1, timeout=5000)

    page.wait_for_timeout(500)

    assert page.url == initial_url

    expect(page.locator("input[name='q']")).to_be_visible()

    preview_link = table_card.get_by_role("link", name="Preview")
    expect(preview_link).to_have_attribute(
        "href",
        f"/preview/pudl/core_ferceqr__quarterly_identity/{selected_partition[0]}?return_q=name:core_ferceqr__quarterly_identity",
    )


def test_partition_dropdown_has_label(page: Page):
    """Partitioned tables should have a descriptive label above the dropdown."""
    _ = page.goto(
        "http://localhost:8080/search?q=name:core_ferceqr__quarterly_identity"
    )

    table_card = page.get_by_test_id("core_ferceqr__quarterly_identity")
    expect(table_card).to_be_visible(timeout=5000)

    label = table_card.locator("label").filter(
        has_text="Select a partition to preview or download:"
    )
    expect(label).to_be_visible()


def test_buttons_disabled_until_partition_selected(page: Page):
    """For partitioned tables, preview/download buttons should be disabled until partition selected.

    We start from /search and then type in the query, because the button
    behavior was once funky in a way that only manifested when HTMX was doing a
    bunch of page updates.
    """
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("name:core_ferceqr__quarterly_identity")

    table_card = page.get_by_test_id("core_ferceqr__quarterly_identity")
    expect(table_card).to_be_visible(timeout=5000)

    preview_button = table_card.get_by_role("link").filter(has_text="Preview")
    download_button = table_card.get_by_role("link").filter(
        has_text="Download full table as Parquet"
    )

    # NOTE (2026-01-23): can't use expect().to_be_disabled() since these are
    # actually `a` tags - since they're really *links* that merely look like
    # buttons.
    expect(preview_button).to_have_attribute("disabled", "disabled")
    expect(download_button).to_have_attribute("disabled", "disabled")

    dropdown = table_card.locator("select#partition")
    selected_partition = dropdown.select_option(index=1)

    expect(preview_button).to_be_visible()
    expect(download_button).to_be_visible()

    preview_href = preview_button.get_attribute("href")
    download_href = download_button.get_attribute("href")

    assert (
        preview_href
        == f"/preview/pudl/core_ferceqr__quarterly_identity/{selected_partition[0]}"
    )
    assert download_href.endswith(f"{selected_partition[0]}.parquet")

    preview_button.click()
    page.wait_for_url(f"http://localhost:8080{preview_href}")

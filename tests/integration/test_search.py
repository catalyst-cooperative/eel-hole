import re
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, expect


def test_search_autocomplete_keyboard_select(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    first_option = autocomplete_menu.locator("button").first
    expect(first_option).to_have_text(
        'Search for "codes_datasource"',
    )
    expect(first_option).to_have_class(re.compile(r"is-selected"))
    second_option = autocomplete_menu.locator("button").nth(1)
    expect(second_option).to_contain_text("name: core_pudl__codes_datasources")
    expect(second_option.locator("strong")).to_have_count(1)

    search_input.press("ArrowDown")
    search_input.press("Enter")

    expect(page).to_have_url(
        "http://localhost:8080/search?q=name%3Acore_pudl__codes_datasources"
    )
    expect(page.get_by_test_id("core_pudl__codes_datasources")).to_be_visible()


def test_search_autocomplete_click_select(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    second_option = autocomplete_menu.locator("button").nth(1)
    second_option.click()

    expect(page).to_have_url(
        "http://localhost:8080/search?q=name%3Acore_pudl__codes_datasources"
    )
    expect(page.get_by_test_id("core_pudl__codes_datasources")).to_be_visible()


def test_search_autocomplete_keyboard_navigation_wraps_and_selects(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()

    first_option = autocomplete_menu.locator("button").first
    last_option = autocomplete_menu.locator("button").last
    expect(first_option).to_have_class(re.compile(r"is-selected"))

    # ArrowUp from first item should wrap to the last item.
    search_input.press("ArrowUp")
    expect(last_option).to_have_class(re.compile(r"is-selected"))

    # ArrowDown from last item should wrap to the first item.
    search_input.press("ArrowDown")
    expect(first_option).to_have_class(re.compile(r"is-selected"))

    # Move to the table suggestion and select it with Enter.
    search_input.press("ArrowDown")
    search_input.press("Enter")
    expect(search_input).to_have_value("name:core_pudl__codes_datasources")
    expect(autocomplete_menu).to_be_hidden()


def test_search_metadata(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("out eia860 yearly ownership")
    search_input.press("Enter")

    # figure out if the search has actually happened by looking to see if
    # something that *shouldn't* be in the results has disappeared
    core_table = page.get_by_test_id("core_eia923__monthly_boiler_fuel")
    core_table.wait_for(state="detached")
    max_num_search_results = 20
    num_results = page.locator("#search-results > *").count()
    assert num_results <= max_num_search_results

    ownership_table = page.get_by_test_id("out_eia860__yearly_ownership")
    expect(ownership_table).to_contain_text("Primary key")

    # check that metadata includes column descriptions
    ownership_columns = ownership_table.get_by_test_id("column")
    expect(ownership_columns).to_have_count(16)
    assert re.search(
        r"report_date\W+Date reported.", "".join(ownership_columns.all_text_contents())
    )


def test_search_for_ferc_table(page: Page):
    _ = page.goto(
        "http://localhost:8080/search?variants=search_packages:raw_ferc&q=package:ferc6_xbrl"
    )
    num_results = page.locator("#search-results > *").count()
    # there are more than 50 tables in ferc6, only 50 will show up
    assert num_results == 50
    expect(page.get_by_test_id("identification_001_duration")).to_contain_text(
        "001 - Schedule - Identification - duration"
    )
    expect(page.get_by_test_id("identification_001_duration")).to_contain_text(
        "ferc6_xbrl"
    )


def test_search_preview(page: Page):
    """Preview button now navigates to dedicated preview page via HTMX instead of showing overlay."""
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto("http://localhost:8080/search?q=name:core_pudl__codes_datasources")

    table_metadata = page.get_by_test_id("core_pudl__codes_datasources")
    preview_link = table_metadata.get_by_role("link").and_(
        table_metadata.get_by_text("Preview")
    )
    preview_link.click()

    page.wait_for_url(
        "http://localhost:8080/preview/pudl/core_pudl__codes_datasources?return_q=name:core_pudl__codes_datasources"
    )


def test_search_preview_back_button(page: Page):
    """We should preserve search results and query when using browser back button.

    We start from /search and then type in the query, because if we navigate
    *directly* to /search?q=foo the query is already populated server-side.
    """
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("name:core_pudl__codes_datasources")
    search_input.press("Enter")

    # Wait for HTMX to update URL and results (: gets URL encoded to %3A)
    page.wait_for_url(
        "http://localhost:8080/search?q=name%3Acore_pudl__codes_datasources"
    )
    table_metadata = page.get_by_test_id("core_pudl__codes_datasources")
    expect(table_metadata).to_be_visible()

    preview_link = table_metadata.get_by_role("link").and_(
        table_metadata.get_by_text("Preview")
    )
    preview_link.click()

    page.wait_for_url(
        "http://localhost:8080/preview/pudl/core_pudl__codes_datasources?return_q=name:core_pudl__codes_datasources"
    )

    page.evaluate("window.history.back()")
    page.wait_for_url(
        "http://localhost:8080/search?q=name%3Acore_pudl__codes_datasources"
    )
    # NOTE (2026-01-28): this reload is needed for the actual content to appear
    _ = page.reload()

    expect(table_metadata).to_be_visible()

    # Search query should be restored in the input field (via our JS, not server template)
    expect(search_input).to_have_value("name:core_pudl__codes_datasources")


def test_search_preview_ctrl_click_new_tab(page: Page):
    """Ctrl+click on preview link should open in new tab, not trigger HTMX."""
    _ = page.goto("http://localhost:8080/login")
    _ = page.goto("http://localhost:8080/search?q=name:core_pudl__codes_datasources")

    table_metadata = page.get_by_test_id("core_pudl__codes_datasources")
    preview_link = table_metadata.get_by_role("link").and_(
        table_metadata.get_by_text("Preview")
    )

    with page.context.expect_page() as new_page_info:
        preview_link.click(modifiers=["Control"])

    new_page = new_page_info.value
    new_page.wait_for_url(
        "http://localhost:8080/preview/pudl/core_pudl__codes_datasources?return_q=name:core_pudl__codes_datasources"
    )
    new_page.close()

    # Original page should still be on search
    expect(page).to_have_url(
        "http://localhost:8080/search?q=name:core_pudl__codes_datasources"
    )


def test_search_redirect_legacy_datasette_urls(page: Page):
    _ = page.goto("http://localhost:8080/pudl/core_pudl__codes_datasources")
    page.wait_for_url("http://localhost:8080/preview/pudl/core_pudl__codes_datasources")
    _ = page.goto("http://localhost:8080/pudl")
    page.wait_for_url("http://localhost:8080/search")
    _ = page.goto("http://localhost:8080/pudl/")
    page.wait_for_url("http://localhost:8080/search")


def test_search_preserves_variant_in_hx_requests(page: Page):
    _ = page.goto("http://localhost:8080/search?variants=search_method:title_boost")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("name:core_pudl__codes_datasources")

    page.wait_for_url(re.compile(r".*/search\?.*q="))
    params = parse_qs(urlparse(page.url).query)
    assert params.get("q") == ["name:core_pudl__codes_datasources"]
    assert params.get("variants") == ["search_method:title_boost"]

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


def test_search_metadata(page: Page):
    page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("out eia860 yearly ownership")

    core_table = page.get_by_test_id("core_eia923__monthly_boiler_fuel")
    core_table.wait_for(state="detached")
    num_results = page.locator("#search-results > *").count()
    assert num_results <= 20
    ownership_table = page.get_by_test_id("out_eia860__yearly_ownership")
    expect(ownership_table).to_contain_text("Primary key")


def test_search_for_ferc_table(page: Page):
    page.goto("http://localhost:8080/search?ferc_enabled=true")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("package:ferc1_xbrl")
    core_table = page.get_by_test_id("core_eia923__monthly_boiler_fuel")
    core_table.wait_for(state="detached")
    num_results = page.locator("#search-results > *").count()
    assert num_results <= 20
    expect(page.get_by_test_id("identification_001_duration")).to_contain_text(
        "001 - Schedule - Identification - duration"
    )
    expect(page.get_by_test_id("identification_001_duration")).to_contain_text(
        "ferc1_xbrl"
    )


def test_search_preview(page: Page):
    page.goto("http://localhost:8080/search?q=core pudl codes datasources tags:core")
    data_table = page.locator("#data-table")
    expect(data_table).to_be_hidden()
    table_metadata = page.get_by_test_id("core_pudl__codes_datasources")

    table_metadata.get_by_role("button").and_(
        table_metadata.get_by_text("Preview")
    ).click()
    page.locator("#data-table").get_by_text("epacems").wait_for(state="visible")

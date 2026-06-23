import re

from playwright.sync_api import Page, expect

from eel_hole.search import SEARCH_PACKAGES


def test_landing_page_shows_search_controls(page: Page):
    page.goto("http://localhost:8080/")

    expect(page.locator("#search-query-input")).to_be_visible()
    package_select = page.locator("#search-package-select")
    expect(package_select).to_be_visible()
    expect(package_select.locator("option")).to_have_text(SEARCH_PACKAGES)


def test_landing_page_search_autocomplete_suggestions(page: Page):
    page.goto("http://localhost:8080/")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    expect(autocomplete_menu.locator("a").first).to_have_text(
        'Search for "codes_datasource"',
    )
    second_option = autocomplete_menu.locator("a").nth(1)
    expect(second_option).to_contain_text("name: core_pudl__codes_datasources")
    expect(second_option.locator("strong")).to_have_text("codes_datasource")


def test_landing_page_search_navigates_to_search(page: Page):
    page.goto("http://localhost:8080/")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")
    search_input.press("Enter")

    expect(page).to_have_url(
        "http://localhost:8080/search?package=pudl&q=codes_datasource"
    )


def test_landing_page_search_autocomplete_selection_navigates_to_search(page: Page):
    page.goto("http://localhost:8080/")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    autocomplete_menu.locator("a").nth(1).click()

    expect(page).to_have_url(
        "http://localhost:8080/search?package=pudl&q=name%3Acore_pudl__codes_datasources"
    )


def test_finding_data_tabs_switch_content(page: Page):
    page.goto("http://localhost:8080/")

    by_data_source_tab = page.locator("#find-data .tabs a", has_text="By Data Source")
    by_topic_tab = page.locator("#find-data .tabs a", has_text="By Topic")
    most_popular_tab = page.locator("#find-data .tabs a", has_text="By Most Popular")

    expect(by_data_source_tab).to_be_visible()
    expect(by_topic_tab).to_be_visible()
    expect(most_popular_tab).to_be_visible()

    # "data source" is identifiable by EIA details section
    data_source_content = page.locator("#find-data summary").get_by_text(
        "Energy Information Administration"
    )
    # "topic" is identifiable by topics element
    topic_content = page.locator("#find-data #topics")
    # "most popular" is identified by popular element
    popular_content = page.locator("#find-data #popular")
    expect(data_source_content).to_be_visible()
    expect(topic_content).not_to_be_visible()
    expect(popular_content).not_to_be_visible()

    most_popular_tab.click()
    expect(popular_content).to_be_visible()
    expect(data_source_content).not_to_be_visible()
    expect(topic_content).not_to_be_visible()

    by_data_source_tab.click()
    expect(data_source_content).to_be_visible()
    expect(topic_content).not_to_be_visible()
    expect(popular_content).not_to_be_visible()

    by_topic_tab.click()
    expect(topic_content).to_be_visible()
    expect(data_source_content).not_to_be_visible()
    expect(popular_content).not_to_be_visible()


def test_finding_data_expand_and_collapse_all(page: Page):
    page.goto("http://localhost:8080/")

    expand_all_button = page.get_by_role("button", name="Expand All")
    collapse_all_button = page.get_by_role("button", name="Collapse All")
    all_details = page.locator("#find-data details")

    details_count = all_details.count()
    assert details_count > 0

    open_details = page.locator("#find-data details[open]")
    expand_all_button.click()
    expect(open_details).to_have_count(details_count)

    collapse_all_button.click()
    expect(open_details).to_have_count(0)


def test_table_of_contents_stays_visible_while_scrolling(page: Page):
    page.goto("http://localhost:8080/")

    # use first/last links to make sure the *whole* toc is visible
    toc_links = page.locator("#welcome-nav a[href^='#']")
    expect(toc_links.first).to_be_in_viewport()
    expect(toc_links.last).to_be_in_viewport()

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    expect(toc_links.first).to_be_in_viewport()
    expect(toc_links.last).to_be_in_viewport()

    page.evaluate("window.scrollTo(0, 0)")
    expect(toc_links.first).to_be_in_viewport()
    expect(toc_links.last).to_be_in_viewport()


def test_table_of_contents_links_scroll_to_sections(page: Page):
    page.goto("http://localhost:8080/")

    toc_links = page.locator("#welcome-nav a[href^='#']")
    assert toc_links.count() > 0

    for link in toc_links.all():
        href = link.get_attribute("href")
        assert href is not None
        target = href.removeprefix("#")
        assert target

        link.click()
        expect(page).to_have_url(re.compile(href))
        section = page.locator(href)
        expect(section).to_be_in_viewport()

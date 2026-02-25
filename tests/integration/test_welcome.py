import re

from playwright.sync_api import Page, expect


def test_finding_data_tabs_switch_content(page: Page):
    page.goto("http://localhost:8080/")

    by_data_source_tab = page.locator("#find-data .tabs a", has_text="By Data Source")
    most_popular_tab = page.locator("#find-data .tabs a", has_text="By Most Popular")

    expect(by_data_source_tab).to_be_visible()
    expect(most_popular_tab).to_be_visible()

    # "data source" is identifiable by EIA details section
    data_source_content = page.locator("#find-data summary").get_by_text(
        "Energy Information Administration"
    )
    # "most popular" is identified by list item w/ yearly generators table
    popular_content = page.locator("#find-data li").get_by_text(
        "out_eia__yearly_generators"
    )
    expect(data_source_content).to_be_visible()
    expect(popular_content).not_to_be_visible()

    most_popular_tab.click()
    expect(popular_content).to_be_visible()
    expect(data_source_content).not_to_be_visible()

    by_data_source_tab.click()
    expect(data_source_content).to_be_visible()
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
    page.wait_for_timeout(100)
    expect(toc_links.first).to_be_in_viewport()
    expect(toc_links.last).to_be_in_viewport()


def test_table_of_contents_links_scroll_to_sections(page: Page):
    page.goto("http://localhost:8080/")

    toc_links = page.locator("#welcome-nav a[href^='#']")
    links = toc_links.all()
    assert links

    for link in links:
        href = link.get_attribute("href")
        assert href is not None
        target = href.removeprefix("#")
        assert target

        link.click()
        expect(page).to_have_url(re.compile(rf".*#{target}$"))
        section = page.locator(f"#{target}")
        expect(section).to_be_in_viewport()

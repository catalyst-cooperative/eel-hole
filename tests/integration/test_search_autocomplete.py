from playwright.sync_api import Page, expect


def test_search_autocomplete_keyboard_select(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    first_option = autocomplete_menu.locator("a").first
    expect(first_option).to_have_text(
        'Search for "codes_datasource"',
    )
    second_option = autocomplete_menu.locator("a").nth(1)
    expect(second_option).to_contain_text("name: core_pudl__codes_datasources")
    expect(second_option.locator("strong")).to_have_text("codes_datasource")

    search_input.press("ArrowDown")
    search_input.press("Enter")

    expect(page).to_have_url(
        "http://localhost:8080/search?q=name%3Acore_pudl__codes_datasources"
    )


def test_search_autocomplete_click_select(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    second_option = autocomplete_menu.locator("a").nth(1)
    second_option.click()

    expect(page).to_have_url(
        "http://localhost:8080/search?q=name%3Acore_pudl__codes_datasources"
    )


def test_search_autocomplete_hides_when_query_is_cleared(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    search_input.fill("codes_datasource")

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    search_input.fill("")
    expect(autocomplete_menu).to_be_hidden()


def test_search_autocomplete_does_not_clear_input(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    typed_query = "codes_datasource"
    search_input.fill(typed_query)

    autocomplete_menu = page.locator("#search-autocomplete")
    expect(autocomplete_menu).to_be_visible()
    expect(search_input).to_have_value(typed_query)


def test_search_autocomplete_escape_close_and_keyboard_submit_selected(page: Page):
    _ = page.goto("http://localhost:8080/search")
    search_input = page.get_by_role("textbox").and_(
        page.get_by_placeholder("Search...")
    )
    autocomplete_menu = page.locator("#search-autocomplete")

    # Open autosuggest and verify options are present.
    search_input.fill("codes_datasource")
    expect(autocomplete_menu).to_be_visible()
    num_options = autocomplete_menu.locator("a").count()
    assert num_options >= 2

    # Escape should close the autosuggest menu.
    search_input.press("Escape")
    expect(autocomplete_menu).to_be_hidden()

    # Reopen and keyboard-select second item, then submit with Enter.
    search_input.fill("")
    search_input.fill("codes_datasource")

    # Wait for the first option is visible & selected before we try to hit
    # ArrowDown to select the second option - if we don't do this, the ArrowDown
    # gets swallowed.
    first_option = autocomplete_menu.locator("a").first
    expect(first_option).to_contain_class("is-selected")
    search_input.press("ArrowDown")
    second_option = autocomplete_menu.locator("a").nth(1)
    expect(second_option).to_contain_class("is-selected")
    search_input.press("Enter")

    expect(page).to_have_url(
        "http://localhost:8080/search?q=name%3Acore_pudl__codes_datasources"
    )

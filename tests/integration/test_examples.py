from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from eel_hole.examples_config import ExampleConfig, load_examples_config


@pytest.fixture(scope="module")
def configured_examples() -> list[ExampleConfig]:
    examples = load_examples_config(Path("eel_hole/examples.yaml"))
    assert examples, "Need at least one configured example for integration coverage."
    return examples


def test_examples_gallery_reflects_config(
    page: Page, configured_examples: list[ExampleConfig]
):
    page.goto("http://localhost:8080/secret-examples")

    open_links = page.get_by_role("link", name="Open example")

    expect(open_links).to_have_count(len(configured_examples))

    for idx, example in enumerate(configured_examples):
        # link goes to right place
        expect(open_links.nth(idx)).to_have_attribute(
            "href", f"/secret-examples/{example.slug}/"
        )
        # card shows title and description
        expect(
            page.locator(".card").filter(has_text=example.title).first
        ).to_be_visible()
        expect(page.get_by_text(example.description)).to_be_visible()


def test_clicking_gallery_link_loads_iframe(
    page: Page, configured_examples: list[ExampleConfig]
):
    example = configured_examples[0]

    page.goto("http://localhost:8080/secret-examples")

    page.locator(f"a[href='/secret-examples/{example.slug}/']").click()
    page.wait_for_url(f"http://localhost:8080/secret-examples/{example.slug}/")

    iframe = page.locator("iframe")
    expect(iframe).to_have_count(1)
    expect(iframe).to_have_attribute("src", example.url)


def test_direct_example_url_loads_iframe(
    page: Page, configured_examples: list[ExampleConfig]
):
    example = configured_examples[0]

    response = page.goto(f"http://localhost:8080/secret-examples/{example.slug}/")
    assert response is not None
    assert response.status == 200

    iframe = page.locator("iframe")
    expect(iframe).to_have_count(1)
    expect(iframe).to_have_attribute("src", example.url)


def test_examples_invalid_slug_returns_404(page: Page):
    response = page.request.get(
        "http://localhost:8080/secret-examples/not-a-real-slug/"
    )
    assert response.status == 404

from pathlib import Path

import pytest
import yaml
from playwright.sync_api import Page, expect


def _configured_examples() -> list[dict]:
    config = yaml.safe_load(Path("eel_hole/examples.yaml").read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        return []
    examples = config.get("examples", [])
    if not isinstance(examples, list):
        return []
    return [example for example in examples if isinstance(example, dict)]


def test_examples_gallery_matches_config(page: Page):
    examples = _configured_examples()

    _ = page.goto("http://localhost:8080/examples")

    open_links = page.get_by_role("link", name="Open example")

    if not examples:
        expect(
            page.get_by_text("No notebook examples are available yet.")
        ).to_be_visible()
        expect(open_links).to_have_count(0)
        return

    expect(open_links).to_have_count(len(examples))

    hrefs = open_links.evaluate_all("els => els.map((el) => el.getAttribute('href'))")
    expected_hrefs = [f"/examples/{example['slug']}/" for example in examples]
    assert hrefs == expected_hrefs

    for example in examples:
        expect(
            page.locator(".card").filter(has_text=example["title"]).first
        ).to_be_visible()
        description = example.get("description")
        if description:
            expect(page.get_by_text(description)).to_be_visible()


@pytest.mark.parametrize("slug", [e["slug"] for e in _configured_examples()])
def test_examples_gallery_links_work(page: Page, slug: str):
    _ = page.goto("http://localhost:8080/examples")

    page.locator(f"a[href='/examples/{slug}/']").click()
    page.wait_for_url(f"http://localhost:8080/examples/{slug}/")

    # marimo export currently sets <title> to the notebook slug.
    expect(page).to_have_title(slug)


def test_examples_invalid_slug_returns_404(page: Page):
    response = page.request.get("http://localhost:8080/examples/not-a-real-slug/")
    assert response.status == 404

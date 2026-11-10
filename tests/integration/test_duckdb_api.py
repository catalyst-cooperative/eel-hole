from playwright.sync_api import Page

DUCKDB_URL = "http://localhost:8080/api/duckdb"


def test_duckdb_api_requires_login(page: Page):
    """Logged-out requests should not get a query spec."""
    response = page.request.get(
        DUCKDB_URL,
        params={
            "name": "core_pudl__codes_datasources.parquet",
        },
    )
    assert response.status == 401


def test_duckdb_api_available_when_logged_in(page: Page):
    """Logged-in requests should get a query spec for the requested table."""
    page.goto("http://localhost:8080/login")

    response = page.request.get(
        DUCKDB_URL,
        params={
            "name": "core_pudl__codes_datasources.parquet",
        },
    )
    assert response.status == 200
    query = response.json()
    assert query["statement"] == (
        "SELECT * FROM core_pudl__codes_datasources.parquet"
        " WHERE true LIMIT 10000 OFFSET 0"
    )
    assert query["count_statement"] == (
        "SELECT COUNT(*) FROM core_pudl__codes_datasources.parquet WHERE true LIMIT 1"
    )

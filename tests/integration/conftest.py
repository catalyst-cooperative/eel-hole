import os

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function")
def integration_test_db():
    username = os.getenv("PUDL_VIEWER_DB_USERNAME", "pudl_viewer")
    password = os.getenv("PUDL_VIEWER_DB_PASSWORD", "pudl_viewer")
    database = os.getenv("PUDL_VIEWER_DB_NAME", "pudl_viewer")
    port = os.getenv("PUDL_VIEWER_DB_PORT", "5432")
    db_uri = f"postgresql://{username}:{password}@localhost:{port}/{database}"
    engine = create_engine(db_uri)

    yield engine

    engine.dispose()


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_user(integration_test_db):
    """Delete the integration test user before and after each test."""

    def delete_test_user():
        with integration_test_db.connect() as conn:
            conn.execute(
                text('DELETE FROM "user" WHERE email = :email'),
                {"email": "integration_test@catalyst.coop"},
            )
            conn.commit()

    delete_test_user()
    yield
    delete_test_user()

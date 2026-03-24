# Parquet Frontend-only prototype

## Installation

Install `uv` and `npm`.

Install the required packages:

```
npm install --include=dev
uv sync
uv pip install -e .
```

Build the JS/CSS:

```
npm run build
```

Set up pre-commit hooks:

```
uv run pre-commit install
```

In most cases, you don't need to actually log in locally.
For integration testing, you can set the `PUDL_VIEWER_INTEGRATION_TEST` environment variable to `true`.
This will automatically create a test user that bypasses Auth0 and has already accepted the privacy policy.

But if you're testing something related to the login flow, you will need to set that up:

1. Set up your auth0 environment variables (see below)
2. Set up the database:

```
docker compose up -d
docker compose exec eel_hole uv run flask db upgrade
```

## Running this thing locally

We have a docker compose file, but _make sure to build the JS/CSS first_:

```bash
$ npm run build
...
$ docker compose build && docker compose up
```

We've set up a bind-mount for the `eel-hole` directory, so changes to the Python
files and the `npm run build` outputs _should_ just show up in the container. If
the app detects changes to the .py files it will restart, and changes to the
template files and frontend files should work on refresh because they're being
read/served at request time.

The main thing you'd have to rebuild the Docker image for would be if you need
to rebuild the search index for whatever reason. It should take about a minute.

If you want to skip the auth0 setup for integration testing, set the `PUDL_VIEWER_INTEGRATION_TEST` env var:

```bash
$ PUDL_VIEWER_INTEGRATION_TEST=true docker compose up
```

This creates a test user that can log in and access preview functionality.

You'll still need to set up the users table in the database, though:

```
docker compose exec eel_hole uv run flask db upgrade
```

## Auth0 setup

We use Auth0 for user authentication. This means you'll need to set up your own
Auth0 credentials for development.

1. Go to the [Auth0 dashboard](https://manage.auth0.com/dashboard) and sign up for a free account.

2. [Create a new tenant](https://auth0.com/docs/get-started/auth0-overview/create-tenants). Name it something easy to remember.

3. [Create a Regular Web
   Application](https://auth0.com/docs/get-started/auth0-overview/create-applications).
   This will be the main application that manages login/logout.
   Once at the application dashboard, go to the Settings tab, where you'll
   find the client ID and secret which should go in the
   `PUDL_VIEWER_AUTH0_CLIENT_ID` and `PUDL_VIEWER_AUTH0_CLIENT_SECRET` env
   vars, respectively.

   While you're there, set the Application URIs to dev addresses as follows:
   - Allowed Callback URLs: http://127.0.0.1:8080/callback
   - Allowed Logout URLs: http://127.0.0.1:8080

   If you plan to access your app via `localhost` instead of `127.0.0.1`,
   substitute as appropriate.

   Note that you'll want **HTTP**, not **HTTPS**.

4. Create another application, this time as a Machine-to-Machine application.
   This will allow you to trigger email verification emails. Select the Auth0
   Management API and give it the `read:users` and `update:users` scopes. Put
   _its_ client ID and secret into the `PUDL_VIEWER_AUTH0_USER_API_CLIENT_ID`
   and `PUDL_VIEWER_AUTH0_USER_API_CLIENT_SECRET` scopes, respectively.

## Tests

To run the unit tests:

```
$ uv run pytest tests/test_*
```

To run the integration tests:

```
$ # If you haven't gotten playwright set up, you'll need to run `playwright install chromium` to give it *some* browser to drive
$ uv run playwright install chromium
$ PUDL_VIEWER_INTEGRATION_TEST=true docker compose up
$ uv run pytest tests/integration
```

This uses `playwright` to run through some user flows.
Make sure you have a stable Internet connection, otherwise you'll hit a bunch of timeouts.

To run the search relevancy tests:

```
$ uv run pytest -s tests/relevancy/test_*
```

## Feature Variants

In order to make testing out features more convenient, you can set feature variants in a query parameter in the url or via app config.

To enable a feature flag temporarily during development, append it as a query string in the URL:

```
http://localhost:8080/somepage?variants=my_feature:value
```

You can also define persistent feature flags via the Flask config:

```
app.config["FEATURE_VARIANTS"] = {
    "my_feature": "value",
}
```

This allows you to add conditional logic in your code:

```
def some_function():
    if get_variant('my_feature') == "value":
        # behavior of the feature we want to test
    else:
        # regular behavior
```

## Running on GCP

See the [Terraform file](https://github.com/catalyst-cooperative/pudl/blob/main/terraform/pudl-viewer.tf) for infrastructure setup details.

### Deployment

1. run `make gcp-latest` to push the image up to GCP.
2. re-deploy the service on Cloud Run.

### DB migration

1. run `make gcp-latest` to push the image up to GCP.
2. Run the Cloud Run job that runs a db migration.

## Architecture

We have a standard client-server-database situation going on.

For **search**:

1. The client sends search query to the server
2. The server queries against an in-memory search index. See the `/search` endpoint and the `search.py` file.
3. The server sends a list of matches back to the client

Via the magic of [`htmx`](https://www.htmx.org), if the search wasn't triggered by a whole page load, we only send back an HTML fragment.

For **preview**:

1. Client sends the filters that the user's applied to the server, and gets a DuckDB query back. See the `/api/duckdb` endpoint and `duckdb_query.py` files.
2. Client queries DuckDB (using [duckdb-wasm](https://duckdb.org/docs/api/wasm/overview.html)), which can read data from remote Parquet files.
3. The data comes back as Apache Arrow tables, which we convert into JS arrays to feed into [AG Grid](https://www.ag-grid.com/) viewer.

The database is _only_ used for storing users right now.

## Frameworks

- [Bulma](https://bulma.io/) for static CSS and component layout
- [Alpine](https://alpinejs.dev/) for client-side interactivity
- [HTMX](https://htmx.org/) for server-side interactivity and partial DOM updates
- [AG Grid](https://www.ag-grid.com/) for display of interactive tabular data

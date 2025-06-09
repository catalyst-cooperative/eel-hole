# Parquet Frontend-only prototype

## Installation

Install `uv` and `npm`.

Install the required packages:

```
npm install
uv sync
```

## Running this thing locally

We have a docker compose file, but *make sure to build the JS/CSS first*:

```bash
$ npm run build
...
$ docker compose build && docker compose up
```

If you want to skip the auth0 setup and just disable the authentication altogether, set the `PUDL_VIEWER_LOGIN_DISABLED` env var:

```bash
$ PUDL_VIEWER_LOGIN_DISABLED=true docker compose up
```

You won't be able to log in, but you won't have to, to see the preview functionality.

If you do want to test the login functionality, you'll need to make sure the database is up-to-date:

```bash
$ uv run flask --app eel_hole db upgrade
```

## Tests

We only have a few unit tests right now - no frontend testing or anything.

```
$ uv run pytest
```

## Feature Flags
In order to make testing out features more convenient, you can toggle feature flags in a query parameter in the url or via a config file.

To enable a feature flag temporarily during development, append it as a query string in the URL:
```
http://localhost:5000/somepage?my_feature=true
```
You can also define persistent feature flags via the Flask config:
```
app.config["FEATURE_FLAGS"] = {
    "my_feature": True,
}
```
This allows you to add conditional logic in your code:
```
def some_function():
    if is_flag_enabled('my_feature'):
        # behavior of the feature we want to test
    else:
        # regular behavior
```

To conditionally guard routes with feature flags, use the `@require_feature_flag("my_feature")` decorator. If the flag is not enabled, the route will return a `404`.

For example:
```
@app.route("/new-feature")
@require_feature_flag("my_feature")
def new_feature():
    return "This feature is gated!"
```

Note that a feature flag added in the URL is only accessible after the app has been loaded.

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

The database is *only* used for storing users right now.

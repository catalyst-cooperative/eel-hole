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
uv run prek install
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

## Staging Environment

`eel-hole` can be used to inspect `PUDL` data deployed to the staging area.
This can be triggered by setting the environment variable `PUDL_VIEWER_STAGING`,
to `true`. This can be used during local development as well as with a separate
cloud run service. For local development you can use the following command:

```bash
$ PUDL_VIEWER_STAGING=true docker compose up
```

The dedicated cloud run service is triggered via the `build-deploy-staging` workflow.
This workflow uses Google Cloud's new support for the
[docker compose](https://docs.cloud.google.com/run/docs/deploy-run-compose)
standard so it can use the existing `docker-compose.yml` file and doesn't need to
manage it's own cloud SQL instance. The one draw back of this approach is that the
`compose` support is still quite new, and each deployment will reset the security
settings with each deployment, which will make the service unaccessible. For the
time being we are relying on manually resetting the authorization settings each
time we use the staging environment. Hopefully, this is something we can streamline
as `gcloud`'s `compose` support matures. To use this remote staging environment,
follow these steps:

1. Run the `build-deploy-staging` workflow (this is auto-triggered by the `deploy-pudl`
   workflow in the `PUDL` repo when `staging=True`).
2. Navigate to the `cloud run` page in the Google Cloud Console and select the `eel-hole`
   service.
3. Go to the `Security` tab, check the `Identity Aware Proxy (IAP)` box, and click `Save`.
4. Click the link at the top of the page.

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

# Tuning search parameters using parameter sweeps

## 1. Set up an initial step file

Make a YAML file according to the SweepConfig schema in tests/relevancy/sweep_config.py.

Configure this initial step file with the current MAP score you want to beat,
the values of the search parameters that yield that MAP score, and an empty set
of sweep parameters.

The order and names of the sweep parameters come from however you laid out the search
parameter configuration in search.py.

Here is an example for the default search variant. It uses named references
(id001) to reduce copy-pasting, since the list of params to beat and the list of
center params are the same, but you can put the full list in both places if you
prefer.

```
$ cat steps/default.yaml
variant: default
beat:
  map: 0.55
  params: &id001
  - 1.5
  - 1.0
  - 0.8
  - 0.4
  - 10.0
  - -10.0
center: *id001
sweep:
  fieldboosts.name: []
  fieldboosts.description: []
  fieldboosts.column_names: []
  fieldboosts.column_descriptions: []
  out_boost: []
  preliminary_penalty: []
```

## 2. Test generating the next set of sweep parameters

The tool that generates the next set of sweep parameters is tests/relevancy/sweep.py.

It can generate sweep parameters from a bare step file, or from the combination of a step file and its performance measurements.

At this stage we are generating sweep parameters from a bare step file.

```
$ uv run python tests/relevancy/sweep.py steps/default.yaml
MAP to beat: 0.55
From params: [1.5, 1.0, 0.8, 0.4, 10.0, -10.0]
Best MAP this round: 0.550000 (1 of 0)
Next center: [1.500000, 1.000000, 0.800000, 0.400000, 10.000000, -10.000000]
Delta: 0.0
Next increment: [0.300000, 0.200000, 0.160000, 0.080000, 2.000000, -2.000000]
Enter next experiment stem (like default):
```

type in something like "default1" and hit enter. "default1" is the new experiment stem.

```
Ready to run next experiment
```

Check the output; you should have three options for each of the sweep parameters.
Note that the sweep parameters might be in a different order in this file than in
the initial step file, but that's okay -- the order between beat.params, center, and sweep
is consistent within a file, and the system will use the order of whatever step file
it's processing.

```
$ cat steps/default1.yaml
beat:
  map: 0.55
  params:
  - 1.5
  - 1.0
  - 0.8
  - 0.4
  - 10.0
  - -10.0
center:
- 1.5
- 1.0
- 0.8
- 0.4
- 10.0
- -10.0
sweep:
  fieldboosts.column_descriptions:
  - 0.32
  - 0.4
  - 0.48000000000000004
  fieldboosts.column_names:
  - 0.64
  - 0.8
  - 0.9600000000000001
  fieldboosts.description:
  - 0.8
  - 1.0
  - 1.2
  fieldboosts.name:
  - 1.2
  - 1.5
  - 1.8
  out_boost:
  - 8.0
  - 10.0
  - 12.0
  preliminary_penalty:
  - -8.0
  - -10.0
  - -12.0
variant: default
```

## 3. Test evaluating performance for the generated parameters

The tool that evaluates the performance for the generated parameters is the pytest test, `tests/relevancy/test_relevancy.py::test_sweep`.

Run it, passing in the step file using the `experiment` parameter.

```
$ uv run pytest tests/relevancy/test_relevancy.py::test_sweep --experiment steps/default1.yaml
==================================== test session starts =================================================
platform darwin -- Python 3.13.11, pytest-9.0.1, pluggy-1.6.0
rootdir: /Users/katie/Documents/work/catalyst/eel-hole
configfile: pyproject.toml
plugins: mock-3.15.1, playwright-0.7.2, base-url-2.1.0
collected 729 items

tests/relevancy/test_relevancy.py ....
```

You should get one green '.' for each of the 3\*\*(number of sweep parameters) configurations for this sweep.
Up to 1000 configurations will run in 3-4 minutes; if you have significantly more than that, consider running over lunch or overnight.

Check the output; you should get one row in `sweep.{stem}.out` for each parameter configuration.
The first column is the MAP score. The remaining columns are the parameters used for that run.

```
$ head sweep.default1.out
0.648,0.320,0.640,0.800,1.200,8.000,-8.000
0.651,0.320,0.640,0.800,1.200,8.000,-10.000
0.651,0.320,0.640,0.800,1.200,8.000,-12.000
0.660,0.320,0.640,0.800,1.200,10.000,-8.000
0.662,0.320,0.640,0.800,1.200,10.000,-10.000
0.662,0.320,0.640,0.800,1.200,10.000,-12.000
0.666,0.320,0.640,0.800,1.200,12.000,-8.000
0.668,0.320,0.640,0.800,1.200,12.000,-10.000
0.668,0.320,0.640,0.800,1.200,12.000,-12.000
0.647,0.320,0.640,0.800,1.500,8.000,-8.000
```

## 4. Run the experiment

The tool that can iterate between generating parameters and evaluating their performance is `tests/relevancy/run_sweep_experiment.sh`.

It will run for 10 iterations.
If the experiment reaches a point where no further improvements are available,
`sweep.py` will not create the next step file,
and the script will halt (likely with a "file not found" error from one component or another).

```
$ tests/relevancy/run_sweep_experiment.sh steps/default.yaml
[...]
```

This is definitely a lunch/overnight/weekend situation. The number of configurations usually
decreases over time as individual parameters stop moving though, so it's not quite 10x your test run.

## 5. Analyze the results

We're still at the "idk load it into a notebook and see if it looks okay" prototyping stage with this.
The pattern we're looking for is (if pretty hacky) gradient ascent with simulated annealing.
If it worked properly, we found a local maximum in the parameter manifold (🤓).
If it was almost right, we headed uphill but didn't reach the top before we quit looking.
If it was totally busted, we bounced around the parameter wilderness without making much improvement at all.

Look for:

- Patterns in MAP-to-beat. Ideally this never decreases, but it might stall out.
  If it stalls out super early, it might be interesting to look at the range of
  parameter settings that all have equivalent performance.
- Patterns in the path of individual parameters.
  These might start out always-increasing or always-decreasing,
  but if we did manage to narrow in on a local maximum,
  you'll get oscillations.

Anyway if you found any improvement at all, update the default params settings in search.py,
and we can figure out later whether we need to refine further.

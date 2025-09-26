"""Main app definition."""

import itertools
import json
import os
from dataclasses import asdict
from urllib.parse import quote

import requests
from authlib.integrations.flask_client import OAuth
from flask import (
    Flask,
    redirect,
    request,
    render_template,
    session,
    url_for,
)
from flask_htmx import HTMX
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from frictionless import Package, Resource

from eel_hole.models import db, User
from eel_hole.duckdb_query import ag_grid_to_duckdb, Filter
from eel_hole.logs import log
from eel_hole.search import initialize_index, run_search
from eel_hole.utils import clean_pudl_resource, clean_ferc_xbrl_resource
from eel_hole.feature_flags import is_flag_enabled

AUTH0_DOMAIN = os.getenv("PUDL_VIEWER_AUTH0_DOMAIN")
CLIENT_ID = os.getenv("PUDL_VIEWER_AUTH0_CLIENT_ID")
CLIENT_SECRET = os.getenv("PUDL_VIEWER_AUTH0_CLIENT_SECRET")


def __init_auth0(app: Flask):
    """Connects our application to Auth0.

    The client ID, client secret, and auth0 domain are all accessible at
    manage.auth0.com.

    The auth0 object this returns has a bunch of methods that handle the
    various steps of the OAuth flow.
    """
    oauth = OAuth()
    oauth.init_app(app)

    auth0 = oauth.register(
        "auth0",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        server_metadata_url=f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email"},
    )
    return auth0


def __init_db(db: SQLAlchemy, app: Flask):
    """Connect application to Postgres database for storing users.

    Uses host/port in development environment, but on Cloud Run we use a Unix
    socket under /cloudsql.
    """
    username = os.getenv("PUDL_VIEWER_DB_USERNAME")
    password = os.getenv("PUDL_VIEWER_DB_PASSWORD")
    database = os.getenv("PUDL_VIEWER_DB_NAME")

    if os.environ.get("IS_CLOUD_RUN"):
        cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
        db_uri = f"postgresql://{username}:{password}@/{database}?host=/cloudsql/{cloud_sql_connection_name}"
    else:
        host = os.getenv("PUDL_VIEWER_DB_HOST")
        port = os.getenv("PUDL_VIEWER_DB_PORT")
        db_uri = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    db.init_app(app)

    migrate = Migrate()
    migrate.init_app(app, db)


def __build_search_index():
    """Create a search index.

    We currently convert a static YAML file into a Frictionless datapackage,
    then pass that in.
    """

    def get_datapackage(datapackage_path: str) -> Package:
        s3_base_url = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly"
        url = f"{s3_base_url}/{datapackage_path}"
        log.info(f"Getting datapackage from {url}")
        descriptor = requests.get(url).json()
        log.info(f"{url} downloaded")
        return Package.from_descriptor(descriptor)

    pudl_package = get_datapackage("pudl_parquet_datapackage.json")
    log.info("Cleaning up descriptors for pudl")
    pudl_resources = [
        clean_pudl_resource(resource) for resource in pudl_package.resources
    ]
    log.info("Cleaned up descriptors for pudl")

    ferc_xbrls = [
        "ferc1_xbrl",
        "ferc2_xbrl",
        "ferc6_xbrl",
        "ferc60_xbrl",
        "ferc714_xbrl",
    ]

    ferc_xbrl_resources = []
    for ferc_xbrl in ferc_xbrls:
        ferc_xbrl_package = get_datapackage(f"{ferc_xbrl}_datapackage.json")
        log.info(f"Cleaning up descriptors for {ferc_xbrl}")
        ferc_xbrl_resources.extend(
            clean_ferc_xbrl_resource(resource, ferc_xbrl)
            for resource in ferc_xbrl_package.resources
        )
        log.info(f"Cleaned up descriptors for {ferc_xbrl}")

    all_resources = pudl_resources + ferc_xbrl_resources
    index = initialize_index(all_resources)
    log.info("index done")

    return all_resources, index


def __sort_resources_by_name(resource: Resource):
    """Helper function to enforce resource ordering with no query.

    Four recommended tables show up first, then we order by layer.
    """
    name = resource.name

    # make these tables show up first, by returning negative numbers.
    first_tables = [
        "out_eia__monthly_generators",
        "out_eia923__fuel_receipts_costs",
        "out_ferc1__yearly_all_plants",
        "out_eia__yearly_generators",
    ]
    if name in first_tables:
        return first_tables.index(name) - len(first_tables) - 1

    if name.startswith("out"):
        return 0
    if name.startswith("core"):
        return 1
    if name.startswith("_out"):
        return 2
    if name.startswith("_core"):
        return 3
    return 4


def create_app():
    """Main app definition.

    1. initialize Flask app with a bunch of extensions:
        * auth0 for authentication
        * htmx for simplifying our client/server interaction
        * accessing the db through sql alchemy
        * logins/sessions
    2. set up the search index
    3. add a middleware that bounces people to privacy policy if necessary
    3. define a bunch of application routes
    """
    app = Flask("eel_hole", instance_relative_config=True)
    if os.getenv("IS_CLOUD_RUN"):
        app.config["PREFERRED_URL_SCHEME"] = "https"
    app.config.from_mapping(
        SECRET_KEY=os.getenv("PUDL_VIEWER_SECRET_KEY"),
        TEMPLATES_AUTO_RELOAD=True,
        LOGIN_DISABLED=os.getenv("PUDL_VIEWER_LOGIN_DISABLED", False),
    )

    auth0 = __init_auth0(app)

    htmx = HTMX()
    htmx.init_app(app)

    __init_db(db, app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    all_resources, search_index = __build_search_index()
    sorted_pudl_only = sorted(
        [resource for resource in all_resources if resource.package == "pudl"],
        key=__sort_resources_by_name,
    )
    sorted_all_resources = sorted(all_resources, key=__sort_resources_by_name)

    @app.before_request
    def check_for_privacy_policy():
        """Bounce people to privacy policy if necessary.

        All of these conditions must be met:
        * you are logged in
        * you have not accepted the privacy policy
        * you are not:
            * looking at the privacy policy
            * setting privacy settings
            * logging out
            * looking at static files
        """
        if not current_user.is_authenticated:
            return None
        if current_user.accepted_privacy_policy:
            return None
        if request.path in {
            "/privacy-policy",
            "/privacy-settings",
            "/logout",
        }:
            return None
        if request.path.startswith("/static"):
            return None
        return redirect(url_for("privacy_policy", next_url=request.full_path))

    @app.get("/")
    def home():
        """Just a redirect for search until we come up with proper content."""
        return redirect(url_for("search"))

    @login_manager.user_loader
    def __load_user(user_id):
        """Teach Flask-Login how to interact with our Users in db."""
        return User.query.get(int(user_id))

    @app.route("/login")
    def login():
        """Redirect to auth0 to handle actual logging in.

        Params:
            next_url: the next URL to redirect to once logged in.
        """
        next_url = request.args.get("next_url")
        if next:
            redirect_uri = url_for("callback", next_url=next_url, _external=True)
        else:
            redirect_uri = url_for("callback", _external=True)
        return auth0.authorize_redirect(redirect_uri=redirect_uri)

    @app.route("/callback")
    def callback():
        """Once user successfully logs in on Auth0, it redirects here.

        We want to then log that user in on our system as well since we trust
        Auth0. If they don't exist in our system we add them.

        Params:
            next_url: the next URL to redirect to once logged in.
        """
        next_url = request.args.get("next_url", url_for("search"))
        token = auth0.authorize_access_token()
        userinfo = token["userinfo"]
        user = User.query.filter_by(auth0_id=userinfo["sub"]).first()
        if not user:
            user = User.from_userinfo(userinfo)
            db.session.add(user)
            db.session.commit()
        login_user(user, remember=True)
        return redirect(next_url)

    @login_required
    @app.route("/logout")
    def logout():
        """Log out user from our session & auth0 session, then go home."""
        logout_user()
        session.clear()
        return_to = quote(url_for("home", _external=True))
        response = redirect(
            f"https://{AUTH0_DOMAIN}/v2/logout?"
            f"client_id={CLIENT_ID}&"
            f"return_to={return_to}"
        )
        response.delete_cookie("remember_token")
        response.delete_cookie("session")
        return response

    @app.get("/privacy-policy")
    def privacy_policy():
        """Display the privacy policy and controls to accept/reject.

        Params:
            next_url: the next URL to redirect to after acceptance. This gets
                passed through into the rendered template as a hidden input on
                the form, so we can still see the next_url in the form handler.
        """
        next_url = request.args.get("next_url")
        return render_template("privacy-policy.html", next_url=next_url)

    @login_required
    @app.post("/privacy-settings")
    def privacy_settings():
        """POST endpoint for setting privacy settings.

        Will log people out if they reject the privacy policy.

        Form fields:
            accept_privacy_policy: "on" means they checked the checkbox and
                accepted the privacy policy.
            do_individual_outreach: "on" -> they consented to individual
                outreach
            send_newsletter: "on" -> they consented to newsletter mailings
            next_url: if present, the URL they were trying to go to before being
                forced to the privacy policy.
        """
        accepted = (
            "accept_privacy_policy" in request.form
            and request.form["accept_privacy_policy"] == "on"
        )
        outreach = (
            "do_individual_outreach" in request.form
            and request.form["do_individual_outreach"] == "on"
        )
        newsletter = (
            "send_newsletter" in request.form
            and request.form["send_newsletter"] == "on"
        )
        log.info(
            "privacy-policy",
            accepted=accepted,
            outreach=outreach,
            newsletter=newsletter,
        )
        current_user.accepted_privacy_policy = accepted
        current_user.do_individual_outreach = outreach
        current_user.send_newsletter = newsletter
        db.session.commit()
        if not accepted:
            return redirect(url_for("logout"))
        next_url = request.form.get("next_url", url_for("privacy_policy"))
        return redirect(next_url)

    @app.get("/search")
    def search():
        """Run a search query and return results.

        If hit as part of an HTMX request, only render the search results HTML
        fragment. Otherwise render the whole page.

        Params:
            q: the query string
        """
        template = "partials/search_results.html" if htmx else "search.html"
        query = request.args.get("q")
        log.info("search", url=request.full_path, query=query)

        if query:
            resources = run_search(ix=search_index, raw_query=query)
        else:
            resources = (
                sorted_all_resources
                if is_flag_enabled("ferc_enabled")
                else sorted_pudl_only
            )

        return render_template(template, resources=resources, query=query)

    @app.get("/api/duckdb")
    def duckdb():
        """Take filters from Perspective and return a DuckDB query.

        Params:
            perspective_filters: a table name and its associated filters.
            forDownload: whether this is for the full download (i.e., no row
                limit) or a sample query which needs a limit to be fast.

        Returns:
            duckdb_query: prepared statements and the corresponding values to
                both query the data and also get a full row-count of the result
                set.
        """
        name = request.args.get("name")
        filters = [
            Filter.model_validate(f)
            for f in json.loads(request.args.get("filters", "[]"))
        ]
        duckdb_query = ag_grid_to_duckdb(name=name, filters=filters)
        page = int(request.args.get("page", 1))
        DEFAULT_PREVIEW_PAGE = 10_000
        DEFAULT_CSV_EXPORT_PAGE = 1_000_000
        per_page = int(request.args.get("perPage", DEFAULT_PREVIEW_PAGE))
        if per_page == DEFAULT_PREVIEW_PAGE:
            event = "duckdb_preview"
        elif per_page == DEFAULT_CSV_EXPORT_PAGE:
            event = "duckdb_csv"
        else:
            event = "duckdb_other"

        log.info(event, url=request.full_path, params=dict(request.args))
        offset = (page - 1) * per_page
        duckdb_query.statement += f" LIMIT {per_page} OFFSET {offset}"
        return asdict(duckdb_query)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.route("/pudl/")
    @app.route("/pudl/<table_name>")
    def redirect_legacy_datasette_url(table_name: str | None = None):
        """Redirect datasette-style URLs that exist in the wild.

        As more databases (FERC 1, Census, etc.) get pulled in, we will need to
        add more routes.

        When we create direct links to tables, we will need to change the
        redirect location.
        """
        if table_name:
            query = f"name:{table_name}"
        else:
            query = None
        return redirect(url_for("search", q=query))

    return app

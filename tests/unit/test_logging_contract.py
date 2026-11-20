"""Pin the structured log events that pudl-usage-metrics parses.

The usage metrics pipeline (catalyst-cooperative/pudl-usage-metrics,
``src/usage_metrics/core/eel_hole.py``) reads this app's structlog output from GCP.
It routes each analytics event by its exact name, validates the ``/api/duckdb``
request params, and validates the AG Grid filter vocabulary. A change here that isn't
mirrored there loses data, so these tests fail whenever the contract changes. If one
fails, update the snapshots below **and** the matching constants in usage metrics:

* a new or renamed event -> ``ROUTED_EVENT_TYPES`` (plus a new table, if needed)
* a changed event field -> ``JsonPayload``
* a changed ``/api/duckdb`` request param -> ``KNOWN_PARAM_KEYS``
* a new AG Grid filter type or operation -> ``ALLOWABLE_FIELD_TYPES`` /
  ``ALLOWABLE_OPERATIONS``

Analytics events are logged with ``eel_hole.logs.log_event``, which only accepts the
events registered in ``eel_hole.logs.EVENTS``. Plain ``log`` is for operational
(prose) messages.
"""

import ast
import json
import re
from pathlib import Path
from typing import get_args

import pytest
from structlog.testing import capture_logs

from eel_hole.logs import EVENTS, EventName, log_event

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = sorted(
    p for p in (ROOT / "eel_hole").rglob("*.py") if p.name != "logs.py"
)

# Snapshot of the contract: event name -> the keyword fields it is logged with.
# ``user_id`` and ``user_domain`` are added to every event by ``user_info_adder``.
ANALYTICS_EVENTS: dict[str, frozenset[str]] = {
    "log_in": frozenset({"next_url", "is_new_user"}),
    "search": frozenset({"url", "query"}),
    "preview": frozenset({"package", "table_name", "partition"}),
    "duckdb_preview": frozenset({"url", "params"}),
    "duckdb_csv": frozenset({"url", "params"}),
    "duckdb_other": frozenset({"url", "params"}),
    "privacy-policy": frozenset({"accepted", "outreach", "newsletter"}),
    "verify-email-requested": frozenset(),
    "verify-email-failed": frozenset({"status_code"}),
    "refresh-email-verification-failed": frozenset({"status_code"}),
}

# The query-string keys of ``/api/duckdb`` (what ``params`` carries in the logs).
DUCKDB_PARAMS = frozenset({"name", "filters", "page", "perPage"})

# The AG Grid major version whose ``filterType`` values and filter operations usage
# metrics was checked against (v36 added ``bigint``; integer columns used to report
# ``number``). The grid forwards these straight into the ``filters`` param.
AG_GRID_MAJOR_VERSION = 36
AG_GRID_FILTER_TYPES = ("text", "number", "bigint", "date")
# What every rendered event carries besides its own fields.
ALWAYS_LOGGED_KEYS = frozenset({"event", "timestamp", "user_id", "user_domain"})

LOG_LEVELS = {"debug", "info", "warning", "error", "exception", "critical"}
SLUG = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
SLUG_ANY_CASE = re.compile(SLUG.pattern, re.IGNORECASE)  # same pattern, any case


# --- the registry ---------------------------------------------------------------------


def test_registry_matches_the_contract():
    registered = {name: spec.fields for name, spec in EVENTS.items()}
    assert registered == ANALYTICS_EVENTS, (
        "eel_hole.logs.EVENTS changed. Update ANALYTICS_EVENTS in this file and "
        "pudl-usage-metrics (ROUTED_EVENT_TYPES for new or renamed events, "
        "JsonPayload for changed fields, in src/usage_metrics/core/eel_hole.py), or "
        "the events are dropped or never persisted."
    )


def test_event_type_lists_every_registered_event():
    assert set(get_args(EventName)) == set(EVENTS)


def test_every_event_name_is_a_lower_case_slug():
    """``Preview`` would be dropped by the usage metrics parser as a prose line."""
    bad = sorted(name for name in EVENTS if not SLUG.match(name))
    assert not bad, f"Event names must match {SLUG.pattern}: {bad}"


@pytest.mark.parametrize("event", sorted(EVENTS))
def test_log_event_emits_the_registered_name_level_and_fields(event):
    spec = EVENTS[event]
    fields = {name: f"{name}-value" for name in spec.fields}

    with capture_logs() as logs:
        log_event(event, **fields)  # type: ignore[arg-type]

    assert logs == [{"event": event, "log_level": spec.level, **fields}]


# --- call sites -------------------------------------------------------------------------


def _calls(tree: ast.AST) -> list[tuple[ast.Call, str]]:
    """Every ``log_event(...)`` or ``log.<level>(...)`` call, as ``(node, name)``."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "log_event":
            found.append((node, "log_event"))
        elif (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "log"
            and func.attr in LOG_LEVELS
        ):
            found.append((node, f"log.{func.attr}"))
    return found


def _first_arg_names(tree: ast.AST, call: ast.Call) -> set[str] | None:
    """The string(s) a call's first argument can be, or None if not a literal."""
    first = call.args[0] if call.args else None
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return {first.value}
    if isinstance(first, ast.Name):
        names = {
            n.value.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == first.id for t in n.targets)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        }
        return names or None
    return None


def check_call_sites(
    source: str, filename: str = "<source>"
) -> tuple[set[str], list[str]]:
    """Return ``(events_logged, problems)`` for one source file."""
    tree = ast.parse(source, filename)
    logged: set[str] = set()
    problems: list[str] = []
    for call, name in _calls(tree):
        where = f"{filename}:{call.lineno}"
        names = _first_arg_names(tree, call)
        if name == "log_event":
            if names is None:
                problems.append(f"{where}: log_event() needs a literal event name")
                continue
            kwargs = frozenset(k.arg for k in call.keywords if k.arg)
            for event in names:
                logged.add(event)
                if event not in EVENTS:
                    problems.append(f"{where}: {event!r} is not in EVENTS")
                elif kwargs != EVENTS[event].fields:
                    problems.append(
                        f"{where}: {event!r} logged with {sorted(kwargs)}, "
                        f"expected {sorted(EVENTS[event].fields)}"
                    )
        elif names and any(SLUG_ANY_CASE.match(n) for n in names):
            problems.append(
                f"{where}: {name}({min(names)!r}) looks like an analytics "
                "event: use log_event() and register it in eel_hole.logs.EVENTS. "
                "Operational messages should contain spaces."
            )
    return logged, problems


def test_call_sites_use_log_event_with_the_registered_fields():
    logged: set[str] = set()
    problems: list[str] = []
    for path in SOURCE_FILES:
        file_logged, file_problems = check_call_sites(
            path.read_text(), str(path.relative_to(ROOT))
        )
        logged |= file_logged
        problems += file_problems
    assert not problems, "\n".join(problems)
    assert logged == set(EVENTS), (
        f"Registered but never logged: {sorted(set(EVENTS) - logged)}. Remove them "
        "from EVENTS and ANALYTICS_EVENTS, and tell pudl-usage-metrics."
    )


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        ('log_event("search", url=u, query=q)', None),
        ('log_event("search", url=u)', "logged with"),
        ('log_event("brand-new", url=u)', "not in EVENTS"),
        ("log_event(name_from_somewhere)", "literal event name"),
        ('log.info("Preview", package=p)', "looks like an analytics event"),
        ('log.info("search", url=u)', "looks like an analytics event"),
        ('log.warning("Loading the index from disk")', None),  # prose has spaces
        ('log.info(f"search for {q}")', None),  # f-string
        ('other.info("Preview")', None),  # not our logger
        ('event = "duckdb_csv"\nlog_event(event, url=u, params=p)', None),
    ],
)
def test_call_site_checker(source, problem):
    _, problems = check_call_sites(source)
    if problem is None:
        assert not problems
    else:
        assert len(problems) == 1 and problem in problems[0]


# --- request params and AG Grid ------------------------------------------------------


def _duckdb_request_args_read_by_backend() -> set[str]:
    tree = ast.parse((ROOT / "eel_hole/__init__.py").read_text())
    handler = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "duckdb"
    )
    keys = set()
    for node in ast.walk(handler):
        # request.args.get("key", ...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and ast.unparse(node.func.value) == "request.args"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            keys.add(node.args[0].value)
        # request.args["key"]
        if (
            isinstance(node, ast.Subscript)
            and ast.unparse(node.value) == "request.args"
            and isinstance(node.slice, ast.Constant)
        ):
            keys.add(node.slice.value)
    return keys


def _duckdb_params_sent_by_frontend() -> set[str]:
    source = (ROOT / "src/preview.ts").read_text()
    block = re.search(r"new URLSearchParams\(\{(.*?)\}\)", source, re.DOTALL)
    assert block, "src/preview.ts: expected a `new URLSearchParams({...})` call"
    return set(re.findall(r"^\s*(\w+):", block.group(1), re.MULTILINE))


def test_duckdb_params_match_the_contract():
    """``params`` in the duckdb_* events is ``dict(request.args)``, logged verbatim."""
    hint = (
        "Update KNOWN_PARAM_KEYS and DuckDBParams in pudl-usage-metrics "
        "(src/usage_metrics/core/eel_hole.py) along with DUCKDB_PARAMS here."
    )
    assert _duckdb_request_args_read_by_backend() == DUCKDB_PARAMS, (
        f"/api/duckdb reads different params than the contract. {hint}"
    )
    assert _duckdb_params_sent_by_frontend() == DUCKDB_PARAMS, (
        f"The frontend sends different params than the contract. {hint}"
    )


def test_ag_grid_version_is_the_one_usage_metrics_was_checked_against():
    """The grid forwards its ``filterType`` and operation values into the logs."""
    version = json.loads((ROOT / "package.json").read_text())["dependencies"][
        "ag-grid-community"
    ]
    major = int(re.search(r"\d+", version).group())
    assert major == AG_GRID_MAJOR_VERSION, (
        f"ag-grid-community is now v{major}. Check its `filterType` values "
        f"(contract: {AG_GRID_FILTER_TYPES}) and filter operations in "
        "node_modules/ag-grid-community/dist/types, then update "
        "ALLOWABLE_FIELD_TYPES / ALLOWABLE_OPERATIONS in pudl-usage-metrics "
        "(src/usage_metrics/core/eel_hole.py) and AG_GRID_MAJOR_VERSION / "
        "AG_GRID_FILTER_TYPES here. An unlisted value fails every logged-in "
        "/api/duckdb event in the usage metrics run."
    )


# --- what is rendered ------------------------------------------------------------------


class FakeUser:
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return "42"

    def get_domain(self):
        return "example.org"


@pytest.fixture
def app():
    from flask import Flask
    from flask_login import LoginManager

    app = Flask(__name__)
    app.secret_key = "test"
    login_manager = LoginManager(app)
    login_manager.user_loader(lambda user_id: FakeUser())
    return app


def test_events_carry_the_user_id_and_domain_of_the_logged_in_user(app, capsys):
    """``log_in`` is logged right after ``login_user``, which is when these appear."""
    from flask_login import login_user

    with app.test_request_context("/callback"):
        log_event("log_in", next_url="/search", is_new_user=False)
        anonymous = json.loads(capsys.readouterr().out)
        login_user(FakeUser())
        log_event("log_in", next_url="/search", is_new_user=False)
        logged_in = json.loads(capsys.readouterr().out)

    assert (anonymous["user_id"], anonymous["user_domain"]) == (None, None)
    assert (logged_in["user_id"], logged_in["user_domain"]) == ("42", "example.org")
    assert logged_in["event"] == "log_in"
    assert logged_in["next_url"] == "/search"


@pytest.mark.parametrize("logged_in", [False, True], ids=["anonymous", "logged-in"])
@pytest.mark.parametrize("event", sorted(EVENTS))
def test_rendered_events_have_exactly_the_contract_keys(event, logged_in, app, capsys):
    """Through the real structlog processors, not ``capture_logs``.

    A key added by a processor (a log level, a request id) would appear on every event
    and fail every day's usage metrics run, which rejects fields it doesn't expect.
    """
    from flask_login import login_user

    with app.test_request_context("/"):
        if logged_in:
            login_user(FakeUser())
        log_event(event, **{name: "x" for name in EVENTS[event].fields})  # type: ignore[arg-type]
        rendered = json.loads(capsys.readouterr().out)

    assert set(rendered) == ALWAYS_LOGGED_KEYS | EVENTS[event].fields

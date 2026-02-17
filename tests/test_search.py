import pytest

from eel_hole.search import autocomplete_resource_names, initialize_index, run_search
from eel_hole.utils import ColumnDisplay, ResourceDisplay


def _build_search_index():
    resources = [
        ResourceDisplay(
            name="out_token123_title_match",
            package="pudl",
            description="title-oriented example",
            columns=[ColumnDisplay(name="id", description="identifier")],
        ),
        ResourceDisplay(
            name="out_other_table",
            package="pudl",
            description="column-oriented example",
            columns=[
                ColumnDisplay(name="token123_metric", description="token123 value")
            ],
        ),
    ]
    return initialize_index(resources)


def test_title_boost_prefers_name_match():
    ix = _build_search_index()

    results = run_search(
        ix=ix,
        raw_query="token123",
        search_method="title_boost",
        search_packages="pudl_only",
    )

    assert results[0]["name"] == "out_token123_title_match"


def test_column_boost_prefers_column_match():
    ix = _build_search_index()

    results = run_search(
        ix=ix,
        raw_query="token123",
        search_method="column_boost",
        search_packages="pudl_only",
    )

    assert results[0]["name"] == "out_other_table"


def _resource(name: str) -> ResourceDisplay:
    return ResourceDisplay(
        name=name,
        package="pudl",
        description="",
        columns=[ColumnDisplay(name="id", description="")],
    )


RESOURCES = [
    _resource("out_eia860__yearly_ownership"),
    _resource("core_eia861__scd_territories"),
    _resource("core_eia923__monthly_boiler_fuel"),
    _resource("core_pudl__codes_datasources"),
    _resource("out_pudl__utilities"),
]


@pytest.mark.parametrize(
    "raw_query",
    [
        "eia923",
        "eia 923",
        "boiler fuel",
        "monthly boiler",
        "name:eia923 boiler",
    ],
)
def test_autocomplete_resource_names_queries_match_eia923_table(raw_query: str):
    suggestions = autocomplete_resource_names(resources=RESOURCES, raw_query=raw_query)

    assert "core_eia923__monthly_boiler_fuel" in suggestions


@pytest.mark.parametrize(
    "raw_query",
    [
        "eia860 ownership",
        "860 scd",
        "codes datasource",
        "out pudl utilities",
        "name:core_pudl__codes_datasources",
    ],
)
def test_autocomplete_resource_names_queries_do_not_match_eia923_table(raw_query: str):
    suggestions = autocomplete_resource_names(resources=RESOURCES, raw_query=raw_query)

    assert "core_eia923__monthly_boiler_fuel" not in suggestions

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


def test_autocomplete_resource_names_prefers_exact_table_name():
    resources = [
        _resource("out_eia__monthly_generators"),
        _resource("core_pudl__codes_datasources"),
        _resource("core_eia923__monthly_boiler_fuel"),
    ]

    suggestions = autocomplete_resource_names(
        resources=resources,
        raw_query="core_pudl__codes_datasources",
    )

    assert suggestions[0] == "core_pudl__codes_datasources"


def test_autocomplete_resource_names_handles_name_prefix():
    resources = [
        _resource("core_pudl__codes_datasources"),
        _resource("core_pudl__codes_data_maturities"),
    ]

    suggestions = autocomplete_resource_names(
        resources=resources,
        raw_query="name:codes_datasource",
    )

    assert "core_pudl__codes_datasources" in suggestions


def test_autocomplete_resource_names_handles_space_separated_numeric_tokens():
    resources = [
        _resource("out_eia860__yearly_ownership"),
        _resource("core_eia923__monthly_boiler_fuel"),
    ]

    suggestions = autocomplete_resource_names(resources=resources, raw_query="eia 860")

    assert suggestions[0] == "out_eia860__yearly_ownership"


def test_autocomplete_resource_names_matches_across_delimiters():
    resources = [
        _resource("core_eia861__scd_territories"),
        _resource("core_eia923__monthly_boiler_fuel"),
        _resource("out_pudl__utilities"),
    ]

    suggestions = autocomplete_resource_names(resources=resources, raw_query="eia scd")

    assert suggestions[0] == "core_eia861__scd_territories"

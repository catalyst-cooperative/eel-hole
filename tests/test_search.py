from eel_hole.search import initialize_index, run_search
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

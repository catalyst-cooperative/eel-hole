import requests
import pytest


@pytest.fixture
def reference_queries():
    """Placeholder reference queries; replace with read from YAML"""
    return [
        {
            "query": "name:epacamd",
            "relevant": {
                "core_epa__assn_eia_epacamd",
                "core_epa__assn_eia_epacamd_subplant_ids",
            },
        },
        {
            "query": "core_eia861__yearly_net_metering_customer_fuel_cla",
            "relevant": {"core_eia861__yearly_net_metering_customer_fuel_class"},
        },
        {
            "query": "data_out_eia__yearly_utilities",
            "relevant": {"out_eia__yearly_utilities"},
        },
        {
            "query": "form 1",
            "relevant": {
                "out_ferc1__yearly_all_plants",
                "out_ferc1__yearly_detailed_income_statements",
                "out_ferc1__yearly_detailed_balance_sheet_assets",
                "out_ferc1__yearly_detailed_balance_sheet_liabilities",
            },
        },
    ]


@pytest.mark.parametrize(
    "variant",
    [
        "default",
        "title_boost",
        "column_boost",
    ],
)
def test_relevancy_map(reference_queries, variant):
    """Measure search performance of available variants using Mean Average Precision (MAP)."""
    # precision at k: (number of relevant retrieved documents in first k) / k
    # average precision: sum with k from 1 to (number of retrieved documents) of:
    #     (precision at k) * (1 if kth document is relevant, 0 otherwise) / (number of relevant documents)
    # mean average precision: sum with j from 1 to (number of queries) of:
    #     (average precision of query j) / (number of queries)
    map = 0.0
    n_queries = len(reference_queries)
    for ex in reference_queries:
        result = requests.get(
            "http://localhost:8080/search",
            params={
                "q": ex["query"],
                "variants": f"search_method:{variant}",
            },
            headers={"accept-mimetypes": "application/json"},
        )
        try:
            result = result.json()
        except requests.exceptions.JSONDecodeError:
            assert False, f"Expected json; got \n{result.content}"
        assert result["settings"]["method"] == variant, (
            f"Bad variant; expected {variant} but got {result['settings']['method']}"
        )
        ap = 0.0
        n_relevant = len(ex["relevant"])
        n_relevant_retrieved = 0
        for i, doc in enumerate(result["results"]):
            if doc["name"] in ex["relevant"]:
                n_relevant_retrieved += 1
                ap += n_relevant_retrieved / (i + 1) / n_relevant
        # special case:
        # if we know there should be zero results, and there are in fact zero results, robot gets a gold star
        if n_relevant == 0 and len(result["results"]) == 0:
            ap = 1.0
        map += ap / n_queries
    print(f"\n{variant} MAP: {map}")
    assert map > 0, "MAP too miserable to ship"

import re

import pytest
import requests
import yaml

from eel_hole.search import SEARCH_VARIANT_FIELD_BOOSTS


def query_search_api(query: str, variant: str) -> dict:
    """Query the search API for one query/variant pair and validate response."""
    result = requests.get(
        "http://localhost:8080/api/search",
        params={
            "q": query,
            "variants": f"search_method:{variant}",
        },
        headers={"accept-mimetypes": "application/json"},
    )
    try:
        payload = result.json()
    except requests.exceptions.JSONDecodeError:
        assert False, f"Expected json; got \n{result.content}"
    assert payload["settings"]["method"] == variant, (
        f"Bad variant; expected {variant} but got {payload['settings']['method']}"
    )
    return payload


def _compute_relevant_ranks(result_names, relevant_names):
    """Given the actual results and expected relevant results, compute the ranks of the relevant results."""
    ranks = {}
    unseen_relevant = set(relevant_names)
    for i, name in enumerate(result_names):
        if name in unseen_relevant:
            ranks[name] = i + 1
            unseen_relevant.remove(name)
    return ranks


def _compute_average_precision(result_names, relevant_names):
    """Get the average precision for one query, based on the actual results + relevant set."""
    n_relevant = len(relevant_names)
    if n_relevant == 0 and len(result_names) == 0:
        return 1.0

    relevant_ranks = _compute_relevant_ranks(result_names, relevant_names)
    ap = 0.0
    for retrieved_count, rank in enumerate(sorted(relevant_ranks.values()), start=1):
        ap += retrieved_count / rank / n_relevant
    return ap


def _collect_query_metrics(reference_queries, variant):
    """Get metrics for the set of reference queries, and compute MAP."""
    map_score = 0.0
    query_metrics = {}
    n_top_results = 10
    n_queries = len(reference_queries)

    for ex in reference_queries:
        result = query_search_api(ex["query"], variant)
        result_names = [doc["name"] for doc in result["results"]]
        relevant_ranks = _compute_relevant_ranks(result_names, ex["relevant"])
        missing = set(ex["relevant"]) - set(result_names)
        average_precision = _compute_average_precision(result_names, ex["relevant"])

        query_metrics[ex["query"]] = {
            "average_precision": average_precision,
            "missing": missing,
            "relevant_ranks": relevant_ranks,
            "top_results": result_names[:n_top_results],
        }
        map_score += average_precision / n_queries

    return map_score, query_metrics


@pytest.fixture
def reference_queries():
    """Reference queries defined in ./reference-queries.yaml."""
    with open("tests/relevancy/reference-queries.yaml") as f:
        from_file = yaml.safe_load(f)
    return from_file


@pytest.fixture
def negative_queries():
    with open("tests/relevancy/negative-queries.yaml") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize(
    "variant",
    set(SEARCH_VARIANT_FIELD_BOOSTS.keys()),
)
def test_relevancy_map(reference_queries, variant, pytestconfig):
    """Measure search performance of available variants using Mean Average Precision (MAP).

    Pass -v for output that includes the worst-performing queries and details thereof."""
    # precision at k: (number of relevant retrieved documents in first k) / k
    # average precision: sum with k from 1 to (number of retrieved documents) of:
    #     (precision at k) * (1 if kth document is relevant, 0 otherwise) / (number of relevant documents)
    # mean average precision: sum with j from 1 to (number of queries) of:
    #     (average precision of query j) / (number of queries)
    map, query_metrics = _collect_query_metrics(reference_queries, variant)
    worst_5 = sorted(query_metrics.items(), key=lambda x: x[1]["average_precision"])[:5]
    pytestconfig._relevancy_reports[variant] = {
        "map": map,
        "worst_queries": worst_5,
    }
    assert map > 0, "MAP too miserable to ship"


@pytest.mark.xfail
@pytest.mark.parametrize(
    "variant",
    set(SEARCH_VARIANT_FIELD_BOOSTS.keys()),
)
def test_negative_queries(negative_queries, variant):
    failures = []
    for case in negative_queries:
        result = query_search_api(case["query"], variant)
        result_names = [doc["name"] for doc in result["results"]]
        for pattern in case["forbidden_regex"]:
            regex = re.compile(pattern)
            matches = [name for name in result_names if regex.search(name)]
            if matches:
                failures.append(
                    {
                        "query": case["query"],
                        "pattern": pattern,
                        "matches": matches,
                    }
                )

    assert not failures, "Forbidden regex matches found:\n" + "\n".join(
        f"query={f['query']!r} pattern={f['pattern']!r} matches={f['matches']}"
        for f in failures
    )

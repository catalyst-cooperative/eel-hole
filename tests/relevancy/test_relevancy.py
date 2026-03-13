from collections import namedtuple
from itertools import product
import re

import pytest
import requests
import yaml

from eel_hole.search import search_variants


def query_search_api(query: str, variant: str, config: str) -> dict:
    """Query the search API for one query/variant pair and validate response."""
    result = requests.get(
        "http://localhost:8080/api/search",
        params={
            "q": query,
            "variants": f"search_method:{variant}",
            "config": config,
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


def _compute_average_precision(
    n_results: int, n_relevant: int, relevant_ranks: list[int]
):
    """Compute AP from hit ranks.

    Inputs are the number of returned results, number of truly relevant documents,
    and 0-based ranks where relevant results appeared in the returned list.
    """
    if n_results == 0 and n_relevant == 0:
        return 1.0
    if n_results == 0 or n_relevant == 0 or not relevant_ranks:
        return 0.0

    relevant_in_results = min(len(relevant_ranks), n_relevant)
    return sum(
        (retrieved_relevant / (rank + 1)) / n_relevant
        for retrieved_relevant, rank in enumerate(
            sorted(relevant_ranks)[:relevant_in_results], start=1
        )
    )


def _collect_query_metrics(reference_queries, variant, config="{}"):
    """Get metrics for the set of reference queries, and compute MAP."""
    map_score = 0.0
    query_metrics = {}
    n_top_results = 10
    n_queries = len(reference_queries)

    for ex in reference_queries:
        relevant_set = set(ex["relevant"])
        results = query_search_api(ex["query"], variant, config)["results"]
        relevant_ranks = {
            result["name"]: result | {"rank": i}
            for i, result in enumerate(results)
            if result["name"] in relevant_set
        }
        missing = relevant_set - {result["name"] for result in results}
        average_precision = _compute_average_precision(
            len(results),
            len(relevant_set),
            [r["rank"] for r in relevant_ranks.values()],
        )

        query_metrics[ex["query"]] = {
            "average_precision": average_precision,
            "missing": missing,
            "relevant_ranks": relevant_ranks,
            "top_results": results[:n_top_results],
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
    set(search_variants().keys()),
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


@pytest.mark.xfail()
@pytest.mark.parametrize(
    "variant",
    set(search_variants().keys()),
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


@pytest.mark.parametrize(
    "n_results,n_relevant,relevant_ranks,expected",
    [
        (5, 2, [0, 2], (1 + (2 / 3)) / 2),
        (10, 3, [0, 1, 2], 1.0),
        (4, 3, [1], (1 / 2) / 3),
        (0, 2, [], 0.0),
        (0, 0, [], 1.0),
    ],
)
def test_compute_average_precision(n_results, n_relevant, relevant_ranks, expected):
    assert _compute_average_precision(
        n_results, n_relevant, relevant_ranks
    ) == pytest.approx(expected)


DefaultConfig = namedtuple(
    "DefaultConfig",
    "name description column_names column_descriptions out_boost preliminary_penalty",
)


@pytest.fixture
def experiment(request):
    return request.config.getoption("--experiment")


def pytest_generate_tests(metafunc):
    if "sweep_options" in metafunc.fixturenames:
        with open(metafunc.config.getoption("experiment")) as f:
            experiment_params = yaml.safe_load(f)
        metafunc.parametrize(
            "sweep_options",
            (
                DefaultConfig(*p)
                for p in product(
                    *[list(x.values()).pop() for x in experiment_params["sweep"]]
                )
            ),
        )


def test_sweep_default(reference_queries, sweep_options, pytestconfig):
    import json

    config_dict = {
        "fieldboosts": {
            "name": sweep_options.name,
            "description": sweep_options.description,
            "column_names": sweep_options.column_names,
            "column_descriptions": sweep_options.column_descriptions,
        },
        "out_boost": sweep_options.out_boost,
        "preliminary_penalty": sweep_options.preliminary_penalty,
    }
    config_param = json.dumps(config_dict)
    map, _ = _collect_query_metrics(reference_queries, "default", config_param)
    pytestconfig._sweep_results.append(
        f"{map:.3f},{','.join(f'{v:.3f}' for v in sweep_options)}"
    )

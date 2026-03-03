"""Formatting helpers for relevancy diagnostics output."""

import yaml


def _format_query_metrics(worst_queries):
    serialized = []
    for query, details in worst_queries:
        relevant_ranks = [
            f"{name}@{details['relevant_ranks'][name]}"
            for name in sorted(
                details["relevant_ranks"], key=lambda x: details["relevant_ranks"][x]
            )
        ]
        ranked_names = details["top_results"]
        max_name_len = max((len(name) for name in ranked_names), default=0)
        top_results = []
        for i, name in enumerate(ranked_names, start=1):
            marker = "*" if name in details["relevant_ranks"] else "-"
            top_results.append(f"{i:02d}:{name.ljust(max_name_len)} {marker}")
        serialized.append(
            {
                "query": query,
                "average precision": round(details["average_precision"], 4),
                "missing": sorted(details["missing"]),
                "relevant_ranks": relevant_ranks,
                "top_results": top_results,
            }
        )
    return serialized


def render_variant_report(variant, report, include_worst_queries=False):
    """Render the full report block for a single search variant as YAML."""
    payload = {
        "variant": variant,
        "mean average precision": round(report["map"], 4),
    }
    if include_worst_queries:
        payload["worst_queries"] = _format_query_metrics(report["worst_queries"])
    return "\n" + yaml.safe_dump(
        payload,
        sort_keys=False,
    )

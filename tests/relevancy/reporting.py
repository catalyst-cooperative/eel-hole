"""Formatting helpers for relevancy diagnostics output."""

import yaml


def _format_results(results, relevant_names):
    """Serialize top results with rank, relevance marker, and score.

    The report output is designed for quick visual inspection in terminal logs,
    so this function emits compact, aligned strings rather than nested objects.
    """
    max_name_len = max((len(result["name"]) for result in results), default=0)

    formatted = []
    for rank, result in enumerate(results, start=1):
        name = f"{result['name']:<{max_name_len}}"
        relevance = "✅" if result["name"] in relevant_names else "❌"
        score_text = f"score={float(result['score']):.3f}"
        line = f"{rank:02d}:{name} {score_text} {relevance}"
        formatted.append(line)
    return formatted


def _format_query_metrics(queries):
    """Serialize per-query diagnostics into YAML-friendly structures."""
    serialized = []
    for query, details in queries:
        relevant_ranks = [
            (
                f"{name}@{details['relevant_ranks'][name]['rank'] + 1} "
                f"score={details['relevant_ranks'][name]['score']:.3f}"
            )
            for name in sorted(
                details["relevant_ranks"],
                key=lambda name: details["relevant_ranks"][name]["rank"],
            )
        ]
        serialized.append(
            {
                "query": query,
                "average precision": round(details["average_precision"], 4),
                "missing": sorted(details["missing"]),
                "relevant_ranks": relevant_ranks,
                "top_results": _format_results(
                    details["top_results"],
                    details["relevant_ranks"],
                ),
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
        allow_unicode=True,
        sort_keys=False,
    )

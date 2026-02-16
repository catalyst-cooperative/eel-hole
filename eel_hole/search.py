"""Interact with the document search."""

import dataclasses
import re
from difflib import SequenceMatcher

from frictionless import Resource

# TODO 2025-01-15: think about switching this over to py-tantivy since that's better maintained
from whoosh import index
from whoosh.analysis import (
    LowercaseFilter,
    RegexTokenizer,
    StemFilter,
    StopFilter,
)
from whoosh.fields import KEYWORD, STORED, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.lang.porter import stem
from whoosh.qparser import MultifieldParser
from whoosh.query import AndMaybe, Or, Term

from eel_hole.logs import log
from eel_hole.utils import ResourceDisplay

SEARCH_VARIANT_FIELD_BOOSTS = {
    "default": {"name": 1.5, "description": 1.0, "columns": 0.5},
    "title_boost": {"name": 3.0, "description": 1.0, "columns": 0.5},
    "column_boost": {"name": 0.5, "description": 1.0, "columns": 3.0},
}
TOKEN_RE = re.compile(r"[a-z0-9]+")


def custom_stemmer(word: str) -> str:
    """Collapse words down to their roots, except for some special cases."""
    stem_map = {
        "generators": "generator",
        "generator": "generator",
    }
    return stem_map.get(word, stem(word))


def initialize_index(
    resources: list[ResourceDisplay],
) -> index.Index:
    """Index the resources from a datapackage for later searching.

    Search index is stored in memory since it's such a small dataset.
    """
    storage = RamStorage()

    analyzer = (
        RegexTokenizer(r"[A-Za-z]+|[0-9]+")
        | LowercaseFilter()
        | StopFilter()
        | StemFilter(custom_stemmer)
    )
    schema = Schema(
        name=TEXT(analyzer=analyzer, stored=True),
        description=TEXT(analyzer=analyzer),
        columns=TEXT(analyzer=analyzer),
        package=KEYWORD(stored=True),
        tags=KEYWORD(stored=True),
        original_object=STORED,
    )
    ix = storage.create_index(schema)
    writer = ix.writer()

    for resource in resources:
        description = re.sub("<[^<]+?>", "", resource.description)
        columns = "".join(
            (" ".join([col.name, col.description]) for col in resource.columns)
        )
        tags = [resource.name.strip("_").split("_")[0]]
        if resource.name.startswith("_"):
            tags.append("preliminary")

        writer.add_document(
            name=resource.name,
            description=description,
            package=resource.package,
            columns=columns,
            original_object=dataclasses.asdict(resource),
            tags=" ".join(tags),
        )

    writer.commit()

    return ix


def autocomplete_resource_names(
    resources: list[ResourceDisplay],
    raw_query: str,
    limit: int = 8,
    min_score: float = 0.45,
) -> list[str]:
    """Return table-name suggestions that are reasonably close to a query."""
    query = raw_query.strip().lower()
    if not query:
        return []
    if query.startswith("name:"):
        query = query.removeprefix("name:").strip()
    if not query:
        return []

    query_tokens = TOKEN_RE.findall(query)
    normalized_query = "".join(query_tokens)

    scored: list[tuple[float, str]] = []
    for resource in resources:
        name = resource.name
        name_lc = name.lower()
        name_tokens = TOKEN_RE.findall(name_lc)
        normalized_name = "".join(name_tokens)
        score = 0.0

        # Substring match is strong, then fall back to edit-distance-ish ratio.
        if query in name_lc:
            score = 1.0 + (len(query) / max(len(name_lc), 1))
        elif normalized_query and normalized_query in normalized_name:
            score = 0.95 + (len(normalized_query) / max(len(normalized_name), 1))

        score = max(score, SequenceMatcher(a=query, b=name_lc).ratio())

        # Token overlap helps for out-of-order partial table names.
        if query_tokens:
            overlap = sum(1 for token in query_tokens if token in name_lc)
            score += overlap / len(query_tokens)

            # Reward token order, which helps short 2-token lookups like "eia scd".
            last_index = -1
            in_order = True
            for token in query_tokens:
                token_index = name_lc.find(token, last_index + 1)
                if token_index == -1:
                    in_order = False
                    break
                last_index = token_index
            if in_order:
                score += 0.4

        if score >= min_score:
            scored.append((score, name))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored[:limit]]


def run_search(
    ix: index.Index, raw_query: str, search_method: str, search_packages: str
) -> list[Resource]:
    """Actually run a user query.

    This doctors the raw query with some field boosts + tag boosts.
    """
    field_boosts = SEARCH_VARIANT_FIELD_BOOSTS[search_method]

    with ix.searcher() as searcher:
        parser = MultifieldParser(
            ["name", "description", "columns"],
            ix.schema,
            fieldboosts=field_boosts,
        )
        user_query = parser.parse(raw_query)
        out_boost = Term("tags", "out", boost=10.0)
        preliminary_penalty = Term("tags", "preliminary", boost=-10.0)
        query_with_boosts = AndMaybe(user_query, Or([out_boost, preliminary_penalty]))
        if search_packages == "pudl_only":
            results = searcher.search(
                query_with_boosts, filter=Term("package", "pudl"), limit=50
            )
        else:
            results = searcher.search(query_with_boosts, limit=50)
        for hit in results:
            log.debug(
                "hit",
                name=hit["name"],
                tags=hit["tags"],
                score=hit.score,
                search_method=search_method,
            )
        return [hit["original_object"] for hit in results]

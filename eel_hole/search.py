"""Interact with the document search."""

import dataclasses
import re
from typing import Any

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

from eel_hole.feature_flags import is_flag_enabled
from eel_hole.logs import log
from eel_hole.utils import ResourceDisplay


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


def run_search(
    ix: index.Index, raw_query: str, search_params=dict[str, Any]
) -> list[Resource]:
    """Actually run a user query.

    This doctors the raw query with some field boosts + tag boosts.
    """
    with ix.searcher() as searcher:
        parser = MultifieldParser(
            ["name", "description", "columns"],
            ix.schema,
            fieldboosts={"name": 1.5, "description": 1.0, "columns": 0.5},
        )
        user_query = parser.parse(raw_query)
        out_boost = Term("tags", "out", boost=10.0)
        preliminary_penalty = Term("tags", "preliminary", boost=-10.0)
        query_with_boosts = AndMaybe(user_query, Or([out_boost, preliminary_penalty]))
        if not is_flag_enabled("ferc_enabled"):
            results = searcher.search(query_with_boosts, filter=Term("package", "pudl"))
        else:
            results = searcher.search(query_with_boosts)
        for hit in results:
            log.debug(
                "hit",
                name=hit["name"],
                tags=hit["tags"],
                score=hit.score,
            )
        return [hit["original_object"] for hit in results]

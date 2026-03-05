"""Interact with the document search."""

import dataclasses
import re
import shutil
from pathlib import Path

import requests
from frictionless import Package, Resource
from rapidfuzz import fuzz

# TODO 2025-01-15: think about switching this over to py-tantivy since that's better maintained
from whoosh import index
from whoosh.analysis import (
    LowercaseFilter,
    RegexTokenizer,
    StemFilter,
    StopFilter,
)
from whoosh.fields import KEYWORD, STORED, TEXT, Schema
from whoosh.filedb.filestore import FileStorage, RamStorage
from whoosh.lang.porter import stem
from whoosh.qparser import MultifieldParser
from whoosh.query import AndMaybe, Or, Term

from eel_hole.logs import log
from eel_hole.utils import (
    ResourceDisplay,
    clean_ferc_xbrl_resource,
    clean_ferceqr_resource,
    clean_pudl_resource,
)

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
    storage: RamStorage | FileStorage,
) -> index.Index:
    """Create a search index from already-cleaned resource metadata.

    Configure index-level settings, then add each resource to the index.

    We store the "original object" so we can grab anything we need for resource
    display later. We use dataclasses.asdict() to serialize over Pickle, to
    avoid having to remember to think about the stability/robustness limitations
    of Pickle in the future. Since there are multiple different classes we could
    be serializing here, we need to store the classname - we use a custom
    deserializer (ResourceDisplay.fromdict()) on the other end.
    """
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


def build_search_index(
    index_dir: str | Path = ".search-index",
) -> tuple[list[ResourceDisplay], index.Index]:
    """Fetch datapackages, clean metadata, and build an on-disk search index.

    Actual indexing logic is in initialize_index - this is just the IO and orchestration.
    """

    def get_datapackage(datapackage_path: str) -> Package:
        """Fetch a datapackage descriptor and parse it into a frictionless package."""
        log.info(f"Getting datapackage from {datapackage_path}")
        descriptor = requests.get(datapackage_path).json()
        log.info(f"{datapackage_path} downloaded")
        return Package.from_descriptor(descriptor)

    s3_base_url = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop"

    pudl_package = get_datapackage(
        f"{s3_base_url}/eel-hole/pudl_parquet_datapackage.json"
    )
    log.info("Cleaning up descriptors for pudl")
    pudl_resources = [
        clean_pudl_resource(resource) for resource in pudl_package.resources
    ]
    log.info("Cleaned up descriptors for pudl")

    ferceqr_package = get_datapackage(
        f"{s3_base_url}/ferceqr/ferceqr_parquet_datapackage.json"
    )
    log.info("Cleaning up descriptors for ferceqr")
    ferceqr_resources = [
        clean_ferceqr_resource(resource) for resource in ferceqr_package.resources
    ]
    log.info("Cleaned up descriptors for ferceqr")

    ferc_xbrls = [
        "ferc1_xbrl",
        "ferc2_xbrl",
        "ferc6_xbrl",
        "ferc60_xbrl",
        "ferc714_xbrl",
    ]

    ferc_xbrl_resources = []
    for ferc_xbrl in ferc_xbrls:
        ferc_xbrl_package = get_datapackage(
            f"{s3_base_url}/eel-hole/{ferc_xbrl}_datapackage.json"
        )
        log.info(f"Cleaning up descriptors for {ferc_xbrl}")
        ferc_xbrl_resources.extend(
            clean_ferc_xbrl_resource(resource, ferc_xbrl)
            for resource in ferc_xbrl_package.resources
        )
        log.info(f"Cleaned up descriptors for {ferc_xbrl}")

    all_resources = pudl_resources + ferceqr_resources + ferc_xbrl_resources
    target_dir = Path(index_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Building search index in {target_dir}")
    ix = initialize_index(all_resources, FileStorage(str(target_dir)))
    log.info("search index build complete")
    return all_resources, ix


def load_search_index(
    index_dir: str | Path,
) -> tuple[list[ResourceDisplay], index.Index]:
    """Open a prebuilt search index and rebuild display resources from it."""
    ix = index.open_dir(str(index_dir))
    with ix.searcher() as searcher:
        resources = [
            ResourceDisplay.fromdict(fields["original_object"])
            for fields in searcher.all_stored_fields()
        ]
    return resources, ix


def build_or_load_search_index(
    index_dir: str | Path = ".search-index",
) -> tuple[list[ResourceDisplay], index.Index]:
    """Load an existing on-disk index, or build one if it doesn't exist yet."""
    target_dir = Path(index_dir)
    if target_dir.is_dir() and index.exists_in(str(target_dir)):
        log.info(f"Loading prebuilt search index from {target_dir}")
        return load_search_index(target_dir)
    return build_search_index(target_dir)


def search_settings(search_method: str) -> dict[str, float]:
    """Identify settings for specified search method."""
    return SEARCH_VARIANT_FIELD_BOOSTS[search_method]


def build_autocomplete_name_index(
    resources: list[ResourceDisplay],
) -> list[tuple[str, str, str]]:
    """Precompute lowercase + normalized forms used by autocomplete."""
    return [
        (name, name.lower(), "".join(TOKEN_RE.findall(name.lower())))
        for name in {resource.name for resource in resources}
    ]


def autocomplete_resource_names(
    resources: list[ResourceDisplay],
    raw_query: str,
    limit: int = 8,
    min_score: float = 60.0,
    name_index: list[tuple[str, str, str]] | None = None,
) -> list[str]:
    """Return table-name suggestions that are reasonably close to a query.

    1. Clean up query
    2. Compute similarity score with *exact* match (inc. punctuation) and
       normalized query/resource name.
    3. Sort the results by score and return the top `limit` results

    We join tokens with `""` so that things like `eia860` and `eia 860` are
    treated as the same.

    NOTE (2026-02-17): our score threshold is 60 by default - but it's just a
    guess. If we find the results are too noisy/strict we should change it.
    """
    query = raw_query.strip().lower()
    if query.startswith("name:"):
        query = query.removeprefix("name:").strip()
    if not query:
        return []

    normalized_query = "".join(TOKEN_RE.findall(query))

    scored: list[tuple[float, str]] = []
    names = (
        name_index
        if name_index is not None
        else build_autocomplete_name_index(resources)
    )
    for name, name_lower, normalized_name in names:
        exact_score = fuzz.WRatio(query, name_lower)
        normalized_score = fuzz.WRatio(normalized_query, normalized_name)
        score = max(exact_score, normalized_score)

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
    field_boosts = search_settings(search_method)

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
        return [
            {
                "original_object": r["original_object"],
                "name": r["name"],
                "score": r.score,
            }
            for r in results
        ]

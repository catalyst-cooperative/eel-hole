"""Interact with the document search."""

import dataclasses
import re
import shutil
from pathlib import Path
from typing import Callable

import requests
from frictionless import Package
from pydantic import BaseModel, ConfigDict
from rapidfuzz import fuzz

# TODO 2025-01-15: think about switching this over to py-tantivy since that's better maintained
from whoosh import index
from whoosh.analysis import (
    LowercaseFilter,
    RegexTokenizer,
    StemFilter,
    StopFilter,
)
from whoosh.fields import ID, KEYWORD, STORED, TEXT, Schema
from whoosh.filedb.filestore import FileStorage, RamStorage
from whoosh.lang.porter import stem
from whoosh.qparser import MultifieldParser
from whoosh.query import AndMaybe, Or, Query, Term
from whoosh.searching import Results, Searcher

from eel_hole.logs import log
from eel_hole.utils import (
    ResourceDisplay,
    clean_ferc_xbrl_resource,
    clean_ferceqr_resource,
    clean_pudl_resource,
)

TOKEN_RE = re.compile(r"[a-z0-9]+")


SearchExecutor = Callable[[Query], Results]
SearchVariant = Callable[[Schema, str, SearchExecutor, dict], Results]


def search_variants() -> dict[str, SearchVariant]:
    """Define available search variants.

    A search variant takes a raw query and runs one or more index searches,
    returning a Whoosh Results object.

    This is a function, not a module level variable, because:
    * it wants to be at the top of the file
    * it needs to see the other functions
    """
    return {"default": default_search_query, "boost_exact_match": boost_exact_match}


def custom_stemmer(word: str) -> str:
    """Collapse words down to their roots, except for some special cases."""
    stem_map = {
        "generators": "generator",
        "generator": "generator",
    }
    return stem_map.get(word, stem(word))


def compact_for_name_match(text: str) -> str:
    """Smash the differences between strange spellings of names.

    When we're *only* looking at table-name or column-name, we don't really care
    about token boundaries, cases, or punctuation, so remove them.

    Currently this is useful for autocomplete (fuzzy match) and for the
    exact-name-match boosting.
    """
    return "".join(TOKEN_RE.findall(text.lower())).strip()


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
        RegexTokenizer(re.compile(r"[A-Za-z]+|[0-9]+"))
        | LowercaseFilter()
        | StopFilter()
        | StemFilter(custom_stemmer)
    )
    schema = Schema(
        name=TEXT(analyzer=analyzer, stored=True),
        name_exact=ID,
        description=TEXT(analyzer=analyzer),
        column_names=TEXT(analyzer=analyzer),
        column_descriptions=TEXT(analyzer=analyzer),
        # each keyword is a column
        column_names_exact=KEYWORD(commas=True),
        package=KEYWORD(stored=True),
        tags=KEYWORD(stored=True),
        original_object=STORED,
    )
    ix = storage.create_index(schema)
    writer = ix.writer()

    for resource in resources:
        description = re.sub("<[^<]+?>", "", resource.description)
        column_names = " ".join(col.name for col in resource.columns)
        column_descriptions = " ".join(col.description for col in resource.columns)
        column_names_exact_tokens = [
            compact_for_name_match(col.name) for col in resource.columns
        ]
        tags = [resource.name.strip("_").split("_")[0]]
        if resource.name.startswith("_"):
            tags.append("preliminary")

        writer.add_document(
            name=resource.name,
            name_exact=compact_for_name_match(resource.name),
            description=description,
            package=resource.package,
            column_names=column_names,
            column_descriptions=column_descriptions,
            column_names_exact=",".join(t for t in column_names_exact_tokens if t),
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


def build_autocomplete_name_index(
    resources: list[ResourceDisplay],
) -> list[tuple[str, str, str]]:
    """Precompute lowercase + normalized forms used by autocomplete."""
    return [
        (name, name.lower(), compact_for_name_match(name))
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

    normalized_query = compact_for_name_match(query)

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


class DefaultSearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fieldboosts: dict[str, float] = {
        "name": 1.5,
        "description": 1.0,
        "column_names": 0.8,
        "column_descriptions": 0.4,
    }
    out_boost: float = 10.0
    preliminary_penalty: float = -10.0


def default_search_query(
    schema: Schema, raw_query: str, execute_search: SearchExecutor, config: dict
) -> Results:
    """Default search method.

    Build one query from user text and execute it against the index.

    Query behavior:

    * AND keywords together and search over
      'name', 'description', 'column_names', and 'column_descriptions' fields
    * apply boost if the table's an `out` table
    * apply penalty if the table starts with `_` (i.e. it's a "preliminary" table)
    """
    config = DefaultSearchConfig(**config)
    parser = MultifieldParser(
        ["name", "description", "column_names", "column_descriptions"],
        schema,
        fieldboosts=config.fieldboosts,
    )
    user_query = parser.parse(raw_query)
    out_boost = Term("tags", "out", boost=config.out_boost)
    preliminary_penalty = Term("tags", "preliminary", boost=config.preliminary_penalty)
    keyword_and_boost = AndMaybe(user_query, Or([out_boost, preliminary_penalty]))
    return execute_search(keyword_and_boost)


def boost_exact_match(
    schema: Schema, raw_query: str, execute_search: SearchExecutor, config: dict
) -> Results:
    """Run

    * apply manual query substitutions
    * combine two queries (apply layer-based boosts/penalties to both)
      * full text query
      * exact-match query on table/column names
    """
    rewritten_query = apply_manual_query_substitutions(
        raw_query,
        {"form 1": "ferc1", "utility finance": "'balance sheets' OR income"},
    )

    out_boost = Term("tags", "out", boost=10.0)
    preliminary_penalty = Term("tags", "preliminary", boost=-10.0)
    ranking_adjustments = Or([out_boost, preliminary_penalty])

    full_text_parser = MultifieldParser(
        ["name", "description", "column_names", "column_descriptions"],
        schema,
        fieldboosts={
            "name": 1.5,
            "description": 1.0,
            "column_names": 0.8,
            "column_descriptions": 0.4,
        },
    )

    full_text_query = full_text_parser.parse(rewritten_query)
    boosted_full_text_results = execute_search(
        AndMaybe(full_text_query, ranking_adjustments)
    )

    normalized_query = compact_for_name_match(rewritten_query)
    exact_query = Or(
        [
            Term("name_exact", normalized_query, boost=3.0),
            Term("column_names_exact", normalized_query, boost=1.5),
        ]
    )
    exact_results = execute_search(AndMaybe(exact_query, ranking_adjustments))

    exact_results.upgrade_and_extend(boosted_full_text_results)

    return exact_results


def apply_manual_query_substitutions(query: str, subs: dict[str, str]) -> str:
    """Apply curated query substitutions before parsing."""
    for target, replacement in subs.items():
        query = query.replace(target, replacement)
    return query


def run_search(
    searcher: Searcher,
    raw_query: str,
    search_method: str,
    search_packages: str,
    search_config: dict,
) -> Results:
    """Actually run a user query.

    Run the selected search variant and return Whoosh Results.

    Callers must consume the returned Results before the provided searcher is closed.
    """

    def execute_search(query: Query) -> Results:
        if search_packages == "pudl_only":
            return searcher.search(query, filter=Term("package", "pudl"), limit=50)
        return searcher.search(query, limit=50)

    return search_variants()[search_method](
        schema=searcher.schema,
        raw_query=raw_query,
        execute_search=execute_search,
        config=search_config,
    )

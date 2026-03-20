import logging

from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    PayloadSelectorExclude,
    Prefetch,
)

from backend.caselaw.models import (
    CaselawReferenceSearch,
    CaselawSearch,
    CaselawSectionSearch,
    CaselawSummarySearch,
    ReferenceType,
)
from backend.core.cache import cached_search
from backend.core.filters import build_year_range_conditions, extract_enum_values
from lex.caselaw.models import Caselaw, CaselawSection, CaselawSummary
from lex.core.embeddings import generate_hybrid_embeddings_async
from lex.core.qdrant_client import async_qdrant_client
from lex.settings import CASELAW_COLLECTION, CASELAW_SECTION_COLLECTION, CASELAW_SUMMARY_COLLECTION

logger = logging.getLogger(__name__)

# Exclude large text fields from caselaw search results (text can be 260K+ chars)
_CASELAW_METADATA_ONLY = PayloadSelectorExclude(exclude=["text", "header"])


def get_filters(
    court_filter: list = None,
    division_filter: list = None,
    year_from: int = None,
    year_to: int = None,
) -> list:
    """Returns Qdrant filter conditions for the query."""
    conditions = []

    if court_filter and len(court_filter) > 0:
        conditions.append(
            FieldCondition(key="court", match=MatchAny(any=extract_enum_values(court_filter)))
        )

    if division_filter and len(division_filter) > 0:
        conditions.append(
            FieldCondition(key="division", match=MatchAny(any=extract_enum_values(division_filter)))
        )

    conditions.extend(build_year_range_conditions(year_from, year_to))

    return conditions


@cached_search
async def caselaw_search(input: CaselawSearch) -> dict:
    """Search for caselaw using Qdrant hybrid search.

    If a query is provided, performs hybrid (dense + sparse) search if is_semantic_search=True,
    or sparse-only (BM25) search if is_semantic_search=False.
    If no query, returns filtered results.

    Returns:
        dict with keys: results (list[Caselaw]), total (int), offset (int), size (int)
    """
    filter_conditions = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None

    if input.query and input.query.strip():
        dense, sparse = await generate_hybrid_embeddings_async(input.query)

        if input.is_semantic_search:
            results = await async_qdrant_client.query_points(
                collection_name=CASELAW_COLLECTION,
                query=FusionQuery(fusion=Fusion.RRF),
                prefetch=[
                    Prefetch(query=dense, using="dense", limit=input.size + input.offset),
                    Prefetch(query=sparse, using="sparse", limit=input.size + input.offset),
                ],
                query_filter=query_filter,
                limit=input.size,
                offset=input.offset,
                with_payload=_CASELAW_METADATA_ONLY,
            )
        else:
            results = await async_qdrant_client.query_points(
                collection_name=CASELAW_COLLECTION,
                query=sparse,
                using="sparse",
                query_filter=query_filter,
                limit=input.size,
                offset=input.offset,
                with_payload=_CASELAW_METADATA_ONLY,
            )
    else:
        results = await async_qdrant_client.query_points(
            collection_name=CASELAW_COLLECTION,
            query_filter=query_filter,
            limit=input.size,
            offset=input.offset,
            with_payload=_CASELAW_METADATA_ONLY,
        )

    cases = [Caselaw(**point.payload) for point in results.points]
    total = len(results.points)

    return {"results": cases, "total": total, "offset": input.offset, "size": input.size}


async def caselaw_section_search(input: CaselawSectionSearch) -> list[CaselawSection]:
    """Search for caselaw sections using Qdrant hybrid search."""
    filter_conditions = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None

    if input.query and input.query.strip():
        dense, sparse = await generate_hybrid_embeddings_async(input.query)

        results = await async_qdrant_client.query_points(
            collection_name=CASELAW_SECTION_COLLECTION,
            query=FusionQuery(fusion=Fusion.RRF),
            prefetch=[
                Prefetch(query=dense, using="dense", limit=input.limit + input.offset),
                Prefetch(query=sparse, using="sparse", limit=input.limit + input.offset),
            ],
            query_filter=query_filter,
            limit=input.limit,
            offset=input.offset,
            with_payload=True,
        )
    else:
        results = await async_qdrant_client.query_points(
            collection_name=CASELAW_SECTION_COLLECTION,
            query_filter=query_filter,
            limit=input.limit,
            offset=input.offset,
            with_payload=True,
        )

    return [CaselawSection(**point.payload) for point in results.points]


async def caselaw_reference_search(input: CaselawReferenceSearch) -> list[Caselaw]:
    """Search for caselaw that references a specific case or legislation."""
    reference_field = (
        "caselaw_references"
        if input.reference_type == ReferenceType.CASELAW
        else "legislation_references"
    )

    filter_conditions = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    filter_conditions.append(
        FieldCondition(key=reference_field, match=MatchAny(any=[input.reference_id]))
    )

    query_filter = Filter(must=filter_conditions)

    results, _ = await async_qdrant_client.scroll(
        collection_name=CASELAW_COLLECTION,
        scroll_filter=query_filter,
        limit=input.size,
        with_payload=_CASELAW_METADATA_ONLY,
        with_vectors=False,
    )

    return [Caselaw(**point.payload) for point in results]


@cached_search
async def caselaw_summary_search(input: CaselawSummarySearch) -> dict:
    """Search caselaw summaries for efficient discovery."""
    filter_conditions = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None

    if input.query and input.query.strip():
        dense, sparse = await generate_hybrid_embeddings_async(input.query)

        if input.is_semantic_search:
            results = await async_qdrant_client.query_points(
                collection_name=CASELAW_SUMMARY_COLLECTION,
                query=FusionQuery(fusion=Fusion.RRF),
                prefetch=[
                    Prefetch(query=dense, using="dense", limit=input.size + input.offset),
                    Prefetch(query=sparse, using="sparse", limit=input.size + input.offset),
                ],
                query_filter=query_filter,
                limit=input.size,
                offset=input.offset,
                with_payload=True,
            )
        else:
            results = await async_qdrant_client.query_points(
                collection_name=CASELAW_SUMMARY_COLLECTION,
                query=sparse,
                using="sparse",
                query_filter=query_filter,
                limit=input.size,
                offset=input.offset,
                with_payload=True,
            )
    else:
        results = await async_qdrant_client.query_points(
            collection_name=CASELAW_SUMMARY_COLLECTION,
            query_filter=query_filter,
            limit=input.size,
            offset=input.offset,
            with_payload=True,
        )

    summaries = [CaselawSummary(**point.payload) for point in results.points]
    total = len(results.points)

    return {"results": summaries, "total": total, "offset": input.offset, "size": input.size}

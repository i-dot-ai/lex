import logging

from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    Prefetch,
    Range,
)

from backend.caselaw.models import (
    CaselawReferenceSearch,
    CaselawSearch,
    CaselawSectionSearch,
    ReferenceType,
)
from backend.core.cache import cached_search
from lex.caselaw.models import Caselaw, CaselawSection
from lex.core.embeddings import generate_hybrid_embeddings
from lex.core.qdrant_client import qdrant_client
from lex.settings import CASELAW_COLLECTION, CASELAW_SECTION_COLLECTION

logger = logging.getLogger(__name__)


def get_filters(
    court_filter: list = None,
    division_filter: list = None,
    year_from: int = None,
    year_to: int = None,
) -> list:
    """Returns Qdrant filter conditions for the query."""
    conditions = []

    if court_filter and len(court_filter) > 0:
        court_values = [c.value if hasattr(c, "value") else c for c in court_filter]
        conditions.append(FieldCondition(key="court", match=MatchAny(any=court_values)))

    if division_filter and len(division_filter) > 0:
        division_values = [d.value if hasattr(d, "value") else d for d in division_filter]
        conditions.append(FieldCondition(key="division", match=MatchAny(any=division_values)))

    if year_from:
        conditions.append(FieldCondition(key="year", range=Range(gte=year_from)))

    if year_to:
        conditions.append(FieldCondition(key="year", range=Range(lte=year_to)))

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
        # Generate embeddings for query
        dense, sparse = generate_hybrid_embeddings(input.query)

        if input.is_semantic_search:
            # Hybrid search with RRF fusion
            results = qdrant_client.query_points(
                collection_name=CASELAW_COLLECTION,
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
            # Sparse-only (BM25) search
            results = qdrant_client.query_points(
                collection_name=CASELAW_COLLECTION,
                query=sparse,
                using="sparse",
                query_filter=query_filter,
                limit=input.size,
                offset=input.offset,
                with_payload=True,
            )
    else:
        # No query - just filter
        results = qdrant_client.query_points(
            collection_name=CASELAW_COLLECTION,
            query_filter=query_filter,
            limit=input.size,
            offset=input.offset,
            with_payload=True,
        )

    cases = [Caselaw(**point.payload) for point in results.points]

    # Qdrant doesn't return total in query_points, approximate with results length
    total = len(results.points)

    return {"results": cases, "total": total, "offset": input.offset, "size": input.size}


async def caselaw_section_search(input: CaselawSectionSearch) -> list[CaselawSection]:
    """Search for caselaw sections using Qdrant hybrid search.

    If a query is provided, performs hybrid semantic search.
    Otherwise, returns results based on filters only.
    """
    filter_conditions = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None

    if input.query and input.query.strip():
        # Generate hybrid embeddings
        dense, sparse = generate_hybrid_embeddings(input.query)

        # Hybrid search with RRF fusion
        results = qdrant_client.query_points(
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
        # No query - just filter
        results = qdrant_client.query_points(
            collection_name=CASELAW_SECTION_COLLECTION,
            query_filter=query_filter,
            limit=input.limit,
            offset=input.offset,
            with_payload=True,
        )

    sections = [CaselawSection(**point.payload) for point in results.points]

    return sections


async def caselaw_reference_search(input: CaselawReferenceSearch) -> list[Caselaw]:
    """Search for caselaw that references a specific case or legislation.

    This function takes a reference ID and type, and returns all cases that
    reference that ID, filtered by the provided criteria.
    """
    # Determine which field to search based on reference type
    reference_field = (
        "caselaw_references"
        if input.reference_type == ReferenceType.CASELAW
        else "legislation_references"
    )

    # Get the standard filters
    filter_conditions = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    # Add reference filter using MatchAny (checks if reference_id is in the array)
    filter_conditions.append(
        FieldCondition(key=reference_field, match=MatchAny(any=[input.reference_id]))
    )

    query_filter = Filter(must=filter_conditions)

    # Use scroll to get all matching documents
    results, _ = qdrant_client.scroll(
        collection_name=CASELAW_COLLECTION,
        scroll_filter=query_filter,
        limit=input.size,
        with_payload=True,
        with_vectors=False,
    )

    # Convert to Caselaw objects
    cases = [Caselaw(**point.payload) for point in results]

    return cases

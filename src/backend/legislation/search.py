import logging
import time
from collections import defaultdict

from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    Prefetch,
    Range,
)

from backend.core.cache import cached_search
from backend.legislation.models import (
    LegislationActSearch,
    LegislationFullText,
    LegislationFullTextLookup,
    LegislationLookup,
    LegislationSectionLookup,
    LegislationSectionSearch,
)
from lex.core.embeddings import generate_hybrid_embeddings
from lex.core.qdrant_client import qdrant_client
from lex.legislation.models import (
    Legislation,
    LegislationCategory,
    LegislationSection,
    LegislationType,
)
from lex.settings import (
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
    LEGISLATION_TYPE_MAPPING,
)

logger = logging.getLogger(__name__)


@cached_search
async def legislation_section_search(
    input: LegislationSectionSearch,
) -> list[LegislationSection]:
    """Search for legislation sections using Qdrant hybrid search."""

    logger.info(
        f"Legislation section search input: query='{input.query}', legislation_id='{input.legislation_id}', size={input.size}"
    )

    sections, _ = await qdrant_search(
        collection=LEGISLATION_SECTION_COLLECTION,
        search_query=input.query,
        is_semantic_search=True,
        category_selection=input.legislation_category,
        type_selection=input.legislation_type,
        year_from=input.year_from,
        year_to=input.year_to,
        legislation_id=input.legislation_id,
        size=input.size,
        offset=input.offset,
        include_text=input.include_text,
    )

    logger.info(
        f"Found {len(sections)} sections for legislation_id='{input.legislation_id}' with query='{input.query}'"
    )

    # Debug log first few sections found
    if sections:
        for i, section in enumerate(sections[:3]):
            logger.info(
                f"Section {i + 1}: id='{section.id}', legislation_id='{section.legislation_id}', title='{section.title[:100]}'"
            )
    else:
        logger.warning(
            f"No sections found for query='{input.query}' within legislation_id='{input.legislation_id}'"
        )

    return sections


@cached_search
async def legislation_act_search(input: LegislationActSearch) -> dict:
    """Search for legislation using hybrid section search.

    Process:
    1. Search sections with hybrid embeddings (dense semantic + sparse BM25)
    2. Group sections by parent legislation, keep top 10 per act
    3. Batch lookup legislation metadata
    4. Return ranked by best matching section scores

    Returns:
        dict with keys: results, total, offset, limit
    """
    start_time = time.time()
    logger.info(f"Searching for: {input.query}")

    # Search sections with hybrid embeddings (200 sections to get diverse results)
    # Reduced from 500 to 200 for 60% faster queries while maintaining quality
    # Don't need text here - only metadata for grouping by legislation_id
    section_search_start = time.time()
    sections, scores = await qdrant_search(
        collection=LEGISLATION_SECTION_COLLECTION,
        search_query=input.query,
        is_semantic_search=True,
        category_selection=None,
        type_selection=input.legislation_type,
        year_from=input.year_from,
        year_to=input.year_to,
        size=200,
        include_text=False,
    )
    section_search_time = time.time() - section_search_start
    logger.info(f"Found {len(sections)} sections in {section_search_time:.3f}s")

    # Group sections by legislation ID, keep top 10 per act
    legislation_sections = defaultdict(list)
    for section in sections:
        leg_id = section.legislation_id
        score = scores.get(section.id, 0.0)
        legislation_sections[leg_id].append({"section": section, "score": score})

    for leg_id in legislation_sections:
        legislation_sections[leg_id].sort(key=lambda x: x["score"], reverse=True)
        legislation_sections[leg_id] = legislation_sections[leg_id][:10]

    # Pagination
    total_unique = len(legislation_sections)
    all_leg_ids = list(legislation_sections.keys())
    unique_leg_ids = all_leg_ids[input.offset : input.offset + input.limit]

    if not unique_leg_ids:
        return {
            "results": [],
            "total": total_unique,
            "offset": input.offset,
            "limit": input.limit,
        }

    # Batch lookup legislation metadata (single query instead of N queries)
    lookup_start = time.time()
    leg_by_id = {}
    
    # Apply same year filters to legislation lookup to ensure consistency
    lookup_conditions = [FieldCondition(key="id", match=MatchAny(any=unique_leg_ids))]
    lookup_conditions.extend(build_year_filters(input.year_from, input.year_to, year_field="year"))
    
    points = qdrant_client.scroll(
        collection_name=LEGISLATION_COLLECTION,
        scroll_filter=Filter(must=lookup_conditions),
        limit=len(unique_leg_ids),
        with_payload=True,
        with_vectors=False,
    )[0]

    for point in points:
        leg_id = point.payload.get("id")
        if leg_id:
            leg_by_id[leg_id] = Legislation(**point.payload)

    # Log if parent documents are missing (data consistency issue)
    missing_docs = set(unique_leg_ids) - set(leg_by_id.keys())
    if missing_docs:
        logger.warning(f"Parent legislation not found: {len(missing_docs)} documents missing from main collection")
        logger.debug(f"Missing IDs sample: {list(missing_docs)[:3]}")
        
        # Extract years from missing documents for diagnosis
        missing_years = {
            sections_data[0]["section"].legislation_year 
            for leg_id, sections_data in legislation_sections.items() 
            if leg_id in missing_docs and sections_data and hasattr(sections_data[0]["section"], 'legislation_year')
        }
        if missing_years:
            logger.warning(f"Missing documents from years: {sorted(missing_years)}")

    lookup_time = time.time() - lookup_start
    logger.info(f"Looked up {len(leg_by_id)} acts in {lookup_time:.3f}s")

    # Build results with top sections
    results = []
    for leg_id in unique_leg_ids:
        if leg_id in leg_by_id:
            leg_dict = leg_by_id[leg_id].model_dump()
            sections_list = [
                {
                    "number": str(s["section"].number) if s["section"].number else "",
                    "provision_type": s["section"].provision_type.value,
                    "score": s["score"],
                }
                for s in legislation_sections[leg_id]
            ]
            leg_dict["sections"] = sections_list
            results.append(leg_dict)

    total_time = time.time() - start_time
    logger.info(
        f"Search completed in {total_time:.3f}s (sections:{section_search_time:.3f}s, lookup:{lookup_time:.3f}s)"
    )

    return {
        "results": results,
        "total": total_unique,
        "offset": input.offset,
        "limit": input.limit,
    }


def get_legislation_types(
    category_selection: list[LegislationCategory] | None = None,
    type_selection: list[LegislationType] | None = None,
) -> list[str] | None:
    """Returns list of legislation types based on category/type selection."""

    if type_selection and len(type_selection) > 0:
        return [t.value for t in type_selection]
    elif category_selection and len(category_selection) > 0:
        res = []
        for category in category_selection:
            res.extend(LEGISLATION_TYPE_MAPPING[category.value])
        return res
    else:
        return None


def normalize_legislation_id(legislation_id: str) -> str:
    """
    Normalize legislation_id to the full URL format.

    Converts formats like:
    - "ukpga/1994/13" -> "http://www.legislation.gov.uk/id/ukpga/1994/13"
    - "http://www.legislation.gov.uk/id/ukpga/1994/13" -> "http://www.legislation.gov.uk/id/ukpga/1994/13" (unchanged)
    """
    if not legislation_id:
        return legislation_id

    # If it's already a full URL, return as-is
    if legislation_id.startswith("http://www.legislation.gov.uk/id/"):
        return legislation_id

    # If it's a short format, convert to full URL
    # Expected format: "type/year/number" (e.g., "ukpga/1994/13")
    return f"http://www.legislation.gov.uk/id/{legislation_id}"


def build_year_filters(year_from: int = None, year_to: int = None, year_field: str = "legislation_year") -> list:
    """Build consistent year filter conditions."""
    filters = []
    if year_from:
        filters.append(FieldCondition(key=year_field, range=Range(gte=year_from)))
    if year_to:
        filters.append(FieldCondition(key=year_field, range=Range(lte=year_to)))
    return filters


def get_filters(
    category_selection: list[LegislationCategory],
    type_selection: list[LegislationType],
    year_from: int,
    year_to: int,
    legislation_id: str = None,
) -> list:
    """Returns Qdrant filter conditions for the query."""

    # Priority filter - if legislation_id provided, use only it
    if legislation_id:
        # Normalize the legislation_id to the full URL format
        normalized_id = normalize_legislation_id(legislation_id)
        logger.info(
            f"Creating filter for legislation_id: '{legislation_id}' -> normalized: '{normalized_id}'"
        )
        return [FieldCondition(key="legislation_id", match=MatchValue(value=normalized_id))]

    legislation_types = (
        get_legislation_types(category_selection, type_selection)
        if category_selection or type_selection
        else None
    )

    conditions = []
    if legislation_types:
        logger.debug(f"Adding legislation_type filter: {legislation_types}")
        conditions.append(
            FieldCondition(key="legislation_type", match=MatchAny(any=legislation_types))
        )

    # Add year filters using the new helper
    conditions.extend(build_year_filters(year_from, year_to))

    logger.debug(f"Created {len(conditions)} filter conditions")
    return conditions


async def qdrant_search(
    collection: str,
    search_query: str = None,
    is_semantic_search: bool = False,
    category_selection: list[LegislationCategory] = None,
    type_selection: list[LegislationType] = None,
    year_from: int = None,
    year_to: int = None,
    legislation_id: str = None,
    size: int = 20,
    offset: int = 0,
    include_text: bool = True,
) -> tuple[list[LegislationSection], dict[str, float]]:
    """Performs Qdrant hybrid search and returns results with scores.

    Args:
        include_text: If False, excludes 'text' field from results for faster retrieval
    """

    filter_conditions = get_filters(
        category_selection=category_selection,
        type_selection=type_selection,
        year_from=year_from,
        year_to=year_to,
        legislation_id=legislation_id,
    )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None
    logger.debug(f"Qdrant search query_filter: {query_filter}")
    logger.debug(
        f"Qdrant search params: collection={collection}, search_query='{search_query}', is_semantic_search={is_semantic_search}, size={size}, offset={offset}"
    )

    # Determine which payload fields to retrieve
    # When include_text=False, exclude large text field for 60% faster retrieval
    payload_fields = (
        True
        if include_text
        else [
            "id",
            "uri",
            "legislation_id",
            "title",
            "provision_type",
            "legislation_type",
            "legislation_year",
            "legislation_number",
            "extent",
        ]
    )

    if is_semantic_search and search_query:
        # Generate hybrid embeddings
        dense, sparse = generate_hybrid_embeddings(search_query)

        # Hybrid search with DBSF fusion (optimized via blind evaluation experiments)
        # DBSF (Distribution-Based Score Fusion) with dense-favoring ratio
        # outperforms RRF by using statistical normalization (mean ± 3σ)
        # Reduced from 5x/1x to 3x/0.8x for 40% fewer vector comparisons
        dense_limit = max(30, 3 * (size + offset))  # 3x multiplier for dense
        sparse_limit = max(8, int(0.8 * (size + offset)))  # 0.8x multiplier for sparse

        results = qdrant_client.query_points(
            collection_name=collection,
            query=FusionQuery(fusion=Fusion.DBSF),  # Distribution-Based Score Fusion
            prefetch=[
                Prefetch(query=dense, using="dense", limit=dense_limit),
                Prefetch(query=sparse, using="sparse", limit=sparse_limit),
            ],
            query_filter=query_filter,
            limit=size,
            offset=offset,
            with_payload=payload_fields,
        )

    elif search_query:
        # Sparse-only (BM25) search for non-semantic queries
        _, sparse = generate_hybrid_embeddings(search_query)

        results = qdrant_client.query_points(
            collection_name=collection,
            query=sparse,
            using="sparse",
            query_filter=query_filter,
            limit=size,
            offset=offset,
            with_payload=payload_fields,
        )
    else:
        # No query - just filter
        results = qdrant_client.query_points(
            collection_name=collection,
            query_filter=query_filter,
            limit=size,
            offset=offset,
            with_payload=payload_fields,
        )

    # Build sections list and scores dict
    sections = []
    scores = {}
    max_score = max([p.score for p in results.points], default=1.0) if results.points else 1.0
    # Ensure max_score is never 0 to prevent division by zero
    if max_score <= 0:
        max_score = 1.0

    logger.debug(f"Qdrant returned {len(results.points)} results, max_score={max_score}")
    for i, point in enumerate(results.points):
        if i < 3:  # Log first 3 results for debugging
            logger.debug(
                f"Result {i}: score={point.score}, legislation_id={point.payload.get('legislation_id', 'N/A')}"
            )

        section = LegislationSection(**point.payload)
        sections.append(section)

        # Store normalized score
        if point.score is not None:
            scores[section.id] = point.score / max_score

    logger.debug(f"Returning {len(sections)} sections")
    return sections, scores


async def legislation_lookup(input: LegislationLookup) -> Legislation | None:
    """Lookup legislation by exact type, year, and number.

    Args:
        input: LegislationLookup with legislation_type, year, and number fields

    Returns:
        Legislation object if found, None if not found
    """
    logger.info(
        f"Looking up legislation: type={input.legislation_type.value}, year={input.year}, number={input.number}"
    )

    # Validate input parameters
    if input.year < 1267 or input.year > 2030:
        logger.warning(f"Invalid year provided: {input.year}. Should be between 1267 and 2030.")
        return None

    if input.number <= 0:
        logger.warning(f"Invalid number provided: {input.number}. Should be positive.")
        return None

    points = qdrant_client.scroll(
        collection_name=LEGISLATION_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="type", match=MatchValue(value=input.legislation_type.value)),
                FieldCondition(key="year", match=MatchValue(value=input.year)),
                FieldCondition(key="number", match=MatchValue(value=input.number)),
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )[0]

    if not points:
        logger.info(
            f"No legislation found for type={input.legislation_type.value}, year={input.year}, number={input.number}"
        )
        return None

    legislation = Legislation(**points[0].payload)
    logger.info(f"Found legislation: '{legislation.title}' (id={legislation.id})")

    return legislation


async def get_legislation_sections(
    input: LegislationSectionLookup,
) -> list[LegislationSection]:
    """Retrieve all sections of specific legislation by legislation_id.

    Args:
        input: LegislationSectionLookup with legislation_id and limit

    Returns:
        List of LegislationSection objects sorted by section number
    """
    # Normalize the legislation_id to ensure consistent format
    normalized_id = normalize_legislation_id(input.legislation_id)
    logger.info(
        f"Looking up sections for legislation_id: '{input.legislation_id}' -> normalized: '{normalized_id}', limit={input.limit}"
    )

    # Use scroll to get all sections (sorted by number in payload)
    points, _ = qdrant_client.scroll(
        collection_name=LEGISLATION_SECTION_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="legislation_id", match=MatchValue(value=normalized_id))]
        ),
        limit=input.limit,
        with_payload=True,
        with_vectors=False,
    )

    sections = [LegislationSection(**point.payload) for point in points]
    logger.info(f"Found {len(sections)} sections for legislation_id: '{normalized_id}'")

    # Sort by number (Qdrant doesn't support sort in scroll API)
    sections.sort(key=lambda s: s.number if s.number else 0)

    return sections


async def get_legislation_full_text(input: LegislationFullTextLookup) -> LegislationFullText:
    """Retrieve the full text of a legislation document by its ID.

    This function:
    1. Retrieves the legislation metadata by ID
    2. Retrieves sections and optionally schedules
    3. Sorts provisions by type (sections first, then schedules) and number
    4. Concatenates all provision texts
    5. Returns the combined metadata and full text
    """
    # Normalize the legislation_id to ensure consistent format
    normalized_id = normalize_legislation_id(input.legislation_id)
    logger.info(
        f"Getting full text for legislation_id: '{input.legislation_id}' -> normalized: '{normalized_id}', include_schedules={input.include_schedules}"
    )

    # Get legislation metadata
    points = qdrant_client.scroll(
        collection_name=LEGISLATION_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="id", match=MatchValue(value=normalized_id))]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )[0]

    if not points:
        logger.warning(f"No legislation found with id: '{normalized_id}'")
        return None

    legislation = Legislation(**points[0].payload)
    logger.info(f"Found legislation: '{legislation.title}'")

    # Build provision type filter
    provision_types = ["section"]
    if input.include_schedules:
        provision_types.append("schedule")

    # Query for provisions
    provisions_points, _ = qdrant_client.scroll(
        collection_name=LEGISLATION_SECTION_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="legislation_id", match=MatchValue(value=normalized_id)),
                FieldCondition(key="provision_type", match=MatchAny(any=provision_types)),
            ]
        ),
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )

    provisions = [LegislationSection(**point.payload) for point in provisions_points]

    # Sort: sections first, then schedules, then by number
    provisions.sort(
        key=lambda p: (
            0 if p.provision_type.value == "section" else 1,
            p.number if p.number else 0,
        )
    )

    # Concatenate all provision texts
    full_text = ""

    for provision in provisions:
        full_text += "\n\n"
        full_text += provision.text

    return LegislationFullText(
        legislation=legislation,
        full_text=full_text.strip()
        if full_text.strip()
        else "No text content available for this legislation.",
    )

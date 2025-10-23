import logging

from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    Prefetch,
)

from backend.explanatory_note.models import ExplanatoryNoteSearch
from lex.core.embeddings import generate_hybrid_embeddings
from lex.core.qdrant_client import qdrant_client
from lex.explanatory_note.models import (
    ExplanatoryNote,
    ExplanatoryNoteSectionType,
    ExplanatoryNoteType,
)
from lex.settings import EXPLANATORY_NOTE_COLLECTION

logger = logging.getLogger(__name__)


def get_filters(
    note_type_filter: list[ExplanatoryNoteType] = None,
    section_type_filter: list[ExplanatoryNoteSectionType] = None,
    legislation_id: str = None,
) -> list:
    """Returns Qdrant filter conditions for the query."""
    conditions = []

    if legislation_id:
        conditions.append(
            FieldCondition(key="legislation_id", match=MatchValue(value=legislation_id))
        )

    if note_type_filter and len(note_type_filter) > 0:
        note_type_values = [nt.value for nt in note_type_filter]
        conditions.append(FieldCondition(key="note_type", match=MatchAny(any=note_type_values)))

    if section_type_filter and len(section_type_filter) > 0:
        section_type_values = [st.value for st in section_type_filter]
        conditions.append(
            FieldCondition(key="section_type", match=MatchAny(any=section_type_values))
        )

    return conditions


async def search_explanatory_note(input: ExplanatoryNoteSearch) -> list[ExplanatoryNote]:
    """Search for explanatory notes using Qdrant hybrid search."""
    filter_conditions = get_filters(
        note_type_filter=input.note_type,
        section_type_filter=input.section_type,
        legislation_id=input.legislation_id,
    )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None

    if input.query and input.query.strip():
        # Generate hybrid embeddings
        dense, sparse = generate_hybrid_embeddings(input.query)

        # Hybrid search with RRF fusion
        results = qdrant_client.query_points(
            collection_name=EXPLANATORY_NOTE_COLLECTION,
            query=FusionQuery(fusion=Fusion.RRF),
            prefetch=[
                Prefetch(query=dense, using="dense", limit=input.size),
                Prefetch(query=sparse, using="sparse", limit=input.size),
            ],
            query_filter=query_filter,
            limit=input.size,
            with_payload=True,
        )
    else:
        # No query - just filter
        results = qdrant_client.query_points(
            collection_name=EXPLANATORY_NOTE_COLLECTION,
            query_filter=query_filter,
            limit=input.size,
            with_payload=True,
        )

    notes = [ExplanatoryNote(**point.payload) for point in results.points]

    return notes


async def get_explanatory_note_by_legislation_id(
    legislation_id: str,
    limit: int = 1000,
) -> list[ExplanatoryNote]:
    """Retrieve all explanatory notes for a specific legislation by ID.

    Uses scroll to get all notes for a legislation, ordered by the order field.
    """
    query_filter = Filter(
        must=[FieldCondition(key="legislation_id", match=MatchValue(value=legislation_id))]
    )

    # Use scroll to get all matching documents
    results, _ = qdrant_client.scroll(
        collection_name=EXPLANATORY_NOTE_COLLECTION,
        scroll_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    # Convert to ExplanatoryNote objects
    notes = [ExplanatoryNote(**point.payload) for point in results]

    # Sort by order field (Qdrant scroll doesn't support sorting)
    notes.sort(key=lambda n: n.order if n.order else 0)

    return notes


async def get_explanatory_note_by_section(
    legislation_id: str,
    section_number: int,
) -> ExplanatoryNote | None:
    """Retrieve a specific explanatory note section by legislation ID and section number."""
    query_filter = Filter(
        must=[
            FieldCondition(key="legislation_id", match=MatchValue(value=legislation_id)),
            FieldCondition(key="section_number", match=MatchValue(value=section_number)),
        ]
    )

    # Use scroll to get matching document
    results, _ = qdrant_client.scroll(
        collection_name=EXPLANATORY_NOTE_COLLECTION,
        scroll_filter=query_filter,
        limit=1,
        with_payload=True,
        with_vectors=False,
    )

    if not results:
        return None

    note = ExplanatoryNote(**results[0].payload)

    return note

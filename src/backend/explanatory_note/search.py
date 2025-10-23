from elasticsearch import AsyncElasticsearch

from backend.explanatory_note.models import ExplanatoryNoteSearch
from lex.explanatory_note.models import (
    ExplanatoryNote,
    ExplanatoryNoteSectionType,
    ExplanatoryNoteType,
)
from lex.settings import EXPLANATORY_NOTE_INDEX


def get_filters(
    note_type_filter: ExplanatoryNoteType = None,
    section_type_filter: ExplanatoryNoteSectionType = None,
    legislation_id: str = None,
) -> list[dict]:
    """Returns a list of filters based on the provided search criteria."""
    filter = []

    if legislation_id:
        filter.append({"term": {"legislation_id.keyword": legislation_id}})

    if note_type_filter:
        filter.append({"term": {"note_type.keyword": note_type_filter.value}})

    if section_type_filter:
        filter.append({"term": {"section_type.keyword": section_type_filter.value}})

    return filter


async def search_explanatory_note(
    input: ExplanatoryNoteSearch,
    es_client: AsyncElasticsearch,
) -> list[ExplanatoryNote]:
    """Perform semantic search for explanatory notes based on the provided search criteria."""
    filter = get_filters(
        note_type_filter=input.note_type,
        section_type_filter=input.section_type,
        legislation_id=input.legislation_id,
    )

    body = {
        "size": input.size,
    }

    # If query is provided, use semantic search; otherwise, use match_all with filters
    if input.query and input.query.strip():
        body["query"] = {
            "bool": {
                "must": [
                    {
                        "semantic": {
                            "field": "text",
                            "query": input.query,
                        }
                    }
                ],
                "filter": filter,
            }
        }
    else:
        # No query provided, just apply filters
        if filter:
            body["query"] = {
                "bool": {
                    "filter": filter,
                }
            }
        else:
            # No query and no filters, return all documents
            body["query"] = {"match_all": {}}

    res = await es_client.search(index=EXPLANATORY_NOTE_INDEX, body=body)

    notes = [ExplanatoryNote(**hit["_source"]) for hit in res["hits"]["hits"]]

    return notes


async def get_explanatory_note_by_legislation_id(
    legislation_id: str,
    es_client: AsyncElasticsearch,
    limit: int = 1000,
) -> list[ExplanatoryNote]:
    """Retrieve all explanatory notes for a specific legislation by ID.

    Performs an exact match query on the legislation_id field to find all
    explanatory notes belonging to a specific piece of legislation. Results are ordered
    by order field from smallest to largest.
    """
    query = {
        "query": {"term": {"legislation_id.keyword": legislation_id}},
        "sort": [{"order": {"order": "asc"}}],
        "size": limit,
    }

    res = await es_client.search(index=EXPLANATORY_NOTE_INDEX, body=query)

    notes = [ExplanatoryNote(**hit["_source"]) for hit in res["hits"]["hits"]]

    return notes


async def get_explanatory_note_by_section(
    legislation_id: str,
    section_number: int,
    es_client: AsyncElasticsearch,
) -> ExplanatoryNote | None:
    """Retrieve a specific explanatory note section by legislation ID and section number.

    Performs an exact match query on the legislation_id and section_number fields.
    """
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"legislation_id.keyword": legislation_id}},
                    {"term": {"section_number": section_number}},
                ]
            }
        }
    }

    res = await es_client.search(index=EXPLANATORY_NOTE_INDEX, body=query)

    if res["hits"]["total"]["value"] == 0:
        return None

    note = ExplanatoryNote(**res["hits"]["hits"][0]["_source"])

    return note

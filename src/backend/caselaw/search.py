from elasticsearch import AsyncElasticsearch

from backend.caselaw.models import (
    CaselawReferenceSearch,
    CaselawSearch,
    CaselawSectionSearch,
    ReferenceType,
)
from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.settings import CASELAW_INDEX, CASELAW_SECTION_INDEX


def get_filters(
    court_filter: list[Court] = None,
    division_filter: list[str] = None,
    year_from: int = None,
    year_to: int = None,
) -> list[dict]:
    """Returns a list of filters based on the provided search criteria.
    These filters are used in the Elasticsearch query.
    """
    filter = []

    if court_filter and len(court_filter) > 0:
        filter.append({"terms": {"court": [c.value for c in court_filter]}})

    if division_filter and len(division_filter) > 0:
        filter.append({"terms": {"division": [d.value for d in division_filter]}})

    if year_from:
        filter.append({"range": {"year": {"gte": year_from}}})

    if year_to:
        filter.append({"range": {"year": {"lte": year_to}}})

    return filter


async def caselaw_search(
    input: CaselawSearch,
    es_client: AsyncElasticsearch,
) -> list[Caselaw]:
    """Perform search for caselaw based on the provided search criteria.

    If a query is provided, performs a semantic or standard search based on is_semantic_search.
    If no query is provided, returns results based on filters only.
    """
    filter = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    body = {
        "size": input.size,
    }

    # If query is provided, use semantic or standard search; otherwise, use filters only
    if input.query and input.query.strip():
        if input.is_semantic_search:
            must = [
                {
                    "semantic": {
                        "field": "text",
                        "query": input.query,
                    }
                }
            ]
        else:
            must = [
                {
                    "multi_match": {
                        "query": input.query,
                        "fields": ["name", "cite_as"],
                    }
                }
            ]

        body["query"] = {
            "bool": {
                "must": must,
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

    res = await es_client.search(index=CASELAW_INDEX, body=body)

    cases = [Caselaw(**hit["_source"]) for hit in res["hits"]["hits"]]

    return cases


async def caselaw_section_search(
    input: CaselawSectionSearch, es_client: AsyncElasticsearch
) -> list[CaselawSection]:
    """Perform search for caselaw sections based on the provided search criteria.

    If a query is provided, performs a semantic search. Otherwise, returns results
    based on filters only.
    """

    filter = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    body = {
        "size": input.limit,
    }

    # If query is provided, use semantic search; otherwise, use filters only
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

    res = await es_client.search(index=CASELAW_SECTION_INDEX, body=body)

    sections = [CaselawSection(**hit["_source"]) for hit in res["hits"]["hits"]]

    return sections


async def caselaw_reference_search(
    input: CaselawReferenceSearch, es_client: AsyncElasticsearch
) -> list[Caselaw]:
    """Perform search for caselaw that references a specific case or legislation.

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
    filter = get_filters(
        court_filter=input.court,
        division_filter=input.division,
        year_from=input.year_from,
        year_to=input.year_to,
    )

    # Create the query body
    body = {
        "query": {
            "bool": {
                "must": [{"term": {reference_field: input.reference_id}}],
                "filter": filter,
            }
        },
        "size": input.size,
    }

    # Execute the search
    res = await es_client.search(index=CASELAW_INDEX, body=body)

    # Convert results to Caselaw objects
    cases = [Caselaw(**hit["_source"]) for hit in res["hits"]["hits"]]

    return cases

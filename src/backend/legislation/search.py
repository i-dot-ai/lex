import logging
import re

from elasticsearch import AsyncElasticsearch

from backend.legislation.models import (
    LegislationActSearch,
    LegislationFullText,
    LegislationFullTextLookup,
    LegislationLookup,
    LegislationSectionLookup,
    LegislationSectionSearch,
)
from lex.legislation.models import (
    Legislation,
    LegislationCategory,
    LegislationSection,
    LegislationType,
)
from lex.settings import LEGISLATION_INDEX, LEGISLATION_SECTION_INDEX, LEGISLATION_TYPE_MAPPING

logger = logging.getLogger(__name__)

"""
This code is a work in progress. There have been changes to the underlying data model which aren't yet reflected here.
"""


async def legislation_section_search(
    input: LegislationSectionSearch, es_client: AsyncElasticsearch
) -> list[LegislationSection]:
    """Search for legislation sections based on the provided search criteria."""

    sections = await elastic_search(
        es_client=es_client,
        index=LEGISLATION_SECTION_INDEX,
        search_query=input.query,
        is_semantic_search=True,
        category_selection=input.legislation_category,
        type_selection=input.legislation_type,
        year_from=input.year_from,
        year_to=input.year_to,
        legislation_id=input.legislation_id,
        size=input.size,
    )

    return sections


async def legislation_act_search(
    input: LegislationActSearch, es_client: AsyncElasticsearch
) -> list[Legislation]:
    """Search for legislation titles with extended filtering options."""

    results = await elastic_search_titles(
        es_client=es_client,
        index=LEGISLATION_INDEX,
        query=input.query,
        year_from=input.year_from,
        year_to=input.year_to,
        type_filter=input.legislation_type,
        limit=input.limit,
    )

    return results


def get_legislation_types(
    category_selection: LegislationCategory | None = None,
    type_selection: LegislationType | None = None,
) -> list[str] | None:
    """Returns a list of legislation types based on the type and subtype selection.

    Args:
        type_selection: The selected legislation type.
        category_selection: The selected legislation category.

    Returns:
        list[str]: The resulting list of legislation subtypes that should be used in the Elasticsearch query. If no selection is made, None is returned.
    """

    if type_selection:
        return [type_selection.value]
    elif category_selection:
        return LEGISLATION_TYPE_MAPPING[category_selection.value]
    else:
        return None


def get_filters(
    category_selection: LegislationCategory | None,
    type_selection: LegislationType | None,
    year_from: int,
    year_to: int,
    legislation_id: str = None,
) -> list[dict]:
    """Returns a list of filters based on the selected legislation types, subtypes, extents, year range.
    These filters are used in the Elasticsearch query.

    Args:
        category_selection: The selected legislation categories.
        type_selection: The selected legislation types.
        year_from: The starting year for filtering.
        year_to: The ending year for filtering.
        legislation_id: The specific legislation ID to filter by. If provided, this takes priority over other filters.

    Returns:
        list[dict]: The resulting list of filters for the Elasticsearch query.
    """
    # Priority filter - if legislation_id provided, use only it (most efficient)
    if legislation_id:
        return [{"term": {"legislation_id.keyword": legislation_id}}]

    legislation_types = (
        get_legislation_types(category_selection, type_selection)
        if category_selection or type_selection
        else None
    )

    filter = []
    if legislation_types:
        filter.append({"terms": {"legislation_type": legislation_types}})

    if year_from:
        filter.append({"range": {"legislation_year": {"gte": year_from}}})

    if year_to:
        filter.append({"range": {"legislation_year": {"lte": year_to}}})

    return filter


def search_query_to_elastic_query(search_query: str, fields: list[str]) -> dict:
    """Converts a search query to an Elasticsearch query.

    Uses a set of regular expressions to match the search query to a specific type of query. If no match is found, a multi_match query is used.

    Possible query types:
    - match_phrase: Matches a phrase with quotes. Example: "hereditary peers"
    - span_near: Matches two terms within a certain distance. Example: child WITHIN 10 OF schools
    - not_match: Matches a term that is not another term. Example: child NOT schools
    - span_not_near: Matches two terms that are not within a certain distance. Example: child NOT WITHIN 10 OF schools
    - multi_match: Matches the query on all fields.

    Args:
        search_query (str): The search query to convert.

    Returns:
        dict: The Elasticsearch query.
    """
    regex_filters = {
        "match_phrase": r'"(.+)"',
        "span_not_near": r"(.+) NOT WITHIN (\d+) OF (.+)",
        "not_match": r"(.+) NOT (.+)",
        "span_near": r"(.+) WITHIN (\d+) OF (.+)",
    }

    if search_query is None or search_query == "":
        return {"match_all": {}}

    for query_type, regex in regex_filters.items():
        match = re.match(regex, search_query)

        if match:
            if query_type == "match_phrase":
                elastic_query = {
                    "multi_match": {
                        "query": match.group(1),
                        "type": "phrase",
                        "fields": fields,
                    }
                }
            elif query_type == "not_match":
                elastic_query = {
                    "bool": {
                        "must": {
                            "multi_match": {
                                "query": match.group(1),
                                "type": "phrase",
                                "fields": fields,
                            }
                        },
                        "must_not": {
                            "multi_match": {
                                "query": match.group(2),
                                "type": "phrase",
                                "fields": fields,
                            }
                        },
                    }
                }
            elif query_type == "span_near":
                elastic_query = {"bool": {"should": []}}
                for field_name in fields:
                    elastic_query["bool"]["should"].append(
                        {
                            "span_near": {
                                "clauses": [
                                    {"span_term": {field_name: match.group(1)}},
                                    {"span_term": {field_name: match.group(3)}},
                                ],
                                "slop": match.group(2),
                                "in_order": True,
                            }
                        }
                    )
            elif query_type == "span_not_near":
                elastic_query = {"bool": {"should": []}}
                for field_name in fields:
                    elastic_query["bool"]["should"].append(
                        {
                            "span_not": {
                                "include": {"span_term": {field_name: match.group(1)}},
                                "exclude": {
                                    "span_near": {
                                        "clauses": [
                                            {"span_term": {field_name: match.group(1)}},
                                            {"span_term": {field_name: match.group(3)}},
                                        ],
                                        "slop": match.group(2),
                                        "in_order": False,
                                    }
                                },
                            }
                        }
                    )
            return elastic_query

    elastic_query = {"multi_match": {"query": search_query}}

    return elastic_query


async def elastic_search(
    es_client: AsyncElasticsearch,
    index: str,
    search_query: str = None,
    is_semantic_search: bool = False,
    category_selection: list[LegislationCategory] = None,
    type_selection: list[LegislationType] = None,
    year_from: int = None,
    year_to: int = None,
    legislation_id: str = None,
    size: int = 20,
    offset: int = 0,
) -> list[LegislationSection]:
    "Performs an Elasticsearch search query and returns the results."

    filter = get_filters(
        category_selection=category_selection,
        type_selection=type_selection,
        year_from=year_from,
        year_to=year_to,
        legislation_id=legislation_id,
    )

    body = {
        "from": offset,
        "size": size,
    }

    if not is_semantic_search and search_query:
        must = search_query_to_elastic_query(search_query)
        body["query"] = {"bool": {"must": must, "filter": filter}}

    elif is_semantic_search and search_query:
        body["query"] = {
            "bool": {
                "must": [
                    {
                        "semantic": {
                            "field": "text",
                            "query": search_query,
                        }
                    }
                ],
                "filter": filter,
            }
        }

    res = await es_client.search(index=index, body=body)

    sections = [LegislationSection(**x["_source"]) for x in res["hits"]["hits"]]

    return sections


async def elastic_search_titles(
    es_client: AsyncElasticsearch,
    index: str,
    query: str,
    year_from: int | None = None,
    year_to: int | None = None,
    type_filter: LegislationType | None = None,
    limit: int = 10,
) -> list[Legislation]:
    match_field = "title"

    body = {
        "query": {
            "bool": {
                "must": [],
                "filter": [],
            }
        },
        "size": limit,
    }

    # Only add match query if query is not empty
    if query and query.strip():
        body["query"]["bool"]["must"].append({"match": {match_field: query}})
    else:
        # If no query, use match_all to return all documents
        body["query"]["bool"]["must"].append({"match_all": {}})

    if type_filter:
        body["query"]["bool"]["filter"].append({"term": {"type": type_filter.value}})

    if year_from:
        body["query"]["bool"]["filter"].append({"range": {"year": {"gte": year_from}}})

    if year_to:
        body["query"]["bool"]["filter"].append({"range": {"year": {"lte": year_to}}})

    res = await es_client.search(index=index, body=body)

    legislation_metadatas = [Legislation(**x["_source"]) for x in res["hits"]["hits"]]

    return legislation_metadatas


async def legislation_lookup(
    input: LegislationLookup, es_client: AsyncElasticsearch
) -> Legislation | None:
    """Lookup legislation by exact type, year, and number.

    This function performs an exact match query on the legislation type,
    year, and number fields to find a specific piece of legislation.
    """
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"type": input.legislation_type.value}},
                    {"term": {"year": input.year}},
                    {"term": {"number": input.number}},
                ]
            }
        }
    }

    res = await es_client.search(index=LEGISLATION_INDEX, body=query)

    if res["hits"]["total"]["value"] == 0:
        return None

    legislation = Legislation(**res["hits"]["hits"][0]["_source"])

    return legislation


async def get_legislation_sections(
    input: LegislationSectionLookup, es_client: AsyncElasticsearch
) -> list[LegislationSection]:
    """Retrieve all sections of a specific legislation by legislation_id.

    Performs an exact match query on the legislation_id field to find all
    sections belonging to a specific piece of legislation. Results are ordered
    by section number.
    """
    query = {
        "query": {"term": {"legislation_id.keyword": input.legislation_id}},
        "sort": [{"number": {"order": "asc"}}],
        "size": input.limit,
    }

    res = await es_client.search(index=LEGISLATION_SECTION_INDEX, body=query)

    sections = [LegislationSection(**hit["_source"]) for hit in res["hits"]["hits"]]

    return sections


async def get_legislation_full_text(
    input: LegislationFullTextLookup, es_client: AsyncElasticsearch
) -> LegislationFullText:
    """Retrieve the full text of a legislation document by its ID.

    This function:
    1. Retrieves the legislation metadata by ID
    2. Retrieves sections and optionally schedules for the legislation using its ID
    3. Sorts provisions by type (sections first, then schedules) and number
    4. Concatenates all provision texts
    5. Returns the combined metadata and full text

    Args:
        input: LegislationFullTextLookup containing legislation_id and include_schedules flag

    Returns:
        LegislationFullText object containing metadata and concatenated text

    Raises:
        HTTPException: If legislation not found or provisions cannot be retrieved
    """
    # First get the legislation metadata
    query = {"query": {"term": {"id.keyword": input.legislation_id}}}

    legislation_res = await es_client.search(index=LEGISLATION_INDEX, body=query)

    if legislation_res["hits"]["total"]["value"] == 0:
        return None

    legislation = Legislation(**legislation_res["hits"]["hits"][0]["_source"])

    # Build the query for provisions based on include_schedules flag
    provision_types = ["section"]
    if input.include_schedules:
        provision_types.append("schedule")

    # Query for provisions (sections and optionally schedules) using legislation_id
    provision_query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"legislation_id.keyword": input.legislation_id}},
                    {"terms": {"provision_type": provision_types}},
                ]
            }
        },
        "sort": [
            {"provision_type": {"order": "asc"}},  # sections first, then schedules
            {"number": {"order": "asc"}},
        ],
        "size": 1000,  # Set a reasonably high limit to get all provisions
    }

    provisions_res = await es_client.search(index=LEGISLATION_SECTION_INDEX, body=provision_query)

    provisions = [LegislationSection(**hit["_source"]) for hit in provisions_res["hits"]["hits"]]

    # Concatenate all provision texts with appropriate formatting
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

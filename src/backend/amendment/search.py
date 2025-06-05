from elasticsearch import AsyncElasticsearch

from backend.amendment.models import AmendmentSearch, AmendmentSectionSearch
from lex.amendment.models import Amendment
from lex.settings import AMENDMENT_INDEX


async def search_amendments(
    input: AmendmentSearch, es_client: AsyncElasticsearch
) -> list[Amendment]:
    """Search for amendments at the legislation level."""

    if input.search_amended:
        # Search for amendments made to the legislation
        field = "changed_url.keyword"
    else:
        # Search for amendments made by the legislation
        field = "affecting_url.keyword"

    query = {"size": input.size, "query": {"match": {field: input.legislation_id}}}

    res = await es_client.search(index=AMENDMENT_INDEX, body=query)

    amendments = [Amendment(**hit["_source"]) for hit in res["hits"]["hits"]]

    return amendments


async def search_amendment_sections(
    input: AmendmentSectionSearch, es_client: AsyncElasticsearch
) -> list[Amendment]:
    """Search for amendments at the provision/section level."""

    if input.search_amended:
        # Search for amendments made to the provision
        field = "changed_provision_url.keyword"
    else:
        # Search for amendments made by the provision
        field = "affecting_provision_url.keyword"

    query = {"size": input.size, "query": {"match": {field: input.provision_id}}}

    res = await es_client.search(index=AMENDMENT_INDEX, body=query)

    amendments = [Amendment(**hit["_source"]) for hit in res["hits"]["hits"]]

    return amendments

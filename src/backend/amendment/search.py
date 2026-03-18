import logging

from qdrant_client.models import FieldCondition, Filter, MatchAny

from backend.amendment.models import AmendmentSearch, AmendmentSectionSearch
from lex.amendment.models import Amendment
from lex.core.qdrant_client import qdrant_client
from lex.core.uri import normalise_legislation_uri
from lex.settings import AMENDMENT_COLLECTION

logger = logging.getLogger(__name__)


async def search_amendments(input: AmendmentSearch) -> list[Amendment]:
    """Search for amendments at the legislation level."""

    if input.search_amended:
        # Search for amendments made to the legislation
        field = "changed_url"
    else:
        # Search for amendments made by the legislation
        field = "affecting_url"

    # Normalise input and match legacy https:// variant until migration completes.
    # TODO: Remove https_variant after running fix_uri_formats.py --apply on amendments
    normalised_id = normalise_legislation_uri(input.legislation_id)
    https_variant = normalised_id.replace("http://", "https://", 1)
    query_filter = Filter(
        must=[FieldCondition(key=field, match=MatchAny(any=[normalised_id, https_variant]))]
    )

    # Use scroll to get matching documents
    results, _ = qdrant_client.scroll(
        collection_name=AMENDMENT_COLLECTION,
        scroll_filter=query_filter,
        limit=input.size,
        with_payload=True,
        with_vectors=False,
    )

    amendments = [Amendment(**point.payload) for point in results]

    return amendments


async def search_amendment_sections(input: AmendmentSectionSearch) -> list[Amendment]:
    """Search for amendments at the provision/section level."""

    if input.search_amended:
        # Search for amendments made to the provision
        field = "changed_provision_url"
    else:
        # Search for amendments made by the provision
        field = "affecting_provision_url"

    # Normalise input and match legacy https:// variant until migration completes.
    # TODO: Remove https_variant after running fix_uri_formats.py --apply on amendments
    normalised_id = normalise_legislation_uri(input.provision_id)
    https_variant = normalised_id.replace("http://", "https://", 1)
    query_filter = Filter(
        must=[FieldCondition(key=field, match=MatchAny(any=[normalised_id, https_variant]))]
    )

    # Use scroll to get matching documents
    results, _ = qdrant_client.scroll(
        collection_name=AMENDMENT_COLLECTION,
        scroll_filter=query_filter,
        limit=input.size,
        with_payload=True,
        with_vectors=False,
    )

    amendments = [Amendment(**point.payload) for point in results]

    return amendments

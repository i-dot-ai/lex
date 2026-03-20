import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from qdrant_client.models import FieldCondition, Filter, MatchValue

from lex.core.qdrant_client import async_qdrant_client
from lex.settings import (
    AMENDMENT_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

router = APIRouter(tags=["stats"])
logger = logging.getLogger(__name__)

# Simple TTL cache for stats
_stats_cache: dict[str, Any] | None = None
_stats_cache_key: str = ""


async def _calculate_live_stats() -> dict[str, Any]:
    """Calculate live statistics from Qdrant collections concurrently."""
    pdf_filter = Filter(
        must=[FieldCondition(key="provenance_source", match=MatchValue(value="llm_ocr"))]
    )

    # Run all 6 count queries concurrently with approximate counts
    (
        legislation_count,
        sections_count,
        explanatory_count,
        amendments_count,
        pdf_legislation_count,
        pdf_sections_count,
    ) = await asyncio.gather(
        async_qdrant_client.count(collection_name=LEGISLATION_COLLECTION, exact=False),
        async_qdrant_client.count(collection_name=LEGISLATION_SECTION_COLLECTION, exact=False),
        async_qdrant_client.count(collection_name=EXPLANATORY_NOTE_COLLECTION, exact=False),
        async_qdrant_client.count(collection_name=AMENDMENT_COLLECTION, exact=False),
        async_qdrant_client.count(
            collection_name=LEGISLATION_COLLECTION, exact=False, count_filter=pdf_filter
        ),
        async_qdrant_client.count(
            collection_name=LEGISLATION_SECTION_COLLECTION, exact=False, count_filter=pdf_filter
        ),
    )

    return {
        "acts_and_sis": f"{legislation_count.count:,}",
        "provisions": f"{sections_count.count:,}",
        "explanatory_sections": f"{explanatory_count.count:,}",
        "amendments": f"{amendments_count.count:,}",
        "pdf_legislation": f"{pdf_legislation_count.count:,}",
        "pdf_provisions": f"{pdf_sections_count.count:,}",
        "last_updated": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    }


@router.get("/api/stats")
async def get_live_stats() -> dict[str, Any]:
    """Get live dataset statistics with 5-minute caching."""
    global _stats_cache, _stats_cache_key

    # Use current time rounded to 5-minute intervals as cache key
    now = datetime.now(timezone.utc)
    cache_key = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0).isoformat()

    if cache_key != _stats_cache_key or _stats_cache is None:
        _stats_cache = await _calculate_live_stats()
        _stats_cache_key = cache_key

    return _stats_cache

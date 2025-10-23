#!/usr/bin/env python3
"""
Migrate data from Elasticsearch to Qdrant.

This script:
1. Reads documents from Elasticsearch indices using scroll API
2. Extracts text and generates hybrid embeddings (dense + sparse)
3. Uploads to Qdrant collections with progress tracking
4. Supports checkpointing for resumable migrations
5. Provides detailed progress bars and statistics

Usage:
    python scripts/migrate_es_to_qdrant.py --collection legislation_section
    python scripts/migrate_es_to_qdrant.py --collection all
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List

from elasticsearch import Elasticsearch
from qdrant_client.models import PointStruct
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

# Load .env from project root with override to ensure correct values
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from lex.core.embeddings import (
    generate_hybrid_embeddings_batch,
    generate_sparse_embedding,
    generate_sparse_embeddings_batch,
)
from lex.core.qdrant_client import qdrant_client
from lex.settings import (
    AMENDMENT_COLLECTION,
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Namespace UUID for generating deterministic UUIDs from URIs
NAMESPACE_LEX = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# Mapping of Qdrant collections to Elasticsearch indices
COLLECTION_TO_INDEX = {
    LEGISLATION_COLLECTION: "lex-dev-legislation",  # Top-level Acts (NEW)
    LEGISLATION_SECTION_COLLECTION: "lex-dev-legislation-section",
    CASELAW_COLLECTION: "lex-dev-caselaw",
    CASELAW_SECTION_COLLECTION: "lex-dev-caselaw-section",
    EXPLANATORY_NOTE_COLLECTION: "lex-dev-explanatory-note",
    AMENDMENT_COLLECTION: "lex-dev-amendment",  # If exists
}

# Field containing the text to embed for each collection
TEXT_FIELD_MAP = {
    LEGISLATION_COLLECTION: None,  # Generate from title + description (no pre-existing embeddings)
    LEGISLATION_SECTION_COLLECTION: "text",
    CASELAW_COLLECTION: "text",
    CASELAW_SECTION_COLLECTION: "text",
    EXPLANATORY_NOTE_COLLECTION: "text",
    AMENDMENT_COLLECTION: None,  # Amendments don't have text/vectors
}

# ID field for each collection
ID_FIELD_MAP = {
    LEGISLATION_COLLECTION: "id",
    LEGISLATION_SECTION_COLLECTION: "id",
    CASELAW_COLLECTION: "id",
    CASELAW_SECTION_COLLECTION: "id",
    EXPLANATORY_NOTE_COLLECTION: "id",
    AMENDMENT_COLLECTION: "id",
}


def uri_to_uuid(uri: str) -> str:
    """Convert a URI to a deterministic UUID string."""
    return str(uuid.uuid5(NAMESPACE_LEX, uri))


def get_checkpoint_path(collection_name: str) -> Path:
    """Get the checkpoint file path for a collection."""
    checkpoint_dir = Path("data/migration_checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"{collection_name}.json"


def load_checkpoint(collection_name: str) -> Dict[str, Any]:
    """Load migration checkpoint if it exists."""
    checkpoint_path = get_checkpoint_path(collection_name)
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            return json.load(f)
    return {"migrated_count": 0, "last_id": None}


def save_checkpoint(collection_name: str, migrated_count: int, last_id: str = None):
    """Save migration checkpoint."""
    checkpoint_path = get_checkpoint_path(collection_name)
    with open(checkpoint_path, "w") as f:
        json.dump({"migrated_count": migrated_count, "last_id": last_id}, f)


def get_es_client() -> Elasticsearch:
    """Create Elasticsearch client."""
    # Try to get ES config from environment
    es_host = os.getenv("ELASTIC_HOST", "http://localhost:9200")
    es_api_key = os.getenv("ELASTIC_API_KEY")

    if es_api_key:
        return Elasticsearch(
            es_host,
            api_key=es_api_key,
        )
    else:
        return Elasticsearch(es_host)


def scroll_es_documents(
    es_client: Elasticsearch,
    index_name: str,
    batch_size: int = 100,
    start_after: str = None,
) -> Iterator[List[Dict[str, Any]]]:
    """
    Scroll through all documents in an Elasticsearch index.

    Args:
        es_client: Elasticsearch client
        index_name: Name of the index to scroll
        batch_size: Number of documents per batch
        start_after: Resume from this document ID

    Yields:
        Batches of documents
    """
    # Check if index exists
    if not es_client.indices.exists(index=index_name):
        logger.warning(f"Index {index_name} does not exist")
        return

    # Use traditional scroll API (more compatible than search_after with _id)
    query = {"match_all": {}}

    # Start with initial search (with retry on timeout)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = es_client.search(
                index=index_name,
                query=query,
                size=batch_size,
                scroll="5m",  # Keep scroll context for 5 minutes
            )
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to start scroll after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Search timeout (attempt {attempt + 1}/{max_retries}), retrying...")
            time.sleep(2**attempt)  # Exponential backoff

    scroll_id = response.get("_scroll_id")

    while True:
        hits = response["hits"]["hits"]

        if not hits:
            break

        # Extract source documents
        batch = []
        for hit in hits:
            doc = hit["_source"]
            # Add the _id as id if not present
            if "id" not in doc:
                doc["id"] = hit["_id"]
            batch.append(doc)

        yield batch

        # Get next batch using scroll (with retry on timeout)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = es_client.scroll(
                    scroll_id=scroll_id,
                    scroll="5m",
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to scroll after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Scroll timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                time.sleep(2**attempt)  # Exponential backoff

    # Clear scroll context
    if scroll_id:
        try:
            es_client.clear_scroll(scroll_id=scroll_id)
        except Exception as e:
            logger.warning(f"Failed to clear scroll context: {e}")


def extract_dense_embedding(text_value: Any) -> List[float]:
    """
    Extract dense embedding from Elasticsearch semantic_text field.

    Args:
        text_value: The text field value from Elasticsearch

    Returns:
        1024-dimensional dense embedding vector, or None if not found
    """
    if not text_value:
        return None

    # Handle dict format with inference.chunks structure
    if isinstance(text_value, dict):
        inference = text_value.get("inference", {})
        chunks = inference.get("chunks", [])

        if chunks and isinstance(chunks, list) and len(chunks) > 0:
            first_chunk = chunks[0]
            embeddings = first_chunk.get("embeddings")

            if embeddings and isinstance(embeddings, list):
                logger.debug(f"Extracted {len(embeddings)}-dimensional embedding from ES")
                return embeddings

    logger.warning("Could not extract embedding from text field")
    return None


def migrate_collection(
    collection_name: str,
    batch_size: int = 100,
    resume: bool = True,
    dry_run: bool = False,
):
    """
    Migrate a single collection from Elasticsearch to Qdrant.

    Uses UUID5 idempotency - duplicates are safely ignored by Qdrant upsert.
    Checks actual Qdrant count vs ES count to determine if migration needed.

    Args:
        collection_name: Name of the Qdrant collection
        batch_size: Number of documents to process per batch
        resume: Ignored (kept for compatibility)
        dry_run: If True, don't actually upload to Qdrant
    """
    index_name = COLLECTION_TO_INDEX.get(collection_name)
    if not index_name:
        logger.error(f"Unknown collection: {collection_name}")
        return

    text_field = TEXT_FIELD_MAP.get(collection_name)
    id_field = ID_FIELD_MAP.get(collection_name)

    logger.info(f"Starting migration: {index_name} → {collection_name}")
    logger.info(f"Text field: {text_field}, ID field: {id_field}")

    # Get ES client
    es_client = get_es_client()

    # Get ES count
    try:
        es_total = es_client.count(index=index_name)["count"]
        logger.info(f"Total documents in ES: {es_total:,}")
    except Exception as e:
        logger.error(f"Could not get ES count: {e}")
        return

    # Get Qdrant count
    try:
        qdrant_info = qdrant_client.get_collection(collection_name)
        qdrant_count = qdrant_info.points_count
        logger.info(f"Current documents in Qdrant: {qdrant_count:,}")
    except Exception as e:
        logger.error(f"Could not get Qdrant count: {e}")
        return

    # Check if already complete
    if qdrant_count >= es_total:
        logger.info(
            f"✓ Collection {collection_name} already complete ({qdrant_count:,} >= {es_total:,}), skipping"
        )
        return

    logger.info(
        f"Need to migrate: {es_total - qdrant_count:,} documents (will process all {es_total:,} relying on UUID idempotency)"
    )

    # Determine if we extract or generate embeddings
    if collection_name == LEGISLATION_COLLECTION:
        logger.info("Will GENERATE embeddings (legislation has no semantic_text in ES)")
    elif text_field:
        logger.info("Will EXTRACT embeddings from ES semantic_text field")
    else:
        logger.info("No embeddings (metadata only)")

    # Progress bar
    pbar = tqdm(
        total=es_total,
        desc=f"Migrating {collection_name}",
        unit="docs",
    )

    migrated_count = 0
    error_count = 0
    batch_points = []

    try:
        for batch_docs in scroll_es_documents(es_client, index_name, batch_size):
            # Process batch - different strategies based on collection type
            if collection_name == LEGISLATION_COLLECTION:
                # PARALLEL PROCESSING for legislation (generate new embeddings)
                try:
                    # Prepare all texts and metadata
                    texts_to_embed = []
                    doc_metadata = []  # Store (doc, doc_id, point_id) tuples

                    for doc in batch_docs:
                        doc_id = doc.get(id_field)
                        if not doc_id:
                            logger.warning(f"Document missing {id_field} field")
                            error_count += 1
                            continue

                        # Combine title + type + year + description into text for embedding
                        title = doc.get("title", "")
                        leg_type = doc.get("type", "")
                        year = doc.get("year", "")
                        description = doc.get("description", "")

                        combined_text = f"{title} - {leg_type} ({year})"
                        if description:
                            combined_text += f": {description}"

                        texts_to_embed.append(combined_text)
                        doc_metadata.append((doc, doc_id, uri_to_uuid(doc_id)))

                    # Generate ALL embeddings in parallel (50 concurrent workers)
                    logger.info(f"Generating {len(texts_to_embed)} embeddings in parallel...")
                    hybrid_embeddings = generate_hybrid_embeddings_batch(
                        texts_to_embed,
                        max_workers=50,  # 50 workers for 7200 RPM = ~120 req/s
                    )

                    # Build points with generated embeddings
                    for (doc, doc_id, point_id), (dense, sparse) in zip(
                        doc_metadata, hybrid_embeddings
                    ):
                        point = PointStruct(
                            id=point_id,
                            vector={"dense": dense, "sparse": sparse},
                            payload=doc,
                        )
                        batch_points.append(point)

                except Exception as e:
                    logger.error(f"Error processing legislation batch: {e}")
                    error_count += len(batch_docs)

            elif text_field:
                # EXTRACTION + BATCH SPARSE for other collections (extract dense from ES)
                texts_for_sparse = []
                doc_with_dense = []  # Store (doc, doc_id, point_id, dense) tuples

                for doc in batch_docs:
                    try:
                        doc_id = doc.get(id_field)
                        if not doc_id:
                            logger.warning(f"Document missing {id_field} field")
                            error_count += 1
                            continue

                        point_id = uri_to_uuid(doc_id)
                        text_value = doc.get(text_field)

                        if not text_value:
                            error_count += 1
                            continue

                        # Extract dense embedding from ES (don't regenerate!)
                        dense = extract_dense_embedding(text_value)

                        if dense is None:
                            logger.warning(f"Could not extract embedding for {doc_id}, skipping")
                            error_count += 1
                            continue

                        # Extract plain text for BM25 sparse embedding
                        if isinstance(text_value, dict):
                            plain_text = text_value.get("text", "")
                        else:
                            plain_text = str(text_value)

                        texts_for_sparse.append(plain_text)
                        doc_with_dense.append((doc, doc_id, point_id, dense))

                    except Exception as e:
                        logger.error(f"Error processing document {doc.get(id_field)}: {e}")
                        error_count += 1

                # Generate sparse embeddings in batch (fast, local BM25)
                if texts_for_sparse:
                    sparse_embeddings = generate_sparse_embeddings_batch(texts_for_sparse)

                    # Build points
                    for (doc, doc_id, point_id, dense), sparse in zip(
                        doc_with_dense, sparse_embeddings
                    ):
                        point = PointStruct(
                            id=point_id,
                            vector={"dense": dense, "sparse": sparse},
                            payload=doc,
                        )
                        batch_points.append(point)

            else:
                # NO VECTORS (e.g., amendments)
                for doc in batch_docs:
                    try:
                        doc_id = doc.get(id_field)
                        if not doc_id:
                            logger.warning(f"Document missing {id_field} field")
                            error_count += 1
                            continue

                        point_id = uri_to_uuid(doc_id)
                        point = PointStruct(
                            id=point_id,
                            vector={},
                            payload=doc,
                        )
                        batch_points.append(point)

                    except Exception as e:
                        logger.error(f"Error processing document {doc.get(id_field)}: {e}")
                        error_count += 1

            # Upload batch to Qdrant
            if batch_points and not dry_run:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        qdrant_client.upsert(
                            collection_name=collection_name,
                            points=batch_points,
                            wait=True,
                        )

                        migrated_count += len(batch_points)
                        pbar.update(len(batch_points))
                        batch_points = []
                        break  # Success, exit retry loop

                    except Exception as e:
                        error_type = type(e).__name__
                        error_str = str(e).lower()
                        is_timeout = (
                            "timeout" in error_str
                            or "WriteTimeout" in error_type
                            or "ResponseHandlingException" in error_type
                            or "timed out" in error_str
                        )

                        if attempt < max_retries - 1 and is_timeout:
                            wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                            logger.warning(
                                f"Timeout uploading batch (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s..."
                            )
                            time.sleep(wait_time)
                            continue

                        # Final failure or non-timeout error
                        logger.error(f"Error uploading batch: {error_type}: {e}")
                        if hasattr(e, "response"):
                            logger.error(f"Response: {e.response}")
                        if hasattr(e, "__dict__"):
                            logger.error(f"Error details: {e.__dict__}")
                        if batch_points:
                            logger.error(
                                f"First point in failed batch: id={batch_points[0].id}, payload keys={list(batch_points[0].payload.keys())}"
                            )

                        error_count += len(batch_points)
                        batch_points = []
                        break

            elif batch_points and dry_run:
                # In dry run mode, just count
                migrated_count += len(batch_points)
                pbar.update(len(batch_points))
                batch_points = []

    finally:
        pbar.close()

        # Upload any remaining points
        if batch_points and not dry_run:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    qdrant_client.upsert(
                        collection_name=collection_name,
                        points=batch_points,
                        wait=True,
                    )
                    migrated_count += len(batch_points)
                    break
                except Exception as e:
                    error_type = type(e).__name__
                    error_str = str(e).lower()
                    is_timeout = (
                        "timeout" in error_str
                        or "WriteTimeout" in error_type
                        or "ResponseHandlingException" in error_type
                        or "timed out" in error_str
                    )

                    if attempt < max_retries - 1 and is_timeout:
                        wait_time = (attempt + 1) * 5
                        logger.warning(
                            f"Timeout uploading final batch (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue

                    logger.error(f"Error uploading final batch: {error_type}: {e}")
                    error_count += len(batch_points)
                    break

    logger.info(f"Migration complete: {collection_name}")
    logger.info(f"  Processed in this run: {migrated_count:,} documents")
    logger.info(f"  Errors: {error_count:,}")

    # Verify final count in Qdrant
    if not dry_run:
        collection_info = qdrant_client.get_collection(collection_name)
        final_count = collection_info.points_count
        logger.info(f"  Final Qdrant count: {final_count:,}")
        logger.info(f"  ES count: {es_total:,}")
        if final_count >= es_total:
            logger.info(f"  ✓ Migration successful - counts match!")
        else:
            logger.warning(f"  ⚠ Missing {es_total - final_count:,} documents")


def main():
    parser = argparse.ArgumentParser(description="Migrate data from Elasticsearch to Qdrant")
    parser.add_argument(
        "--collection",
        type=str,
        default="all",
        help=f"Collection to migrate (or 'all'). Options: {', '.join(COLLECTION_TO_INDEX.keys())}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to process per batch (default: 100)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start from scratch, ignoring checkpoints",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually upload to Qdrant (for testing)",
    )

    args = parser.parse_args()

    # Determine which collections to migrate
    if args.collection == "all":
        collections = list(COLLECTION_TO_INDEX.keys())
    else:
        if args.collection not in COLLECTION_TO_INDEX:
            logger.error(f"Unknown collection: {args.collection}")
            logger.error(f"Valid options: {', '.join(COLLECTION_TO_INDEX.keys())}, all")
            sys.exit(1)
        collections = [args.collection]

    # Migrate each collection
    total_start = time.time()

    for collection in collections:
        start = time.time()
        migrate_collection(
            collection,
            batch_size=args.batch_size,
            resume=not args.no_resume,
            dry_run=args.dry_run,
        )
        elapsed = time.time() - start
        logger.info(f"Collection {collection} took {elapsed:.1f}s")
        logger.info("-" * 80)

    total_elapsed = time.time() - total_start
    logger.info(f"Total migration time: {total_elapsed:.1f}s ({total_elapsed / 60:.1f}m)")


if __name__ == "__main__":
    main()

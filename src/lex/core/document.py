import logging
import time
import uuid
from typing import Iterable, Iterator, Type, TypeVar

from pydantic import BaseModel
from qdrant_client.models import PointStruct

from lex.core.embeddings import generate_hybrid_embeddings
from lex.core.qdrant_client import qdrant_client

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Namespace UUID for generating deterministic UUIDs from URIs
NAMESPACE_LEX = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def uri_to_uuid(uri: str) -> str:
    """Convert a URI to a deterministic UUID string.

    Args:
        uri: The URI to convert (e.g., "http://www.legislation.gov.uk/id/ukpga/2024/21/section/1")

    Returns:
        UUID string generated from the URI
    """
    return str(uuid.uuid5(NAMESPACE_LEX, uri))


def documents_to_batches(documents: Iterable, batch_size: int):
    """Yield batches of documents."""
    batch = []
    for doc in documents:
        batch.append(doc)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def generate_documents(source_documents: Iterable, target_model: Type[T]) -> Iterator[T]:
    """Generate pydantic documents from source documents.

    Args:
        source_documents: Source documents to convert
        target_model: Target pydantic model class

    Returns:
        Iterator of documents of the target model type
    """
    for doc in source_documents:
        try:
            if doc is None:
                continue
            if isinstance(doc, dict):
                yield target_model(**doc)
            elif isinstance(doc, BaseModel):
                yield target_model(**doc.model_dump())
            else:
                # Try direct conversion
                yield target_model.model_validate(doc)
        except Exception as e:
            logger.error(f"Error generating document: {e}", exc_info=True)
            continue


def upload_documents(
    collection_name: str,
    documents: Iterable[BaseModel],
    batch_size: int = 20,
    id_field: str = "id",
    embedding_fields: list[str] | None = None,
    safe: bool = True,
    batches_per_log: int = 10,
    max_retries: int = 5,
    retry_delay: float = 10.0,
):
    """Upload documents to Qdrant with hybrid embeddings.

    Args:
        collection_name: Name of the Qdrant collection
        documents: Iterable of Pydantic models to upload
        batch_size: Number of documents per batch
        id_field: Field to use as document ID
        embedding_fields: Fields to concatenate for embedding. If None, uses "text" field
        safe: If True, continue on errors; if False, raise exceptions
        batches_per_log: Log progress every N batches
        max_retries: Maximum number of retries for connection errors
        retry_delay: Initial delay between retries (seconds)
    """
    logger.info(f"Starting upload to collection {collection_name} with batch size {batch_size}")

    # Default to "text" field if no embedding_fields specified
    if embedding_fields is None:
        embedding_fields = ["text"]

    # Convert documents to dicts
    documents = list(doc.model_dump() for doc in documents)
    batch_generator = documents_to_batches(documents, batch_size)
    docs_uploaded = 0
    connection_errors = 0

    for i, batch in enumerate(batch_generator):
        if i % batches_per_log == 0 and i != 0:
            logger.info(f"Uploaded {docs_uploaded} documents to collection {collection_name}")

        # Retry logic for connection errors
        for retry_attempt in range(max_retries):
            try:
                # Generate embeddings and create points
                points = []
                for doc in batch:
                    doc_id = doc.get(id_field)

                    # Build text from specified fields
                    text_parts = []
                    for field in embedding_fields:
                        value = doc.get(field, "")
                        if value:
                            text_parts.append(str(value))

                    text = " ".join(text_parts)

                    if not text:
                        logger.warning(
                            f"Document {doc_id} has no content in embedding fields {embedding_fields}, skipping",
                            extra={"doc_id": doc_id, "collection": collection_name, "embedding_fields": embedding_fields},
                        )
                        continue

                    # Generate hybrid embeddings
                    dense, sparse = generate_hybrid_embeddings(text)

                    # Convert URI to UUID for Qdrant compatibility
                    point_id = uri_to_uuid(doc_id)

                    # Create point with both dense and sparse vectors
                    point = PointStruct(
                        id=point_id,
                        vector={"dense": dense, "sparse": sparse},
                        payload=doc,  # All fields as metadata
                    )
                    points.append(point)

                # Batch upload to Qdrant
                if points:
                    qdrant_client.upsert(
                        collection_name=collection_name, points=points, wait=True  # Wait for indexing
                    )
                    docs_uploaded += len(points)

                connection_errors = 0  # Reset on success
                break  # Success, exit retry loop

            except Exception as e:
                connection_errors += 1
                current_delay = retry_delay * (2**retry_attempt)

                logger.warning(
                    f"Qdrant connection error (attempt {retry_attempt + 1}/{max_retries}): {e}",
                    extra={
                        "retry_attempt": retry_attempt + 1,
                        "max_retries": max_retries,
                        "wait_time": current_delay,
                        "batch_number": i,
                        "connection_errors": connection_errors,
                        "error_type": type(e).__name__,
                    },
                )

                if retry_attempt < max_retries - 1:
                    logger.info(f"Waiting {current_delay}s before retrying...")
                    time.sleep(current_delay)
                else:
                    logger.error(
                        f"Failed to upload batch after {max_retries} attempts",
                        extra={
                            "batch_number": i,
                            "batch_size": len(batch),
                            "total_connection_errors": connection_errors,
                        },
                    )
                    if not safe:
                        raise e

    logger.info(
        f"Upload complete: {docs_uploaded} documents uploaded to collection {collection_name}",
        extra={
            "total_uploaded": docs_uploaded,
            "collection_name": collection_name,
            "total_connection_errors": connection_errors,
        },
    )

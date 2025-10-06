import logging
import time
from typing import Iterable, Iterator, Type, TypeVar

from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ConnectionError, ConnectionTimeout, TransportError
from pydantic import BaseModel

from lex.core.clients import es_client

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


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
                # Convert model to dict then to target model
                yield target_model(**doc.model_dump())
            else:
                # Try direct conversion
                yield target_model.model_validate(doc)
        except Exception as e:
            logger.error(f"Error generating document: {e}", exc_info=True)
            continue


def upload_documents(
    index_name: str,
    documents: Iterable[BaseModel],
    batch_size: int = 20,
    id_field: str = "id",
    safe: bool = True,
    es_client: Elasticsearch = es_client,
    batches_per_log: int = 10,
    max_retries: int = 5,
    retry_delay: float = 10.0,
):
    """Upload documents to Elasticsearch with connection retry logic.

    Args:
        index_name: Name of the Elasticsearch index
        documents: Iterable of Pydantic models to upload
        batch_size: Number of documents per batch
        id_field: Field to use as document ID
        safe: If True, continue on errors; if False, raise exceptions
        es_client: Elasticsearch client instance
        batches_per_log: Log progress every N batches
        max_retries: Maximum number of retries for connection errors
        retry_delay: Initial delay between retries (seconds)
    """
    logger.info(f"Starting upload to index {index_name} with batch size {batch_size}")

    documents = (doc.model_dump() for doc in documents)

    batch_generator = documents_to_batches(documents, batch_size)
    docs_uploaded = 0
    connection_errors = 0

    for i, batch in enumerate(batch_generator):
        body = [
            {"_index": index_name, "_id": doc.get(id_field, None), "_source": doc} for doc in batch
        ]

        if i % batches_per_log == 0 and i != 0:
            logger.info(f"Uploaded {docs_uploaded} documents to index {index_name}")

        # Retry logic for connection errors
        for retry_attempt in range(max_retries):
            try:
                # Use helpers.bulk with its own retry logic for document-level errors
                success, failed = helpers.bulk(
                    es_client, body, max_retries=3, raise_on_error=False, raise_on_exception=False
                )

                # Check if there were any failures
                if failed:
                    # Extract detailed error information
                    error_details = []
                    for item in failed[:5]:  # Log first 5 failures
                        if 'error' in item.get('index', {}):
                            error = item['index']['error']
                            error_details.append({
                                'type': error.get('type'),
                                'reason': error.get('reason'),
                                'doc_id': item['index'].get('_id')
                            })
                    
                    logger.warning(
                        f"Failed to upload {len(failed)} documents in batch {i}. Errors: {error_details}",
                        extra={
                            "batch_number": i,
                            "failed_count": len(failed),
                            "errors": error_details,
                            "first_full_error": failed[0] if failed else None,
                        },
                    )

                docs_uploaded += success
                connection_errors = 0  # Reset on success
                break  # Success, exit retry loop

            except (ConnectionError, ConnectionTimeout, TransportError) as e:
                connection_errors += 1
                current_delay = retry_delay * (2**retry_attempt)  # Exponential backoff

                logger.warning(
                    f"Elasticsearch connection error (attempt {retry_attempt + 1}/{max_retries}): {e}",
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
                    # Wait before retrying
                    logger.info(f"Waiting {current_delay}s before retrying...")
                    time.sleep(current_delay)

                    # Check if ES is healthy before retrying
                    try:
                        health = es_client.cluster.health(timeout="5s")
                        logger.info(
                            f"Elasticsearch cluster status: {health['status']}",
                            extra={"cluster_health": health},
                        )
                    except Exception as health_error:
                        logger.error(f"Failed to check cluster health: {health_error}")
                else:
                    # Final retry failed
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

            except Exception as e:
                # Non-connection errors
                logger.error(
                    f"Error uploading documents: {e}",
                    extra={
                        "error_type": type(e).__name__,
                        "batch_number": i,
                        "batch_size": len(batch),
                    },
                )
                if not safe:
                    raise e

    logger.info(
        f"Upload complete: {docs_uploaded} documents uploaded to index {index_name}",
        extra={
            "total_uploaded": docs_uploaded,
            "index_name": index_name,
            "total_connection_errors": connection_errors,
        },
    )


def update_documents(
    index_name: str,
    documents: Iterable[BaseModel],
    batch_size: int = 20,
    id_field: str = "id",
    es_client: Elasticsearch = es_client,
    batches_per_log: int = 10,
    max_retries: int = 5,
    retry_delay: float = 10.0,
):
    """Bulk updates sections in an Elasticsearch index with connection retry logic.

    Will only update the fields that are present in the document and leave the rest unchanged.
    """
    documents = (doc.model_dump() for doc in documents)

    batch_generator = documents_to_batches(documents, batch_size)
    docs_uploaded = 0
    connection_errors = 0

    for i, batch in enumerate(batch_generator):
        body = list(
            {
                "_op_type": "update",
                "_index": index_name,
                "_id": doc[id_field],
                "doc": doc,
                "doc_as_upsert": True,
            }
            for doc in batch
        )

        # Retry logic for connection errors
        for retry_attempt in range(max_retries):
            try:
                success, failed = helpers.bulk(
                    es_client, body, max_retries=3, raise_on_error=False, raise_on_exception=False
                )

                if failed:
                    logger.warning(
                        f"Failed to update {len(failed)} documents in batch {i}",
                        extra={
                            "batch_number": i,
                            "failed_count": len(failed),
                            "first_error": failed[0] if failed else None,
                        },
                    )

                docs_uploaded += success
                connection_errors = 0  # Reset on success
                break  # Success, exit retry loop

            except (ConnectionError, ConnectionTimeout, TransportError) as e:
                connection_errors += 1
                current_delay = retry_delay * (2**retry_attempt)  # Exponential backoff

                logger.warning(
                    f"Elasticsearch connection error during update (attempt {retry_attempt + 1}/{max_retries}): {e}",
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
                    logger.error(f"Failed to update batch after {max_retries} attempts")
                    # Continue to next batch instead of failing completely

            except Exception:
                logger.error("Error updating documents", exc_info=True)

        if i % batches_per_log == 0 and i != 0:
            logger.info(f"Updated {docs_uploaded} documents in index {index_name}")

    logger.info(
        f"Update complete: {docs_uploaded} documents updated in index {index_name}",
        extra={
            "total_updated": docs_uploaded,
            "index_name": index_name,
            "total_connection_errors": connection_errors,
        },
    )

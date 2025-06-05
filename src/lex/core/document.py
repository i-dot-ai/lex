import logging
from typing import Iterable, Iterator, Type, TypeVar

from elasticsearch import Elasticsearch, helpers
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
):
    documents = (doc.model_dump() for doc in documents)

    batch_generator = documents_to_batches(documents, batch_size)
    docs_uploaded = 0

    for i, batch in enumerate(batch_generator):
        body = [
            {"_index": index_name, "_id": doc.get(id_field, None), "_source": doc} for doc in batch
        ]

        if i % batches_per_log == 0 and i != 0:
            logger.info(f"Uploaded {docs_uploaded} documents to index {index_name}")

        try:
            helpers.bulk(es_client, body, max_retries=3)
            docs_uploaded += len(batch)
        except Exception as e:
            logger.error(f"Error uploading documents: {e}")
            if not safe:
                raise e

    logger.info(f"Uploaded {docs_uploaded} documents to index {index_name}")


def update_documents(
    index_name: str,
    documents: Iterable[BaseModel],
    batch_size: int = 20,
    id_field: str = "id",
    es_client: Elasticsearch = es_client,
    batches_per_log: int = 10,
):
    """Bulk updates sections in an Elasticsearch index. Will only update the fields that are present in the document and leave the rest unchanged."""

    documents = (doc.model_dump() for doc in documents)

    batch_generator = documents_to_batches(documents, batch_size)
    docs_uploaded = 0

    for i, batch in enumerate(batch_generator):
        body = (
            {
                "_op_type": "update",
                "_index": index_name,
                "_id": doc[id_field],
                "doc": doc,
                "doc_as_upsert": True,
            }
            for doc in batch
        )

        try:
            success, failed = helpers.bulk(es_client, body, max_retries=3)
            docs_uploaded += len(batch)
        except Exception as e:
            logger.error("Error updating documents", exc_info=e)

        if i % batches_per_log == 0:
            logger.info(f"Updated {docs_uploaded} documents in index {index_name}")

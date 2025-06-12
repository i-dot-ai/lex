import logging
import os
from typing import Optional

from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch, NotFoundError

from lex.core.clients import es_client

logger = logging.getLogger(__name__)


def set_logging_level(
    level: int,
    elastic_client: Optional[Elasticsearch] = None,
    elastic_index: Optional[str] = None,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
) -> None:
    """Set logging level for all lex loggers and optionally set up Elasticsearch logging.

    Args:
        level: The logging level to set
        elastic_client: Optional Elasticsearch client for logging to Elasticsearch
        elastic_index: Name of the Elasticsearch index to use for logs
        service_name: Name of the service (e.g., "frontend", "pipeline")
        environment: Environment name (e.g., "localhost", "dev", "prod")
    """
    # Set the log level for all lex loggers
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        if "lex" in logger.name or "backend" in logger.name or "__main__" == logger.name:
            logger.setLevel(level)

    # Configure basic logging format
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Set up Elasticsearch logging if client is provided
    if elastic_client and elastic_index and service_name and environment:
        from backend.core.logging import setup_elasticsearch_logging

        setup_elasticsearch_logging(
            es_client=elastic_client,
            index_name=elastic_index,
            service_name=service_name,
            environment=environment,
            log_level=level,
        )


def create_index_if_none(
    index_name: str,
    mappings: dict | str = None,
    es_client: Elasticsearch = es_client,
    non_interactive: bool = False,
):
    "Creates an index in Elasticsearch if it does not already exist"

    logger.info(f"Creating index {index_name}")

    if not es_client.indices.exists(index=index_name):
        # If the mapping is a string, get the mapping of the index it points towards
        if isinstance(mappings, str):
            mappings = es_client.indices.get_mapping(index=mappings)[mappings]["mappings"]
            logger.info(f"Using mapping from index {mappings}")

        es_client.indices.create(index=index_name, body=mappings)
        logger.info(f"Created index {index_name}")
    elif not non_interactive:
        logger.info(f"Index {index_name} already exists")
        user_input = input("Do you want to continue? [y/N] ")
        if user_input.lower() != "y":
            logger.info("Exiting")
            exit(0)
    else:
        logger.info(f"Index {index_name} already exists. Continuing")


def create_inference_endpoint(
    inference_id: str,
    es_client: Elasticsearch = es_client,
    task_type: str = "text_embedding",
    service: str = "azureopenai",
) -> dict:
    """
    Create an inference endpoint in Elasticsearch.

    Args:
        inference_id (str): The ID for the inference endpoint
        task_type (str): The type of task (default: "text_embedding")
        service (str): The service to use (default: "azureopenai")
        service_settings (dict): Configuration for the service

    Returns:
        dict: The response from Elasticsearch
    """

    service_settings = {
        "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "resource_name": os.getenv("AZURE_RESOURCE_NAME"),
        "deployment_id": os.getenv("AZURE_OPENAI_EMBEDDING_MODEL"),
        "api_version": os.getenv("OPENAI_API_VERSION"),
        "dimensions": 1024,
    }

    chunking_settings = {
        "max_chunk_size": 300,
        "sentence_overlap": 0,
        "strategy": "sentence",
    }

    try:
        response = es_client.inference.put(
            inference_id=inference_id,
            task_type=task_type,
            inference_config={
                "service": service,
                "service_settings": service_settings,
                "chunking_settings": chunking_settings,
            },
        )
        return response
    except Exception as e:
        logger.error(f"Error creating inference endpoint: {e}")
        raise


def create_inference_endpoint_if_none(
    inference_id: str,
    task_type: str = "text_embedding",
    es_client: Elasticsearch = es_client,
    service: str = "azureopenai",
) -> dict:
    """
    Create an inference endpoint in Elasticsearch if it does not already exist.

    Args:
        es_client (Elasticsearch): The Elasticsearch client
        inference_id (str): The ID for the inference endpoint
        task_type (str): The type of task (default: "text_embedding")
        service (str): The service to use (default: "azureopenai")
        non_interactive (bool): If True, skip user confirmation (default: False)

    Returns:
        dict: The response from Elasticsearch
    """
    logger.info(f"Creating inference endpoint {inference_id}")

    # Check for required Azure OpenAI environment variables
    required_vars = ["AZURE_RESOURCE_NAME", "AZURE_OPENAI_EMBEDDING_MODEL", "AZURE_OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.warning(
            f"Skipping inference endpoint creation because the following environment variables are missing: {', '.join(missing_vars)}. "
            f"Please set these variables in your environment or .env file."
        )
        return None

    try:
        # Check if the inference endpoint exists
        es_client.inference.get(inference_id=inference_id)
        logger.info(f"Inference endpoint {inference_id} already exists")
        return es_client.inference.get(inference_id=inference_id)
    except NotFoundError:
        # Endpoint doesn't exist, create it
        try:
            return create_inference_endpoint(
                es_client=es_client,
                inference_id=inference_id,
                task_type=task_type,
                service=service,
            )
        except Exception as e:
            logger.error(f"Failed to create inference endpoint: {e}")
            logger.warning(
                "Continuing without inference endpoint. Some features may not work properly."
            )
            return None


def delete_inference_endpoint(inference_id: str, es_client: Elasticsearch = es_client) -> dict:
    """
    Delete an inference endpoint by its ID.

    Args:
        inference_id (str): The ID of the inference endpoint to delete

    Returns:
        dict: The response from Elasticsearch
    """
    try:
        response = es_client.inference.delete(inference_id=inference_id)
        return response
    except NotFoundError as e:
        logger.info(f"Inference endpoint {inference_id} not found: {e}")


def scroll_index(
    es_client: Elasticsearch,
    index_name: str,
    fields: list[str] = None,
    scroll_size: int = 1000,
    scroll_time: str = "1m",
):
    """
    Generator function to iterate through all documents in an Elasticsearch index using the scroll API.
    """
    # Initial search request

    if not fields:
        body = {"query": {"match_all": {}}, "size": scroll_size}
    else:
        body = {"query": {"match_all": {}}, "size": scroll_size, "_source": fields}

    resp = es_client.search(
        index=index_name,
        body=body,
        scroll=scroll_time,
    )

    # Get the scroll ID
    scroll_id = resp["_scroll_id"]
    hits = resp["hits"]["hits"]

    # Yield the initial batch of documents
    for hit in hits:
        yield hit

    # Continue scrolling until no more hits are returned
    count = len(hits)
    while len(hits) > 0:
        logger.info(f"Scrolling {len(hits)} hits, total hits: {count}")
        resp = es_client.scroll(scroll_id=scroll_id, scroll=scroll_time)
        scroll_id = resp["_scroll_id"]
        hits = resp["hits"]["hits"]

        for hit in hits:
            yield hit

        count += len(hits)

    # Clear the scroll context when done
    es_client.clear_scroll(scroll_id=scroll_id)


def load_xml_file_to_soup(filepath: str) -> BeautifulSoup:
    """Load an XML file and return a BeautifulSoup object."""
    with open(filepath, "r") as f:
        return BeautifulSoup(f.read(), "xml")


def parse_years(years_input):
    """
    Parse years input that can contain individual years or ranges.

    Args:
        years_input: List of strings that can be individual years or ranges like "2020-2025"

    Returns:
        List of integers representing all years

    Examples:
        parse_years(["2020", "2022"]) -> [2020, 2022]
        parse_years(["2020-2022"]) -> [2020, 2021, 2022]
        parse_years(["2020-2022", "2025"]) -> [2020, 2021, 2022, 2025]
    """
    if years_input is None:
        return None

    all_years = []

    for year_item in years_input:
        year_str = str(year_item)

        if "-" in year_str:
            # Handle range like "2020-2025"
            try:
                start_year, end_year = year_str.split("-")
                start_year = int(start_year)
                end_year = int(end_year)

                if start_year > end_year:
                    raise ValueError(
                        f"Invalid year range: {year_str}. Start year must be <= end year."
                    )

                # Generate all years in the range (inclusive)
                range_years = list(range(start_year, end_year + 1))
                all_years.extend(range_years)

            except ValueError as e:
                if "Invalid year range" in str(e):
                    raise e
                else:
                    raise ValueError(
                        f"Invalid year range format: {year_str}. Use format like '2020-2025'."
                    )
        else:
            # Handle individual year
            try:
                all_years.append(int(year_str))
            except ValueError:
                raise ValueError(f"Invalid year: {year_str}. Must be a valid integer.")

    # Remove duplicates and sort
    return sorted(list(set(all_years)))

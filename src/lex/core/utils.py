import logging
import os
from typing import Optional

from bs4 import BeautifulSoup

from lex.core.qdrant_client import qdrant_client

logger = logging.getLogger(__name__)


def set_logging_level(
    level: int,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
) -> None:
    """Set logging level for all lex loggers.

    Args:
        level: The logging level to set
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


def create_collection_if_none(
    collection_name: str,
    schema: dict = None,
    non_interactive: bool = False,
):
    """Creates a collection in Qdrant if it does not already exist.

    Args:
        collection_name: Name of the Qdrant collection
        schema: Collection schema dict with vectors_config and sparse_vectors_config
        non_interactive: If True, skip user confirmation for existing collections
    """
    logger.info(f"Checking if collection {collection_name} exists")

    # Check if collection exists
    collections = qdrant_client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)

    if not exists:
        if schema is None:
            logger.error(f"Cannot create collection {collection_name}: schema is required")
            raise ValueError(f"Schema required to create collection {collection_name}")

        logger.info(f"Creating collection {collection_name}")
        qdrant_client.create_collection(**schema)
        logger.info(f"Created collection {collection_name}")
    elif not non_interactive:
        logger.info(f"Collection {collection_name} already exists")
        user_input = input("Do you want to continue? [y/N] ")
        if user_input.lower() != "y":
            logger.info("Exiting")
            exit(0)
    else:
        logger.info(f"Collection {collection_name} already exists. Continuing")




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

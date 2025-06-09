"""Base analyzer class for connecting to Elasticsearch and running queries."""

import os
import sys
from datetime import datetime
from typing import Dict, List, Any
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from common_utils import extract_year_from_message, extract_legislation_type

load_dotenv()

# Add the parent directory to the Python path to import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lex.core.clients import get_elasticsearch_client


def get_output_path(filename: str) -> str:
    """Get the correct output path for a file, handling both root and analysis directory execution."""
    # Check if we're already in the analysis directory
    if os.path.basename(os.getcwd()) == "analysis":
        return filename
    else:
        return os.path.join("analysis", filename)


class BaseAnalyzer:
    """Base class for log analysis with Elasticsearch connection."""

    def __init__(self, index_name: str = "logs-pipeline"):
        """Initialize connection to Elasticsearch."""
        self.index_name = index_name
        self.es = get_elasticsearch_client()

    def test_connection(self) -> bool:
        """Test if Elasticsearch connection is working."""
        try:
            info = self.es.info()
            print(f"Connected to Elasticsearch {info['version']['number']}")
            return True
        except Exception as e:
            print(f"Failed to connect to Elasticsearch: {e}")
            return False

    def get_total_logs(self) -> int:
        """Get total number of log entries."""
        result = self.es.count(index=self.index_name)
        return result["count"]

    def search_logs(self, query: Dict[str, Any], size: int = 10000) -> List[Dict]:
        """Execute a search query and return results."""
        # Add size to query if not already present
        if "size" not in query:
            query["size"] = size

        response = self.es.search(index=self.index_name, body=query)
        return [hit["_source"] for hit in response["hits"]["hits"]]

    def aggregate_logs(self, agg_query: Dict[str, Any]) -> Dict:
        """Execute an aggregation query and return results."""
        response = self.es.search(
            index=self.index_name,
            body=agg_query,
            size=0,  # We only want aggregations, not individual documents
        )
        return response["aggregations"]

    def extract_year_from_message(self, message: str) -> int:
        """Extract year from log message if possible."""
        return extract_year_from_message(message)

    def extract_type_from_message(self, message: str) -> str:
        """Extract legislation type from log message if possible."""
        return extract_legislation_type(message)

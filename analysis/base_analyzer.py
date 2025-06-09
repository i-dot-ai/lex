"""Base analyzer class for connecting to Elasticsearch and running queries."""

import os
from datetime import datetime
from typing import Dict, List, Any
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from common_utils import extract_year_from_message, extract_legislation_type

load_dotenv()


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
        self.es = self._get_client()

    def _get_client(self) -> Elasticsearch:
        """Get Elasticsearch client with proper configuration."""
        # Use localhost as specified
        es_host = "http://localhost:9200"

        # Check if we need authentication
        username = os.getenv("ELASTIC_USERNAME", "")
        password = os.getenv("ELASTIC_PASSWORD", "")

        if username and password:
            return Elasticsearch([es_host], basic_auth=(username, password), verify_certs=False)
        else:
            return Elasticsearch([es_host])

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

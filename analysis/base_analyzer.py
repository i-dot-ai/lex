"""Base analyzer class for connecting to Elasticsearch and running queries."""

import os
from datetime import datetime
from typing import Dict, List, Any
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()


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
            return Elasticsearch(
                [es_host],
                basic_auth=(username, password),
                verify_certs=False
            )
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
        response = self.es.search(
            index=self.index_name,
            body=query,
            size=size
        )
        return [hit["_source"] for hit in response["hits"]["hits"]]
    
    def aggregate_logs(self, agg_query: Dict[str, Any]) -> Dict:
        """Execute an aggregation query and return results."""
        response = self.es.search(
            index=self.index_name,
            body=agg_query,
            size=0  # We only want aggregations, not individual documents
        )
        return response["aggregations"]
    
    def extract_year_from_message(self, message: str) -> int:
        """Extract year from log message if possible."""
        # Look for patterns like /1963/ or year=1963
        import re
        
        # Try to find 4-digit year in message
        year_patterns = [
            r'/(\d{4})/',  # URL pattern
            r'year[=:]\s*(\d{4})',  # year=YYYY or year: YYYY
            r'\b(19\d{2}|20\d{2})\b'  # Any 4-digit year from 1900s or 2000s
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def extract_type_from_message(self, message: str) -> str:
        """Extract legislation type from log message if possible."""
        # Known legislation types
        types = [
            "ukpga", "asp", "asc", "anaw", "wsi", "uksi", "ssi", "ukcm", 
            "nisr", "nia", "eudn", "eudr", "eur", "ukla", "ukppa", "apni",
            "gbla", "aosp", "aep", "apgb", "mwa", "aip", "mnia", "nisro",
            "nisi", "uksro", "ukmo", "ukci"
        ]
        
        message_lower = message.lower()
        for leg_type in types:
            if f"/{leg_type}/" in message_lower or f"type={leg_type}" in message_lower:
                return leg_type
        
        return None
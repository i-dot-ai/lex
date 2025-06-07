"""Check pipeline status and why it stopped at 1971."""

from base_analyzer import BaseAnalyzer
from datetime import datetime
import json


class PipelineStatusChecker(BaseAnalyzer):
    """Check pipeline execution status and parameters."""
    
    def __init__(self):
        super().__init__()
    
    def get_pipeline_start_logs(self):
        """Find logs indicating pipeline start with parameters."""
        
        # Look for pipeline start messages
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Starting pipeline"}},
                        {"match": {"message": "args"}},
                        {"match": {"message": "Processing"}},
                        {"match": {"message": "Namespace"}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "asc"}}]
        }
        
        logs = self.search_logs(query, size=100)
        
        relevant = []
        for log in logs:
            msg = log.get("message", "")
            if any(term in msg for term in ["args", "Namespace", "Starting pipeline", "years"]):
                relevant.append({
                    "timestamp": log.get("timestamp"),
                    "message": msg,
                    "logger": log.get("logger")
                })
        
        return relevant
    
    def get_document_counts_by_year(self):
        """Count documents processed by year."""
        
        # Count successful parses by year
        query = {
            "query": {
                "match": {"message": "Parsed legislation"}
            },
            "aggs": {
                "years": {
                    "terms": {
                        "field": "message.keyword",
                        "size": 100
                    }
                }
            }
        }
        
        # Simpler approach - just count by searching for year patterns
        year_counts = {}
        
        for year in range(1963, 2026):
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"message": "Parsed legislation"}},
                            {"match": {"message": str(year)}}
                        ]
                    }
                }
            }
            
            result = self.es.count(index=self.index_name, body=query)
            count = result.get("count", 0)
            if count > 0:
                year_counts[year] = count
        
        return year_counts
    
    def check_legislation_completion(self):
        """Check if legislation processing completed normally."""
        
        # Look for transition to other document types
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "explanatory-note"}},
                        {"match": {"message": "amendment"}},
                        {"match": {"message": "caselaw"}}
                    ],
                    "must": [
                        {"range": {"timestamp": {"gte": "2025-06-07T18:00:00Z"}}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "asc"}}]
        }
        
        logs = self.search_logs(query, size=50)
        
        transitions = []
        for log in logs:
            msg = log.get("message", "")
            if any(dtype in msg for dtype in ["explanatory-note", "amendment", "caselaw"]):
                transitions.append({
                    "timestamp": log.get("timestamp"),
                    "message": msg[:150],
                    "logger": log.get("logger")
                })
        
        return transitions
    
    def get_latest_logs_by_doc_type(self):
        """Get the latest logs for each document type."""
        
        doc_types = ["legislation", "explanatory-note", "amendment", "caselaw"]
        latest = {}
        
        for dtype in doc_types:
            query = {
                "query": {
                    "match": {"logger": f"lex.{dtype}"}
                },
                "sort": [{"timestamp": {"order": "desc"}}],
                "size": 1
            }
            
            response = self.es.search(index=self.index_name, body=query)
            hits = response.get("hits", {}).get("hits", [])
            
            if hits:
                log = hits[0]["_source"]
                latest[dtype] = {
                    "timestamp": log.get("timestamp"),
                    "message": log.get("message", "")[:100],
                    "level": log.get("level")
                }
        
        return latest
    
    def analyze_legislation_urls(self):
        """Analyze the URLs that were processed."""
        
        # Get sample of legislation URLs from different years
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "legislation.gov.uk"}},
                        {"match": {"logger": "lex.legislation"}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        logs = self.search_logs(query, size=200)
        
        # Extract years from URLs
        year_distribution = {}
        for log in logs:
            msg = log.get("message", "")
            # Look for year in URL pattern
            import re
            year_match = re.search(r'/(\d{4})/', msg)
            if year_match:
                year = int(year_match.group(1))
                year_distribution[year] = year_distribution.get(year, 0) + 1
        
        return year_distribution
    
    def print_report(self):
        """Print comprehensive status report."""
        print("=" * 80)
        print("PIPELINE STATUS CHECK REPORT")
        print("=" * 80)
        
        # Check for start parameters
        print("\n" + "-" * 60)
        print("PIPELINE START PARAMETERS")
        print("-" * 60)
        
        start_logs = self.get_pipeline_start_logs()
        if start_logs:
            print("Found pipeline initialization logs:")
            for log in start_logs[:5]:
                if "year" in log["message"].lower() or "args" in log["message"].lower():
                    print(f"{log['timestamp'][:19]}: {log['message']}")
        
        # Document counts by year
        print("\n" + "-" * 60)
        print("DOCUMENTS PARSED BY YEAR")
        print("-" * 60)
        
        year_counts = self.get_document_counts_by_year()
        if year_counts:
            for year in sorted(year_counts.keys()):
                print(f"{year}: {year_counts[year]} documents")
            print(f"\nTotal years processed: {len(year_counts)}")
            print(f"Year range: {min(year_counts.keys())} - {max(year_counts.keys())}")
        
        # URL distribution
        print("\n" + "-" * 60)
        print("URL YEAR DISTRIBUTION (from recent logs)")
        print("-" * 60)
        
        url_years = self.analyze_legislation_urls()
        if url_years:
            for year in sorted(url_years.keys())[-10:]:
                print(f"{year}: {url_years[year]} URLs in logs")
        
        # Check transitions
        print("\n" + "-" * 60)
        print("DOCUMENT TYPE TRANSITIONS")
        print("-" * 60)
        
        transitions = self.check_legislation_completion()
        if transitions:
            print("\nFound transitions to other document types:")
            for trans in transitions[:5]:
                print(f"{trans['timestamp'][:19]}: {trans['message']}")
        
        # Latest logs by type
        print("\n" + "-" * 60)
        print("LATEST LOGS BY DOCUMENT TYPE")
        print("-" * 60)
        
        latest = self.get_latest_logs_by_doc_type()
        for dtype, info in latest.items():
            print(f"\n{dtype}:")
            print(f"  Time: {info['timestamp'][:19]}")
            print(f"  Level: {info['level']}")
            print(f"  Message: {info['message']}...")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        if year_counts:
            if max(year_counts.keys()) == 1971:
                print("\n⚠️  ISSUE FOUND: Legislation processing stopped at 1971")
                print("   Expected to process until 2025")
                print("\nPossible causes:")
                print("1. The year range parameter might not have been passed correctly")
                print("2. The pipeline might have hit a limit parameter")
                print("3. There might be an issue with the year range parsing in the code")
        
        if transitions:
            print(f"\n✓ Pipeline successfully transitioned to other document types")
            print(f"  First transition at: {transitions[0]['timestamp'][:19]}")


if __name__ == "__main__":
    checker = PipelineStatusChecker()
    if checker.test_connection():
        checker.print_report()
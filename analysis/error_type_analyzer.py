"""Analyze different types of errors encountered during processing."""

from typing import Dict, List
from collections import defaultdict, Counter
from datetime import datetime
from base_analyzer import BaseAnalyzer
import json
import re


class ErrorTypeAnalyzer(BaseAnalyzer):
    """Analyze error patterns and types from pipeline logs."""
    
    def __init__(self):
        super().__init__()
        self.error_patterns = {
            "pdf_fallback": ["likely a pdf", "no body found in the .xml file"],
            "missing_metadata": ["Invalid caselaw id", "metadata is missing"],
            "http_errors": ["HTTPError", "ConnectionError", "Timeout", "RequestException"],
            "parsing_errors": ["LexParsingError", "Error parsing", "ParseError"],
            "elasticsearch_errors": ["ElasticsearchException", "BulkIndexError"],
            "memory_errors": ["MemoryError", "out of memory"],
            "encoding_errors": ["UnicodeDecodeError", "UnicodeEncodeError"],
            "file_errors": ["FileNotFoundError", "IOError", "PermissionError"]
        }
    
    def categorize_error(self, message: str, exception: str = None) -> str:
        """Categorize an error based on message and exception details."""
        full_text = message + (exception or "")
        
        for category, patterns in self.error_patterns.items():
            for pattern in patterns:
                if pattern.lower() in full_text.lower():
                    return category
        
        return "other"
    
    def get_error_distribution(self) -> Dict[str, int]:
        """Get distribution of error types."""
        
        # Query for all error logs
        query = {
            "query": {
                "term": {"level": "ERROR"}
            }
        }
        
        logs = self.search_logs(query)
        
        error_counts = Counter()
        
        for log in logs:
            message = log.get("message", "")
            exception = log.get("exception", "")
            category = self.categorize_error(message, exception)
            error_counts[category] += 1
        
        return dict(error_counts)
    
    def get_errors_by_time(self, time_bucket: str = "1h") -> Dict[str, List[Dict]]:
        """Get error counts over time using Elasticsearch aggregations."""
        
        query = {
            "query": {
                "term": {"level": "ERROR"}
            },
            "aggs": {
                "errors_over_time": {
                    "date_histogram": {
                        "field": "timestamp",
                        "fixed_interval": time_bucket,
                        "min_doc_count": 1
                    }
                }
            }
        }
        
        result = self.aggregate_logs(query)
        
        # Format the results
        time_series = []
        for bucket in result.get("errors_over_time", {}).get("buckets", []):
            time_series.append({
                "timestamp": bucket["key_as_string"],
                "error_count": bucket["doc_count"]
            })
        
        return time_series
    
    def get_top_error_messages(self, limit: int = 20) -> List[Dict[str, any]]:
        """Get the most common error messages."""
        
        query = {
            "query": {
                "term": {"level": "ERROR"}
            }
        }
        
        logs = self.search_logs(query)
        
        # Group similar errors
        error_groups = defaultdict(list)
        
        for log in logs:
            message = log.get("message", "")
            # Remove variable parts like IDs, URLs, numbers
            normalized = re.sub(r'https?://[^\s]+', 'URL', message)
            normalized = re.sub(r'/\d{4}/', '/YEAR/', normalized)
            normalized = re.sub(r'/[a-zA-Z]+/\d+', '/TYPE/NUM', normalized)
            normalized = re.sub(r'\b\d+\b', 'NUM', normalized)
            
            error_groups[normalized].append({
                "original_message": message,
                "timestamp": log.get("timestamp"),
                "logger": log.get("logger")
            })
        
        # Sort by frequency
        top_errors = []
        for normalized_msg, instances in sorted(error_groups.items(), 
                                               key=lambda x: len(x[1]), 
                                               reverse=True)[:limit]:
            top_errors.append({
                "pattern": normalized_msg,
                "count": len(instances),
                "first_occurrence": min(i["timestamp"] for i in instances if i["timestamp"]),
                "last_occurrence": max(i["timestamp"] for i in instances if i["timestamp"]),
                "example": instances[0]["original_message"]
            })
        
        return top_errors
    
    def get_error_rate_by_document_type(self) -> Dict[str, Dict[str, float]]:
        """Calculate error rates for different document types."""
        
        # Get success logs
        success_query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"level": "INFO"}},
                        {"match": {"message": "Parsed"}}
                    ]
                }
            }
        }
        
        # Get error logs
        error_query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"level": "ERROR"}},
                        {"match": {"message": "Error parsing"}}
                    ]
                }
            }
        }
        
        success_logs = self.search_logs(success_query)
        error_logs = self.search_logs(error_query)
        
        # Track by document type
        stats = defaultdict(lambda: {"success": 0, "errors": 0})
        
        # Count successes
        for log in success_logs:
            message = log.get("message", "")
            
            if "legislation" in message.lower():
                stats["legislation"]["success"] += 1
            elif "caselaw" in message.lower():
                stats["caselaw"]["success"] += 1
            elif "amendment" in message.lower():
                stats["amendment"]["success"] += 1
            elif "explanatory" in message.lower():
                stats["explanatory_note"]["success"] += 1
        
        # Count errors
        for log in error_logs:
            message = log.get("message", "")
            
            if "legislation" in message.lower():
                stats["legislation"]["errors"] += 1
            elif "caselaw" in message.lower():
                stats["caselaw"]["errors"] += 1
            elif "amendment" in message.lower():
                stats["amendment"]["errors"] += 1
            elif "explanatory" in message.lower():
                stats["explanatory_note"]["errors"] += 1
        
        # Calculate error rates
        result = {}
        for doc_type, counts in stats.items():
            total = counts["success"] + counts["errors"]
            if total > 0:
                error_rate = round(100 * counts["errors"] / total, 2)
                result[doc_type] = {
                    "total_attempts": total,
                    "total_success": counts["success"],
                    "total_errors": counts["errors"],
                    "error_rate": error_rate
                }
        
        return result
    
    def print_report(self):
        """Print a comprehensive error analysis report."""
        print("=" * 80)
        print("ERROR TYPE ANALYSIS REPORT")
        print("=" * 80)
        
        # Error distribution
        print("\n" + "-" * 60)
        print("ERROR DISTRIBUTION BY CATEGORY")
        print("-" * 60)
        
        distribution = self.get_error_distribution()
        total_errors = sum(distribution.values())
        
        print(f"Total errors found: {total_errors:,}\n")
        
        for category, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = round(100 * count / total_errors, 2) if total_errors > 0 else 0
            print(f"{category:<20} {count:>8,} ({percentage:>5.1f}%)")
        
        # Error rates by document type
        print("\n" + "-" * 60)
        print("ERROR RATES BY DOCUMENT TYPE")
        print("-" * 60)
        
        doc_type_errors = self.get_error_rate_by_document_type()
        print(f"{'Document Type':<20} {'Attempts':<12} {'Errors':<10} {'Error Rate':<10}")
        print("-" * 60)
        
        for doc_type, stats in sorted(doc_type_errors.items()):
            print(f"{doc_type:<20} {stats['total_attempts']:<12,} "
                  f"{stats['total_errors']:<10,} {stats['error_rate']:<10.2f}%")
        
        # Top error messages
        print("\n" + "-" * 60)
        print("TOP ERROR PATTERNS")
        print("-" * 60)
        
        top_errors = self.get_top_error_messages(10)
        for i, error in enumerate(top_errors, 1):
            print(f"\n{i}. Pattern: {error['pattern'][:100]}...")
            print(f"   Count: {error['count']:,}")
            print(f"   First seen: {error['first_occurrence']}")
            print(f"   Last seen: {error['last_occurrence']}")
        
        # Save detailed results
        results = {
            "summary": {
                "total_errors": total_errors,
                "analysis_timestamp": datetime.now().isoformat()
            },
            "error_distribution": distribution,
            "error_rates_by_type": doc_type_errors,
            "top_error_patterns": top_errors,
            "errors_over_time": self.get_errors_by_time()
        }
        
        with open("analysis/error_type_report.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print("\n" + "=" * 80)
        print("Detailed results saved to: analysis/error_type_report.json")


if __name__ == "__main__":
    analyzer = ErrorTypeAnalyzer()
    if analyzer.test_connection():
        analyzer.print_report()
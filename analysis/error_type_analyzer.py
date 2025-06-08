"""Analyze different types of errors encountered during processing."""

from typing import Dict, List, Set
from collections import defaultdict, Counter
from datetime import datetime
from base_analyzer import BaseAnalyzer, get_output_path
from common_utils import extract_url_from_message, normalize_error_message, categorize_document_type
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
            "file_errors": ["FileNotFoundError", "IOError", "PermissionError"],
            "validation_errors": ["validation error", "ValidationError"]
        }
    
    def categorize_error(self, message: str, exception: str = None) -> str:
        """Categorize an error based on message and exception details."""
        full_text = message + (exception or "")
        
        for category, patterns in self.error_patterns.items():
            for pattern in patterns:
                if pattern.lower() in full_text.lower():
                    return category
        
        return "other"
    
    def get_error_distribution(self, hours_back=None) -> Dict[str, int]:
        """Get distribution of error types."""
        
        # Query for all error logs
        query = {
            "query": {
                "term": {"level": "ERROR"}
            }
        }
        
        # Add time filter if specified
        if hours_back:
            query["query"] = {
                "bool": {
                    "must": [query["query"]],
                    "filter": {
                        "range": {
                            "timestamp": {
                                "gte": f"now-{hours_back}h"
                            }
                        }
                    }
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
            # Use common utility to normalize message
            normalized = normalize_error_message(message)
            
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
    
    def get_error_rate_by_document_type(self, hours_back=None) -> Dict[str, Dict[str, float]]:
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
        
        # Add time filter if specified
        if hours_back:
            time_filter = {
                "filter": {
                    "range": {
                        "timestamp": {
                            "gte": f"now-{hours_back}h"
                        }
                    }
                }
            }
            success_query["query"]["bool"].update(time_filter)
            error_query["query"]["bool"].update(time_filter)
        
        success_logs = self.search_logs(success_query)
        error_logs = self.search_logs(error_query)
        
        # Track by document type
        stats = defaultdict(lambda: {"success": 0, "errors": 0})
        
        # Count successes
        for log in success_logs:
            message = log.get("message", "")
            doc_type = categorize_document_type(message)
            if doc_type:
                stats[doc_type]["success"] += 1
        
        # Count errors
        for log in error_logs:
            message = log.get("message", "")
            doc_type = categorize_document_type(message)
            if doc_type:
                stats[doc_type]["errors"] += 1
        
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
    
    def analyze_non_pdf_errors(self, hours_back=24):
        """Analyze errors that are NOT related to PDF/no body issues."""
        
        print("\n" + "="*80)
        print("NON-PDF ERROR ANALYSIS")
        print("="*80)
        
        # Get validation errors (excluding PDF)
        validation_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "validation error"}}
                    ],
                    "must_not": [
                        {"match_phrase": {"message": "no body found"}}
                    ],
                    "filter": {
                        "range": {
                            "timestamp": {
                                "gte": f"now-{hours_back}h"
                            }
                        }
                    }
                }
            },
            "size": 200
        }
        
        validation_errors = self.search_logs(validation_query)
        
        if validation_errors:
            print(f"\nValidation errors (non-PDF): {len(validation_errors)}")
            # Group by error pattern
            patterns = defaultdict(list)
            for error in validation_errors[:10]:  # Show first 10
                msg = error.get("message", "")
                if "CommentaryCitation" in msg:
                    patterns["CommentaryCitation"].append(error)
                else:
                    patterns["Other Validation"].append(error)
            
            for pattern, errs in patterns.items():
                if errs:
                    print(f"\n  {pattern}: {len(errs)} errors")
                    for err in errs[:2]:
                        print(f"    - {err.get('timestamp', 'N/A')}: {err.get('message', '')[:100]}...")
        
        # Look for specific error patterns
        self._analyze_commentary_citation_errors()
    
    def _analyze_commentary_citation_errors(self):
        """Specifically analyze CommentaryCitation validation errors."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "CommentaryCitation"}},
                        {"match": {"message": "validation error"}}
                    ]
                }
            },
            "size": 50
        }
        
        results = self.search_logs(query)
        
        if results:
            print(f"\n\nCommentaryCitation errors: {len(results)}")
            for i, result in enumerate(results[:3]):
                print(f"\n  Example {i+1}:")
                print(f"    Time: {result.get('timestamp', 'N/A')}")
                print(f"    Message: {result.get('message', '')[:150]}...")
    
    def extract_url_from_message(self, message: str) -> str:
        """Extract legislation.gov.uk URL from log message."""
        return extract_url_from_message(message)
    
    def get_validation_error_documents(self) -> Dict[str, List[Dict]]:
        """Extract documents with validation errors (e.g., CommentaryCitation)."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"level": "ERROR"}},
                        {"match": {"message": "validation error"}}
                    ],
                    "must_not": [
                        {"match_phrase": {"message": "no body found"}}
                    ]
                }
            },
            "size": 10000
        }
        
        logs = self.search_logs(query)
        
        validation_errors = defaultdict(list)
        seen_ids = set()
        
        for log in logs:
            message = log.get("message", "")
            doc_id = log.get("doc_id", "")
            
            # Determine validation error type
            if "CommentaryCitation" in message:
                error_type = "CommentaryCitation"
            elif "validation error" in message:
                error_type = "Other Validation"
            else:
                error_type = "Unknown Validation"
            
            # Get document URL
            url = self.extract_url_from_message(message)
            if not url and doc_id:
                url = doc_id
            
            if url and url not in seen_ids:
                seen_ids.add(url)
                validation_errors[error_type].append({
                    "url": url,
                    "timestamp": log.get("timestamp", ""),
                    "message": message[:200],
                    "doc_id": doc_id
                })
        
        return dict(validation_errors)
    
    def get_failed_xml_urls(self) -> Dict[str, List[Dict]]:
        """Get all URLs where XML parsing failed (excluding PDF fallbacks)."""
        
        # Query for XML parsing errors that are NOT PDF fallbacks
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"level": "ERROR"}},
                        {"match": {"message": "Error parsing"}}
                    ],
                    "must_not": [
                        {"match": {"message": "likely a pdf"}},
                        {"match": {"message": "no body found"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group URLs by error type
        failed_urls = defaultdict(list)
        
        for log in logs:
            message = log.get("message", "")
            exception = log.get("exception", "")
            timestamp = log.get("timestamp", "")
            
            url = self.extract_url_from_message(message)
            if url:
                # Categorize the error
                error_category = "unknown"
                if "metadata is missing" in message:
                    error_category = "missing_metadata"
                elif "ParseError" in str(exception):
                    error_category = "xml_parse_error"
                elif "UnicodeDecodeError" in str(exception):
                    error_category = "encoding_error"
                elif "AttributeError" in str(exception):
                    error_category = "attribute_error"
                
                failed_urls[error_category].append({
                    "url": url,
                    "timestamp": timestamp,
                    "error_message": message[:200],
                    "exception_snippet": str(exception)[:200] if exception else None
                })
        
        # Deduplicate URLs within each category
        for category in failed_urls:
            seen_urls = set()
            unique_entries = []
            for entry in failed_urls[category]:
                if entry["url"] not in seen_urls:
                    seen_urls.add(entry["url"])
                    unique_entries.append(entry)
            failed_urls[category] = unique_entries
        
        return dict(failed_urls)
    
    def get_pdf_fallback_urls(self) -> Dict[str, List[str]]:
        """Get URLs where we had to fall back to PDF (no XML body)."""
        
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "likely a pdf"}},
                        {"match": {"message": "no body found"}}
                    ]
                }
            },
            "size": 10000
        }
        
        logs = self.search_logs(query)
        
        # Group by year
        pdf_urls_by_year = defaultdict(set)
        
        for log in logs:
            message = log.get("message", "")
            url = self.extract_url_from_message(message)
            year = self.extract_year_from_message(message)
            
            if url and year:
                pdf_urls_by_year[year].add(url)
        
        # Convert sets to sorted lists
        result = {}
        for year in sorted(pdf_urls_by_year.keys()):
            result[str(year)] = sorted(list(pdf_urls_by_year[year]))
        
        return result
    
    def get_successful_xml_urls_sample(self, limit: int = 100) -> List[str]:
        """Get a sample of successfully parsed XML URLs for comparison."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"level": "INFO"}},
                        {"match": {"message": "Parsed legislation"}}
                    ]
                }
            },
            "size": limit
        }
        
        logs = self.search_logs(query)
        
        urls = []
        for log in logs:
            message = log.get("message", "")
            url = self.extract_url_from_message(message)
            if url:
                urls.append(url)
        
        return urls
    
    def analyze_error_patterns_by_url(self) -> Dict[str, any]:
        """Analyze patterns in XML parsing failures by URL."""
        
        failed_urls = self.get_failed_xml_urls()
        
        # Analyze by year and type
        year_stats = defaultdict(lambda: defaultdict(int))
        type_stats = defaultdict(lambda: defaultdict(int))
        
        for error_type, entries in failed_urls.items():
            for entry in entries:
                url = entry["url"]
                
                # Extract year
                year_match = re.search(r'/(\d{4})/', url)
                if year_match:
                    year = int(year_match.group(1))
                    year_stats[year][error_type] += 1
                
                # Extract type
                type_match = re.search(r'legislation\.gov\.uk/([^/]+)/', url)
                if type_match:
                    leg_type = type_match.group(1)
                    type_stats[leg_type][error_type] += 1
        
        return {
            "total_failed_urls": sum(len(entries) for entries in failed_urls.values()),
            "by_error_type": {k: len(v) for k, v in failed_urls.items()},
            "by_year": dict(year_stats),
            "by_legislation_type": dict(type_stats)
        }
    
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
        
        # Extract failed XML URLs and validation errors
        print("\n" + "-" * 60)
        print("FAILED XML URL ANALYSIS")
        print("-" * 60)
        
        failed_urls = self.get_failed_xml_urls()
        validation_errors = self.get_validation_error_documents()
        pdf_urls = self.get_pdf_fallback_urls()
        url_analysis = self.analyze_error_patterns_by_url()
        
        print(f"\nTotal unique failed XML URLs: {url_analysis['total_failed_urls']}")
        print(f"Total PDF fallback documents: {sum(len(urls) for urls in pdf_urls.values())}")
        
        # Failed XML by error type
        print("\nFailed XML URLs by error type:")
        for error_type, count in url_analysis['by_error_type'].items():
            print(f"  {error_type:<25} {count:>5} URLs")
        
        # Validation errors summary
        if validation_errors:
            total_validation = sum(len(docs) for docs in validation_errors.values())
            print(f"\nTotal documents with validation errors: {total_validation}")
            for error_type, docs in validation_errors.items():
                if docs:
                    print(f"  {error_type}: {len(docs)} documents")
        
        # Save detailed results
        results = {
            "summary": {
                "total_errors": total_errors,
                "analysis_timestamp": datetime.now().isoformat()
            },
            "error_distribution": distribution,
            "error_rates_by_type": doc_type_errors,
            "top_error_patterns": top_errors,
            "errors_over_time": self.get_errors_by_time(),
            "failed_xml_urls": failed_urls,
            "validation_errors": validation_errors,
            "pdf_fallback_urls": pdf_urls,
            "url_error_analysis": url_analysis,
            "successful_xml_sample": self.get_successful_xml_urls_sample(50)
        }
        
        # Save main report
        output_file = get_output_path("error_type_report.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save separate files for specific analyses
        failed_urls_path = get_output_path("failed_xml_urls.json")
        with open(failed_urls_path, "w") as f:
            json.dump(failed_urls, f, indent=2)
        
        validation_errors_path = get_output_path("validation_error_documents.json")
        with open(validation_errors_path, "w") as f:
            json.dump(validation_errors, f, indent=2)
        
        # Add non-PDF error analysis
        self.analyze_non_pdf_errors(hours_back=168)  # Last 7 days
        
        print("\n" + "=" * 80)
        print("Results saved to:")
        print(f"  - {output_file} (complete error analysis)")
        print(f"  - {failed_urls_path} (XML parsing errors)")
        print(f"  - {validation_errors_path} (validation errors)")


if __name__ == "__main__":
    analyzer = ErrorTypeAnalyzer()
    if analyzer.test_connection():
        analyzer.print_report()
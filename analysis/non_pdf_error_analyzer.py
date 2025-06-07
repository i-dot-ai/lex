"""Analyze non-PDF related errors in the pipeline."""

from base_analyzer import BaseAnalyzer
from datetime import datetime, timedelta
from collections import defaultdict
import re


class NonPDFErrorAnalyzer(BaseAnalyzer):
    """Analyze errors that are not related to PDF/no body issues."""
    
    def find_non_pdf_errors(self, hours_back=24):
        """Find all errors except PDF/no body errors."""
        
        # First, get validation errors
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
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        validation_errors = self.search_logs(validation_query, size=200)
        
        # Get rate limit errors
        rate_limit_query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "rate limit"}},
                        {"match": {"message": "Rate limited"}},
                        {"match": {"error_type": "RateLimitException"}}
                    ],
                    "minimum_should_match": 1,
                    "filter": {
                        "range": {
                            "timestamp": {
                                "gte": f"now-{hours_back}h"
                            }
                        }
                    }
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        rate_limit_errors = self.search_logs(rate_limit_query, size=100)
        
        # Get HTTP/Network errors
        network_query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "HTTPError"}},
                        {"match": {"message": "Connection"}},
                        {"match": {"message": "Timeout"}},
                        {"match": {"error_type": "HTTPError"}},
                        {"match": {"error_type": "ConnectionError"}},
                        {"match": {"error_type": "TimeoutError"}}
                    ],
                    "minimum_should_match": 1,
                    "filter": {
                        "range": {
                            "timestamp": {
                                "gte": f"now-{hours_back}h"
                            }
                        }
                    }
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        network_errors = self.search_logs(network_query, size=100)
        
        # Get parsing errors (excluding PDF ones)
        parsing_query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"error_type": "KeyError"}},
                        {"match": {"error_type": "AttributeError"}},
                        {"match": {"error_type": "ValueError"}},
                        {"match": {"message": "parsing error"}},
                        {"match": {"message": "KeyError"}},
                        {"match": {"message": "AttributeError"}}
                    ],
                    "minimum_should_match": 1,
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
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        parsing_errors = self.search_logs(parsing_query, size=100)
        
        return {
            "validation_errors": validation_errors,
            "rate_limit_errors": rate_limit_errors,
            "network_errors": network_errors,
            "parsing_errors": parsing_errors
        }
    
    def analyze_commentary_citation_errors(self):
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
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        return self.search_logs(query, size=50)
    
    def print_analysis(self, hours_back=24):
        """Print comprehensive analysis of non-PDF errors."""
        
        print("=" * 80)
        print("NON-PDF ERROR ANALYSIS")
        print("=" * 80)
        print(f"Time range: Last {hours_back} hours\n")
        
        errors = self.find_non_pdf_errors(hours_back)
        
        # Validation Errors
        print("1. VALIDATION ERRORS")
        print("-" * 40)
        validation_errors = errors["validation_errors"]
        print(f"Total found: {len(validation_errors)}")
        
        if validation_errors:
            # Group by error pattern
            patterns = defaultdict(list)
            for error in validation_errors:
                msg = error.get("message", "")
                if "CommentaryCitation" in msg:
                    patterns["CommentaryCitation"].append(error)
                elif "validation error" in msg.lower():
                    patterns["Other Validation"].append(error)
            
            for pattern, errs in patterns.items():
                print(f"\n  {pattern}: {len(errs)} errors")
                for i, err in enumerate(errs[:2]):  # Show first 2
                    print(f"    - {err.get('timestamp', 'N/A')}: {err.get('message', '')[:100]}...")
        
        # Rate Limit Errors
        print("\n\n2. RATE LIMIT ERRORS")
        print("-" * 40)
        rate_limit_errors = errors["rate_limit_errors"]
        print(f"Total found: {len(rate_limit_errors)}")
        
        if rate_limit_errors:
            for i, error in enumerate(rate_limit_errors[:3]):
                print(f"\n  Example {i+1}:")
                print(f"    Time: {error.get('timestamp', 'N/A')}")
                print(f"    Message: {error.get('message', '')[:150]}")
        
        # Network Errors
        print("\n\n3. NETWORK/HTTP ERRORS")
        print("-" * 40)
        network_errors = errors["network_errors"]
        print(f"Total found: {len(network_errors)}")
        
        if network_errors:
            for i, error in enumerate(network_errors[:3]):
                print(f"\n  Example {i+1}:")
                print(f"    Time: {error.get('timestamp', 'N/A')}")
                print(f"    Type: {error.get('error_type', 'N/A')}")
                print(f"    Message: {error.get('message', '')[:150]}")
        
        # Parsing Errors
        print("\n\n4. PARSING ERRORS (non-PDF)")
        print("-" * 40)
        parsing_errors = errors["parsing_errors"]
        print(f"Total found: {len(parsing_errors)}")
        
        if parsing_errors:
            # Group by error type
            by_type = defaultdict(list)
            for error in parsing_errors:
                error_type = error.get("error_type", "Unknown")
                by_type[error_type].append(error)
            
            for error_type, errs in by_type.items():
                print(f"\n  {error_type}: {len(errs)} errors")
                for i, err in enumerate(errs[:2]):
                    print(f"    - {err.get('timestamp', 'N/A')}: {err.get('message', '')[:100]}...")
        
        # Summary
        print("\n\nSUMMARY")
        print("-" * 40)
        total_non_pdf = sum(len(errors[k]) for k in errors)
        print(f"Total non-PDF errors found: {total_non_pdf}")
        
        print("\nError Distribution:")
        for error_type, error_list in errors.items():
            if error_list:
                pct = (len(error_list) / total_non_pdf) * 100 if total_non_pdf > 0 else 0
                print(f"  - {error_type.replace('_', ' ').title()}: {len(error_list)} ({pct:.1f}%)")


if __name__ == "__main__":
    analyzer = NonPDFErrorAnalyzer()
    if analyzer.test_connection():
        analyzer.print_analysis(hours_back=48)  # Look at last 48 hours
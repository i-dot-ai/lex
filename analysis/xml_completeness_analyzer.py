"""Analyze XML completeness by year and type from pipeline logs."""

from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime
from base_analyzer import BaseAnalyzer, get_output_path
import json


class XMLCompletenessAnalyzer(BaseAnalyzer):
    """Analyze XML parsing success/failure rates by year and legislation type."""
    
    def __init__(self):
        super().__init__()
        self.pdf_indicator = "likely a pdf"
        self.no_body_indicator = "no body found"
        self.parse_error_indicator = "Error parsing"
        self.parse_success_indicator = "Parsed legislation:"
        
    def get_xml_completeness_all_time(self) -> Dict[int, Dict[str, int]]:
        """Get XML completeness statistics using all-time data for accuracy."""
        
        # Aggregate successful parses by year
        success_query = {
            "query": {
                "match": {
                    "message": self.parse_success_indicator
                }
            },
            "size": 0,
            "aggs": {
                "by_year": {
                    "terms": {
                        "field": "doc_year",
                        "size": 100,
                        "order": {"_key": "asc"}
                    }
                }
            }
        }
        
        # Aggregate PDF failures by year
        pdf_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": self.parse_error_indicator}},
                        {"match": {"message": self.pdf_indicator}}
                    ]
                }
            },
            "size": 0,
            "aggs": {
                "by_year": {
                    "terms": {
                        "field": "doc_year", 
                        "size": 100,
                        "order": {"_key": "asc"}
                    }
                }
            }
        }
        
        # Execute queries
        success_response = self.es.search(index=self.index_name, body=success_query)
        pdf_response = self.es.search(index=self.index_name, body=pdf_query)
        
        # Process results
        year_stats = {}
        
        # Add successful parses
        for bucket in success_response.get("aggregations", {}).get("by_year", {}).get("buckets", []):
            year = bucket["key"]
            count = bucket["doc_count"]
            if year not in year_stats:
                year_stats[year] = {"total": 0, "xml_success": 0, "pdf_fallback": 0, "other_errors": 0}
            year_stats[year]["xml_success"] = count
            year_stats[year]["total"] += count
        
        # Add PDF failures
        for bucket in pdf_response.get("aggregations", {}).get("by_year", {}).get("buckets", []):
            year = bucket["key"]
            count = bucket["doc_count"]
            if year not in year_stats:
                year_stats[year] = {"total": 0, "xml_success": 0, "pdf_fallback": 0, "other_errors": 0}
            year_stats[year]["pdf_fallback"] = count
            year_stats[year]["total"] += count
        
        return year_stats
    
    def get_xml_completeness_by_year(self) -> Dict[int, Dict[str, int]]:
        """Get XML completeness statistics grouped by year."""
        
        # Query for all parsing-related logs
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Parsed legislation"}},
                        {"match": {"message": "Error parsing legislation"}},
                        {"match": {"message": "likely a pdf"}},
                        {"match": {"message": "no body found"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group by year
        stats_by_year = defaultdict(lambda: {
            "total": 0,
            "xml_success": 0,
            "pdf_fallback": 0,
            "other_errors": 0
        })
        
        for log in logs:
            message = log.get("message", "")
            year = self.extract_year_from_message(message)
            
            if year:
                stats_by_year[year]["total"] += 1
                
                if self.parse_success_indicator in message:
                    stats_by_year[year]["xml_success"] += 1
                elif self.pdf_indicator in message or self.no_body_indicator in message:
                    stats_by_year[year]["pdf_fallback"] += 1
                else:
                    stats_by_year[year]["other_errors"] += 1
        
        # Convert to regular dict and calculate percentages
        result = {}
        for year, stats in sorted(stats_by_year.items()):
            total = stats["total"]
            if total > 0:
                result[year] = {
                    "total": total,
                    "xml_success": stats["xml_success"],
                    "xml_success_rate": round(100 * stats["xml_success"] / total, 2),
                    "pdf_fallback": stats["pdf_fallback"],
                    "pdf_fallback_rate": round(100 * stats["pdf_fallback"] / total, 2),
                    "other_errors": stats["other_errors"],
                    "other_error_rate": round(100 * stats["other_errors"] / total, 2)
                }
        
        return result
    
    def get_xml_completeness_by_type_all_time(self) -> Dict[str, Dict[str, int]]:
        """Get XML completeness by legislation type using all-time data."""
        
        # Aggregate successful parses by type
        success_query = {
            "query": {
                "match": {
                    "message": self.parse_success_indicator
                }
            },
            "size": 0,
            "aggs": {
                "by_type": {
                    "terms": {
                        "field": "doc_type.keyword",
                        "size": 100
                    }
                }
            }
        }
        
        # Aggregate PDF failures by type
        pdf_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": self.parse_error_indicator}},
                        {"match": {"message": self.pdf_indicator}}
                    ]
                }
            },
            "size": 0,
            "aggs": {
                "by_type": {
                    "terms": {
                        "field": "doc_type.keyword",
                        "size": 100
                    }
                }
            }
        }
        
        # Execute queries
        success_response = self.es.search(index=self.index_name, body=success_query)
        pdf_response = self.es.search(index=self.index_name, body=pdf_query)
        
        # Process results
        type_stats = {}
        
        # Add successful parses
        for bucket in success_response.get("aggregations", {}).get("by_type", {}).get("buckets", []):
            doc_type = bucket["key"]
            count = bucket["doc_count"]
            if doc_type not in type_stats:
                type_stats[doc_type] = {"total": 0, "xml_success": 0, "pdf_fallback": 0, "other_errors": 0}
            type_stats[doc_type]["xml_success"] = count
            type_stats[doc_type]["total"] += count
        
        # Add PDF failures
        for bucket in pdf_response.get("aggregations", {}).get("by_type", {}).get("buckets", []):
            doc_type = bucket["key"]
            count = bucket["doc_count"]
            if doc_type not in type_stats:
                type_stats[doc_type] = {"total": 0, "xml_success": 0, "pdf_fallback": 0, "other_errors": 0}
            type_stats[doc_type]["pdf_fallback"] = count
            type_stats[doc_type]["total"] += count
        
        return type_stats
    
    def get_xml_completeness_by_type(self) -> Dict[str, Dict[str, int]]:
        """Get XML completeness statistics grouped by legislation type."""
        
        # Query for all parsing-related logs
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Parsed legislation"}},
                        {"match": {"message": "Error parsing legislation"}},
                        {"match": {"message": "likely a pdf"}},
                        {"match": {"message": "no body found"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group by type
        stats_by_type = defaultdict(lambda: {
            "total": 0,
            "xml_success": 0,
            "pdf_fallback": 0,
            "other_errors": 0
        })
        
        for log in logs:
            message = log.get("message", "")
            leg_type = self.extract_type_from_message(message)
            
            if leg_type:
                stats_by_type[leg_type]["total"] += 1
                
                if self.parse_success_indicator in message:
                    stats_by_type[leg_type]["xml_success"] += 1
                elif self.pdf_indicator in message or self.no_body_indicator in message:
                    stats_by_type[leg_type]["pdf_fallback"] += 1
                else:
                    stats_by_type[leg_type]["other_errors"] += 1
        
        # Convert to regular dict and calculate percentages
        result = {}
        for leg_type, stats in sorted(stats_by_type.items()):
            total = stats["total"]
            if total > 0:
                result[leg_type] = {
                    "total": total,
                    "xml_success": stats["xml_success"],
                    "xml_success_rate": round(100 * stats["xml_success"] / total, 2),
                    "pdf_fallback": stats["pdf_fallback"],
                    "pdf_fallback_rate": round(100 * stats["pdf_fallback"] / total, 2),
                    "other_errors": stats["other_errors"],
                    "other_error_rate": round(100 * stats["other_errors"] / total, 2)
                }
        
        return result
    
    def get_xml_completeness_heatmap(self) -> Dict[str, Dict[int, float]]:
        """Get XML success rate as a heatmap (type x year)."""
        
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Parsed legislation"}},
                        {"match": {"message": "Error parsing legislation"}},
                        {"match": {"message": "likely a pdf"}},
                        {"match": {"message": "no body found"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group by type and year
        stats = defaultdict(lambda: defaultdict(lambda: {"success": 0, "total": 0}))
        
        for log in logs:
            message = log.get("message", "")
            year = self.extract_year_from_message(message)
            leg_type = self.extract_type_from_message(message)
            
            if year and leg_type:
                stats[leg_type][year]["total"] += 1
                if self.parse_success_indicator in message:
                    stats[leg_type][year]["success"] += 1
        
        # Convert to success rates
        heatmap = {}
        for leg_type in sorted(stats.keys()):
            heatmap[leg_type] = {}
            for year in sorted(stats[leg_type].keys()):
                total = stats[leg_type][year]["total"]
                if total > 0:
                    success_rate = round(100 * stats[leg_type][year]["success"] / total, 2)
                    heatmap[leg_type][year] = success_rate
        
        return heatmap
    
    def print_report(self):
        """Print a comprehensive XML completeness report using all-time aggregated data."""
        print("=" * 80)
        print("XML COMPLETENESS ANALYSIS REPORT (ALL-TIME DATA)")
        print("=" * 80)
        
        # Overall statistics
        total_logs = self.get_total_logs()
        print(f"\nTotal log entries analyzed: {total_logs:,}")
        
        # By Year using all-time data
        print("\n" + "-" * 60)
        print("XML COMPLETENESS BY YEAR")
        print("-" * 60)
        print(f"{'Year':<6} {'Total':<8} {'XML OK':<8} {'XML %':<8} {'PDF':<8} {'PDF %':<8}")
        print("-" * 60)
        
        by_year = self.get_xml_completeness_all_time()
        for year in sorted(by_year.keys()):
            stats = by_year[year]
            total = stats['total']
            xml_success = stats['xml_success']
            pdf_fallback = stats['pdf_fallback']
            
            if total > 0:
                xml_rate = round(100 * xml_success / total, 1)
                pdf_rate = round(100 * pdf_fallback / total, 1)
                print(f"{year:<6} {total:<8} {xml_success:<8} "
                      f"{xml_rate:<8.1f} {pdf_fallback:<8} "
                      f"{pdf_rate:<8.1f}")
        
        # By Type using all-time data
        print("\n" + "-" * 60)
        print("XML COMPLETENESS BY LEGISLATION TYPE")
        print("-" * 60)
        print(f"{'Type':<10} {'Total':<8} {'XML OK':<8} {'XML %':<8} {'PDF':<8} {'PDF %':<8}")
        print("-" * 60)
        
        by_type = self.get_xml_completeness_by_type_all_time()
        for leg_type in sorted(by_type.keys()):
            stats = by_type[leg_type]
            total = stats['total']
            xml_success = stats['xml_success']
            pdf_fallback = stats['pdf_fallback']
            
            if total > 0:
                xml_rate = round(100 * xml_success / total, 1)
                pdf_rate = round(100 * pdf_fallback / total, 1)
                print(f"{leg_type:<10} {total:<8} {xml_success:<8} "
                      f"{xml_rate:<8.1f} {pdf_fallback:<8} "
                      f"{pdf_rate:<8.1f}")
        
        # Save detailed results
        results = {
            "summary": {
                "total_logs": total_logs,
                "analysis_timestamp": datetime.now().isoformat(),
                "data_source": "all-time aggregated data"
            },
            "by_year": by_year,
            "by_type": by_type,
            "heatmap": self.get_xml_completeness_heatmap()
        }
        
        output_path = get_output_path("xml_completeness_report.json")
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        
        print("\n" + "=" * 80)
        print(f"Detailed results saved to: {output_path}")


if __name__ == "__main__":
    analyzer = XMLCompletenessAnalyzer()
    if analyzer.test_connection():
        analyzer.print_report()
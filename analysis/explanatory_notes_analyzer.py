"""Analyze explanatory notes coverage by year and legislation type."""

from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime
from base_analyzer import BaseAnalyzer, get_output_path
import json


class ExplanatoryNotesAnalyzer(BaseAnalyzer):
    """Analyze explanatory notes availability and coverage."""
    
    def __init__(self):
        super().__init__()
    
    def get_explanatory_notes_coverage_by_year(self) -> Dict[int, Dict[str, int]]:
        """Get explanatory notes coverage statistics by year."""
        
        # Query for explanatory notes related logs
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Parsed explanatory-note"}},
                        {"match": {"message": "Error parsing explanatory"}},
                        {"match": {"message": "No explanatory note found"}},
                        {"match": {"message": "explanatory note"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group by year
        stats_by_year = defaultdict(lambda: {
            "total_attempts": 0,
            "found": 0,
            "not_found": 0,
            "parse_errors": 0
        })
        
        for log in logs:
            message = log.get("message", "")
            level = log.get("level", "")
            year = self.extract_year_from_message(message)
            
            if year:
                if "Parsed explanatory-note" in message:
                    stats_by_year[year]["found"] += 1
                    stats_by_year[year]["total_attempts"] += 1
                elif "No explanatory note found" in message or "404" in message:
                    stats_by_year[year]["not_found"] += 1
                    stats_by_year[year]["total_attempts"] += 1
                elif level == "ERROR" and "explanatory" in message.lower():
                    stats_by_year[year]["parse_errors"] += 1
                    stats_by_year[year]["total_attempts"] += 1
        
        # Calculate coverage rates
        result = {}
        for year, stats in sorted(stats_by_year.items()):
            total = stats["total_attempts"]
            if total > 0:
                result[year] = {
                    "total_attempts": total,
                    "found": stats["found"],
                    "coverage_rate": round(100 * stats["found"] / total, 2),
                    "not_found": stats["not_found"],
                    "not_found_rate": round(100 * stats["not_found"] / total, 2),
                    "parse_errors": stats["parse_errors"]
                }
        
        return result
    
    def get_explanatory_notes_coverage_by_type(self) -> Dict[str, Dict[str, int]]:
        """Get explanatory notes coverage by legislation type."""
        
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Parsed explanatory-note"}},
                        {"match": {"message": "Error parsing explanatory"}},
                        {"match": {"message": "No explanatory note found"}},
                        {"match": {"message": "explanatory note"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group by type
        stats_by_type = defaultdict(lambda: {
            "total_attempts": 0,
            "found": 0,
            "not_found": 0,
            "parse_errors": 0
        })
        
        for log in logs:
            message = log.get("message", "")
            level = log.get("level", "")
            leg_type = self.extract_type_from_message(message)
            
            if leg_type:
                if "Parsed explanatory-note" in message:
                    stats_by_type[leg_type]["found"] += 1
                    stats_by_type[leg_type]["total_attempts"] += 1
                elif "No explanatory note found" in message or "404" in message:
                    stats_by_type[leg_type]["not_found"] += 1
                    stats_by_type[leg_type]["total_attempts"] += 1
                elif level == "ERROR" and "explanatory" in message.lower():
                    stats_by_type[leg_type]["parse_errors"] += 1
                    stats_by_type[leg_type]["total_attempts"] += 1
        
        # Calculate coverage rates
        result = {}
        for leg_type, stats in sorted(stats_by_type.items()):
            total = stats["total_attempts"]
            if total > 0:
                result[leg_type] = {
                    "total_attempts": total,
                    "found": stats["found"],
                    "coverage_rate": round(100 * stats["found"] / total, 2),
                    "not_found": stats["not_found"],
                    "not_found_rate": round(100 * stats["not_found"] / total, 2),
                    "parse_errors": stats["parse_errors"]
                }
        
        return result
    
    def get_coverage_trends(self) -> Dict[str, List[Tuple[int, float]]]:
        """Get coverage trends over years for main legislation types."""
        
        by_year = self.get_explanatory_notes_coverage_by_year()
        
        # Also get coverage by type and year combined
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Parsed explanatory-note"}},
                        {"match": {"message": "No explanatory note found"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Track by type and year
        type_year_stats = defaultdict(lambda: defaultdict(lambda: {"found": 0, "total": 0}))
        
        for log in logs:
            message = log.get("message", "")
            year = self.extract_year_from_message(message)
            leg_type = self.extract_type_from_message(message)
            
            if year and leg_type:
                type_year_stats[leg_type][year]["total"] += 1
                if "Parsed explanatory-note" in message:
                    type_year_stats[leg_type][year]["found"] += 1
        
        # Convert to trends
        trends = {}
        for leg_type in ["ukpga", "uksi", "asp", "wsi"]:  # Main types
            if leg_type in type_year_stats:
                trend = []
                for year in sorted(type_year_stats[leg_type].keys()):
                    stats = type_year_stats[leg_type][year]
                    if stats["total"] > 0:
                        coverage = round(100 * stats["found"] / stats["total"], 2)
                        trend.append((year, coverage))
                if trend:
                    trends[leg_type] = trend
        
        return trends
    
    def print_report(self):
        """Print a comprehensive explanatory notes coverage report."""
        print("=" * 80)
        print("EXPLANATORY NOTES COVERAGE ANALYSIS REPORT")
        print("=" * 80)
        
        # By Year
        print("\n" + "-" * 60)
        print("EXPLANATORY NOTES COVERAGE BY YEAR")
        print("-" * 60)
        print(f"{'Year':<6} {'Attempts':<10} {'Found':<8} {'Coverage %':<12} {'Not Found':<10}")
        print("-" * 60)
        
        by_year = self.get_explanatory_notes_coverage_by_year()
        total_attempts = 0
        total_found = 0
        
        for year in sorted(by_year.keys()):
            stats = by_year[year]
            total_attempts += stats['total_attempts']
            total_found += stats['found']
            print(f"{year:<6} {stats['total_attempts']:<10} {stats['found']:<8} "
                  f"{stats['coverage_rate']:<12.1f} {stats['not_found']:<10}")
        
        if total_attempts > 0:
            overall_coverage = round(100 * total_found / total_attempts, 2)
            print("-" * 60)
            print(f"{'TOTAL':<6} {total_attempts:<10} {total_found:<8} {overall_coverage:<12.1f}")
        
        # By Type
        print("\n" + "-" * 60)
        print("EXPLANATORY NOTES COVERAGE BY LEGISLATION TYPE")
        print("-" * 60)
        print(f"{'Type':<10} {'Attempts':<10} {'Found':<8} {'Coverage %':<12} {'Not Found':<10}")
        print("-" * 60)
        
        by_type = self.get_explanatory_notes_coverage_by_type()
        for leg_type in sorted(by_type.keys()):
            stats = by_type[leg_type]
            print(f"{leg_type:<10} {stats['total_attempts']:<10} {stats['found']:<8} "
                  f"{stats['coverage_rate']:<12.1f} {stats['not_found']:<10}")
        
        # Coverage trends
        print("\n" + "-" * 60)
        print("COVERAGE TRENDS FOR MAIN LEGISLATION TYPES")
        print("-" * 60)
        
        trends = self.get_coverage_trends()
        for leg_type, trend_data in sorted(trends.items()):
            if trend_data:
                recent_years = trend_data[-5:]  # Last 5 years
                print(f"\n{leg_type.upper()}:")
                for year, coverage in recent_years:
                    bar = "█" * int(coverage / 5)  # Simple bar chart
                    print(f"  {year}: {bar} {coverage:.1f}%")
        
        # Save detailed results
        results = {
            "summary": {
                "total_attempts": total_attempts,
                "total_found": total_found,
                "overall_coverage_rate": overall_coverage if total_attempts > 0 else 0,
                "analysis_timestamp": datetime.now().isoformat()
            },
            "by_year": by_year,
            "by_type": by_type,
            "coverage_trends": trends
        }
        
        output_path = get_output_path("explanatory_notes_report.json")
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        
        print("\n" + "=" * 80)
        print(f"Detailed results saved to: {output_path}")


if __name__ == "__main__":
    analyzer = ExplanatoryNotesAnalyzer()
    if analyzer.test_connection():
        analyzer.print_report()
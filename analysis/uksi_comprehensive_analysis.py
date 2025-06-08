"""Comprehensive UKSI digitization analysis tool."""

from base_analyzer import BaseAnalyzer, get_output_path
from datetime import datetime
from collections import defaultdict, Counter
import re
import json


class UKSIComprehensiveAnalyzer(BaseAnalyzer):
    """Comprehensive analyzer for UKSI digitization patterns."""
    
    def __init__(self, index_name="logs-pipeline"):
        super().__init__(index_name)
        self.start_year = 1960
        self.end_year = 2025
    
    def get_all_uksi_logs(self, hours_back=None):  # None means all time
        """Get all UKSI-related logs from the specified time window or all time."""
        
        # Build base queries
        success_base = {
            "bool": {
                "must": [
                    {"match_phrase": {"message": "Parsed legislation"}},
                    {"wildcard": {"message": "*uksi*"}},
                    {"match": {"level": "INFO"}}
                ]
            }
        }
        
        failure_base = {
            "bool": {
                "should": [
                    {
                        "bool": {
                            "must": [
                                {"match_phrase": {"message": "no body found"}},
                                {"wildcard": {"doc_id.keyword": "*uksi*"}}
                            ]
                        }
                    },
                    {
                        "bool": {
                            "must": [
                                {"match_phrase": {"message": "no body found"}},
                                {"wildcard": {"message": "*uksi*"}}
                            ]
                        }
                    }
                ],
                "minimum_should_match": 1,
                "must": [
                    {"match": {"level": "ERROR"}}
                ]
            }
        }
        
        # Add time filter only if hours_back is specified
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
            success_base["bool"].update(time_filter)
            failure_base["bool"].update(time_filter)
        
        # Get successful parses
        success_query = {
            "query": success_base,
            "size": 10000,
            "_source": ["message", "timestamp"]
        }
        
        successful = self.search_logs(success_query)
        
        # Get PDF failures
        failure_query = {
            "query": failure_base,
            "size": 10000,
            "_source": ["doc_id", "message", "timestamp"]
        }
        
        failures = self.search_logs(failure_query)
        
        return successful, failures
    
    def get_total_counts(self):
        """Get total counts of successful and failed UKSI processing."""
        
        # Count successful
        success_count_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "Parsed legislation"}},
                        {"wildcard": {"message": "*uksi*"}}
                    ]
                }
            }
        }
        
        # Count failures
        failure_count_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "no body found"}},
                        {"wildcard": {"doc_id.keyword": "*uksi*"}}
                    ]
                }
            }
        }
        
        try:
            success_response = self.es.count(index=self.index_name, body=success_count_query)
            failure_response = self.es.count(index=self.index_name, body=failure_count_query)
            
            return success_response["count"], failure_response["count"]
        except:
            return 0, 0
    
    def extract_uksi_info(self, text):
        """Extract UKSI year and number from text."""
        match = re.search(r'/uksi/(\d{4})/(\d+)', text)
        if match:
            year = int(match.group(1))
            number = int(match.group(2))
            return year, number
        return None, None
    
    def get_complete_uksi_stats(self):
        """Get complete UKSI statistics using aggregations for accuracy."""
        
        # Aggregate successful parses by year
        success_agg_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "Parsed legislation"}},
                        {"wildcard": {"message": "*uksi*"}}
                    ]
                }
            },
            "size": 0,
            "aggs": {
                "by_year": {
                    "terms": {
                        "script": {
                            "source": """
                                def matcher = /\\/uksi\\/(\\d{4})\\/(\\d+)/.matcher(params._source.message);
                                if (matcher.find()) {
                                    return matcher.group(1);
                                }
                                return null;
                            """
                        },
                        "size": 100
                    },
                    "aggs": {
                        "unique_docs": {
                            "cardinality": {
                                "script": {
                                    "source": """
                                        def matcher = /\\/uksi\\/(\\d{4})\\/(\\d+)/.matcher(params._source.message);
                                        if (matcher.find()) {
                                            return matcher.group(1) + "/" + matcher.group(2);
                                        }
                                        return null;
                                    """
                                }
                            }
                        }
                    }
                }
            }
        }
        
        # Aggregate failures by year
        failure_agg_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "no body found"}},
                        {"match": {"level": "ERROR"}}
                    ],
                    "should": [
                        {"wildcard": {"doc_id.keyword": "*uksi*"}},
                        {"wildcard": {"message": "*uksi*"}}
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": 0,
            "aggs": {
                "by_year": {
                    "terms": {
                        "script": {
                            "source": """
                                def text = params._source.doc_id != null ? params._source.doc_id : params._source.message;
                                def matcher = /\\/uksi\\/(\\d{4})\\/(\\d+)/.matcher(text);
                                if (matcher.find()) {
                                    return matcher.group(1);
                                }
                                return null;
                            """
                        },
                        "size": 100
                    },
                    "aggs": {
                        "unique_docs": {
                            "cardinality": {
                                "script": {
                                    "source": """
                                        def text = params._source.doc_id != null ? params._source.doc_id : params._source.message;
                                        def matcher = /\\/uksi\\/(\\d{4})\\/(\\d+)/.matcher(text);
                                        if (matcher.find()) {
                                            return matcher.group(1) + "/" + matcher.group(2);
                                        }
                                        return null;
                                    """
                                }
                            }
                        }
                    }
                }
            }
        }
        
        try:
            success_response = self.es.search(index=self.index_name, body=success_agg_query)
            failure_response = self.es.search(index=self.index_name, body=failure_agg_query)
            
            success_by_year = {}
            for bucket in success_response.get("aggregations", {}).get("by_year", {}).get("buckets", []):
                year = bucket.get("key")
                if year and year.isdigit():
                    success_by_year[int(year)] = bucket.get("unique_docs", {}).get("value", 0)
            
            failure_by_year = {}
            for bucket in failure_response.get("aggregations", {}).get("by_year", {}).get("buckets", []):
                year = bucket.get("key")
                if year and year.isdigit():
                    failure_by_year[int(year)] = bucket.get("unique_docs", {}).get("value", 0)
            
            return success_by_year, failure_by_year
            
        except Exception as e:
            print(f"Error getting complete stats: {e}")
            return {}, {}
    
    def analyze_year_range(self, year_data):
        """Analyze a specific range of years and return insights."""
        insights = []
        
        # Find first year with any digitization
        first_digital = None
        for year in sorted(year_data.keys()):
            if len(year_data[year]["xml"]) > 0:
                first_digital = year
                break
        
        if first_digital:
            insights.append(f"First digitized UKSI documents appear in: {first_digital}")
        
        # Find years with highest digitization rates
        high_digital_years = []
        for year, data in year_data.items():
            total = len(data["xml"]) + len(data["pdf"])
            if total > 0:
                rate = (len(data["xml"]) / total) * 100
                if rate > 90:
                    high_digital_years.append((year, rate))
        
        if high_digital_years:
            high_digital_years.sort()
            insights.append(f"Years with >90% digitization: {[f'{y} ({r:.1f}%)' for y, r in high_digital_years]}")
        
        return insights
    
    def analyze_comprehensive(self, use_all_time=False):
        """Perform comprehensive UKSI digitization analysis."""
        
        # Initialize results dictionary
        results = {
            "analysis_timestamp": datetime.now().isoformat(),
            "analysis_mode": "all-time" if use_all_time else "recent-7-days",
            "year_range": f"{self.start_year}-{self.end_year}",
            "summary": {},
            "year_breakdown": {},
            "insights": []
        }
        
        print("=" * 80)
        print("COMPREHENSIVE UKSI DIGITIZATION ANALYSIS")
        print("=" * 80)
        print(f"Analysis mode: {'All-time data' if use_all_time else 'Recent processing (7 days)'}")
        print(f"Year range: {self.start_year} - {self.end_year}")
        
        # Get total counts first
        total_success, total_failures = self.get_total_counts()
        print(f"\nTotal counts in database:")
        print(f"  Successful parses: {total_success:,}")
        print(f"  PDF failures: {total_failures:,}")
        
        # Store summary statistics
        results["summary"]["total_successful_parses"] = total_success
        results["summary"]["total_pdf_failures"] = total_failures
        results["summary"]["total_documents"] = total_success + total_failures
        
        if total_success + total_failures > 0:
            overall_rate = (total_success / (total_success + total_failures)) * 100
            print(f"  Overall digitization rate: {overall_rate:.1f}%")
            results["summary"]["overall_digitization_rate"] = round(overall_rate, 1)
        
        # Get complete aggregated statistics
        if use_all_time:
            print("\nGetting complete statistics from all-time data...")
            success_by_year_complete, failure_by_year_complete = self.get_complete_uksi_stats()
            
            if success_by_year_complete or failure_by_year_complete:
                print("\n" + "="*85)
                print("COMPLETE YEAR-BY-YEAR BREAKDOWN (All-Time Data)")
                print("="*85)
                print(f"{'Year':<6} {'XML':<10} {'PDF':<10} {'Total':<10} {'Rate %':<10} {'Status':<25}")
                print("-" * 85)
                
                all_years = sorted(set(success_by_year_complete.keys()) | set(failure_by_year_complete.keys()))
                
                for year in all_years:
                    if self.start_year <= year <= self.end_year:
                        xml_count = int(success_by_year_complete.get(year, 0))
                        pdf_count = int(failure_by_year_complete.get(year, 0))
                        total = xml_count + pdf_count
                        
                        if total > 0:
                            rate = (xml_count / total) * 100
                            
                            # Status indicator
                            if rate == 0:
                                status = "❌ No digitization"
                            elif rate >= 95:
                                status = "✅ Nearly complete"
                            elif rate > 50:
                                status = "🟡 Majority digitized"
                            elif rate > 20:
                                status = "🟠 Partial digitization"
                            else:
                                status = "🔴 Minimal digitization"
                            
                            print(f"{year:<6} {xml_count:<10} {pdf_count:<10} {total:<10} {rate:<10.1f} {status:<25}")
                            
                            # Store year data
                            results["year_breakdown"][year] = {
                                "xml_count": xml_count,
                                "pdf_count": pdf_count,
                                "total": total,
                                "digitization_rate": round(rate, 1),
                                "status": status
                            }
                
                print()
                
                # Save results and return
                output_path = get_output_path("uksi_comprehensive_analysis.json")
                with open(output_path, "w") as f:
                    json.dump(results, f, indent=2)
                print(f"\nDetailed results saved to: {output_path}")
                
                return  # Skip the rest if we have complete data
        
        # Get recent processing details
        hours_back = 168  # 7 days
        print(f"\nAnalyzing recent processing (last {hours_back} hours)...")
        successful, failures = self.get_all_uksi_logs(hours_back)
        
        print(f"  Found {len(successful)} successful parses")
        print(f"  Found {len(failures)} PDF failures")
        
        # Process by year
        year_data = defaultdict(lambda: {"xml": set(), "pdf": set()})
        
        for entry in successful:
            year, num = self.extract_uksi_info(entry.get("message", ""))
            if year and num and self.start_year <= year <= self.end_year:
                year_data[year]["xml"].add(num)
        
        for entry in failures:
            # Try doc_id first, then message
            doc_id = entry.get("doc_id", "")
            if doc_id:
                year, num = self.extract_uksi_info(doc_id)
            else:
                year, num = self.extract_uksi_info(entry.get("message", ""))
            
            if year and num and self.start_year <= year <= self.end_year:
                year_data[year]["pdf"].add(num)
        
        # Year-by-year breakdown
        all_years = sorted(year_data.keys())
        
        if all_years:
            print("\n" + "="*85)
            print("YEAR-BY-YEAR BREAKDOWN (Recent Processing)")
            print("="*85)
            print(f"{'Year':<6} {'XML':<8} {'PDF':<8} {'Total':<10} {'Rate %':<10} {'Status':<25} {'Document Range':<20}")
            print("-" * 85)
            
            decade_stats = defaultdict(lambda: {"xml": 0, "pdf": 0})
            
            for year in all_years:
                xml_count = len(year_data[year]["xml"])
                pdf_count = len(year_data[year]["pdf"])
                total = xml_count + pdf_count
                
                if total > 0:
                    rate = (xml_count / total) * 100
                    decade = (year // 10) * 10
                    decade_stats[decade]["xml"] += xml_count
                    decade_stats[decade]["pdf"] += pdf_count
                    
                    # Status indicator
                    if rate == 0:
                        status = "❌ No digitization"
                    elif rate == 100:
                        status = "✅ Fully digitized"
                    elif rate > 90:
                        status = "🟢 Nearly complete"
                    elif rate > 50:
                        status = "🟡 Majority digitized"
                    elif rate > 10:
                        status = "🟠 Partial digitization"
                    else:
                        status = "🔴 Minimal digitization"
                    
                    # Document range
                    all_nums = list(year_data[year]["xml"]) + list(year_data[year]["pdf"])
                    if all_nums:
                        doc_range = f"{min(all_nums)}-{max(all_nums)}"
                    else:
                        doc_range = "N/A"
                    
                    print(f"{year:<6} {xml_count:<8} {pdf_count:<8} {total:<10} {rate:<10.1f} {status:<25} {doc_range:<20}")
            
            # Decade summary
            print("\n" + "="*85)
            print("DECADE SUMMARY")
            print("="*85)
            
            for decade in sorted(decade_stats.keys()):
                xml = decade_stats[decade]["xml"]
                pdf = decade_stats[decade]["pdf"]
                total = xml + pdf
                if total > 0:
                    pct = (xml / total) * 100
                    print(f"{decade}s: {xml:>6} XML, {pdf:>6} PDF ({pct:>5.1f}% digitized)")
        
        # Sample analysis for specific years
        print("\n" + "="*85)
        print("DETAILED YEAR ANALYSIS (Sample Years)")
        print("="*85)
        
        sample_years = [1970, 1975, 1978, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
        for year in sample_years:
            if year in year_data and (year_data[year]["xml"] or year_data[year]["pdf"]):
                xml_nums = sorted(list(year_data[year]["xml"]))[:5]
                pdf_nums = sorted(list(year_data[year]["pdf"]))[:5]
                
                print(f"\n{year}:")
                print(f"  Total documents: {len(year_data[year]['xml']) + len(year_data[year]['pdf'])}")
                print(f"  XML: {len(year_data[year]['xml'])}, PDF: {len(year_data[year]['pdf'])}")
                
                if xml_nums:
                    print(f"  Sample XML doc numbers: {xml_nums}")
                if pdf_nums:
                    print(f"  Sample PDF doc numbers: {pdf_nums}")
        
        # Insights
        print("\n" + "="*85)
        print("KEY INSIGHTS")
        print("="*85)
        
        insights = self.analyze_year_range(year_data)
        for insight in insights:
            print(f"• {insight}")
        
        # Modern vs Historical comparison
        modern_xml = sum(len(year_data[y]["xml"]) for y in all_years if y >= 2000)
        modern_pdf = sum(len(year_data[y]["pdf"]) for y in all_years if y >= 2000)
        historical_xml = sum(len(year_data[y]["xml"]) for y in all_years if y < 2000)
        historical_pdf = sum(len(year_data[y]["pdf"]) for y in all_years if y < 2000)
        
        if modern_xml + modern_pdf > 0:
            modern_rate = (modern_xml / (modern_xml + modern_pdf)) * 100
            print(f"\n• Modern era (2000+): {modern_rate:.1f}% digitized ({modern_xml} XML, {modern_pdf} PDF)")
        
        if historical_xml + historical_pdf > 0:
            historical_rate = (historical_xml / (historical_xml + historical_pdf)) * 100
            print(f"• Historical (pre-2000): {historical_rate:.1f}% digitized ({historical_xml} XML, {historical_pdf} PDF)")
        
        # Save results
        results = {
            "analysis_date": datetime.now().isoformat(),
            "hours_analyzed": hours_back,
            "year_range": f"{self.start_year}-{self.end_year}",
            "total_counts": {
                "all_time_success": total_success,
                "all_time_failures": total_failures,
                "overall_digitization_rate": overall_rate if 'overall_rate' in locals() else 0
            },
            "recent_processing": {
                "successful_parses": len(successful),
                "pdf_failures": len(failures)
            },
            "by_year": {
                str(year): {
                    "xml_count": len(year_data[year]["xml"]),
                    "pdf_count": len(year_data[year]["pdf"]),
                    "digitization_rate": (len(year_data[year]["xml"]) / 
                                        (len(year_data[year]["xml"]) + len(year_data[year]["pdf"])) * 100)
                                        if (len(year_data[year]["xml"]) + len(year_data[year]["pdf"])) > 0 else 0
                }
                for year in year_data.keys()
            } if year_data else {}
        }
        
        with open("uksi_comprehensive_analysis.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print("\n✓ Results saved to uksi_comprehensive_analysis.json")
        
        # Add warning about data accuracy only if not using all-time data
        if not use_all_time:
            print("\n" + "="*85)
            print("⚠️  DATA ACCURACY WARNING")
            print("="*85)
            print("\nThe year-by-year breakdown may show misleading results due to:")
            print("1. Different pipeline runs processing different year ranges")
            print("2. Time window limitations in log queries")
            print("3. Logs from multiple partial runs being aggregated")
            print("\nFor accurate results, run with --all-time flag: python uksi_comprehensive_analysis.py --all-time")
        
        # Add verification section
        print("\n" + "="*85)
        print("REAL-TIME VERIFICATION (Last 24 hours)")
        print("="*85)
        
        # Check specific years that showed 100% to verify
        verify_years = [1974, 1975, 1976, 1977, 1978]
        for year in verify_years:
            # Query for this specific year's failures in last 24h
            verify_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"wildcard": {"message": f"*uksi/{year}/*"}},
                            {"match": {"level": "ERROR"}},
                            {"match_phrase": {"message": "no body found"}}
                        ],
                        "filter": {
                            "range": {
                                "timestamp": {
                                    "gte": "now-24h"
                                }
                            }
                        }
                    }
                },
                "size": 5
            }
            
            verify_results = self.search_logs(verify_query)
            if verify_results:
                print(f"\n{year}: Found {len(verify_results)} PDF errors in last 24h (showing first few):")
                for r in verify_results[:3]:
                    msg = r.get("message", "")
                    match = re.search(r'/uksi/\d+/(\d+)', msg)
                    if match:
                        doc_num = match.group(1)
                        print(f"  - Document {doc_num}: PDF only")
        
        print("\n" + "="*85)
        print("ANALYSIS COMPLETE")
        print("="*85)
        
        # Save results to JSON
        output_path = get_output_path("uksi_comprehensive_analysis.json")
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    import sys
    
    analyzer = UKSIComprehensiveAnalyzer()
    if analyzer.test_connection():
        # Check if --all-time flag is provided
        use_all_time = "--all-time" in sys.argv
        analyzer.analyze_comprehensive(use_all_time=use_all_time)
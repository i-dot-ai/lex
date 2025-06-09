"""Comprehensive XML completeness analysis combining general and type-specific analysis."""

from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from datetime import datetime
from base_analyzer import BaseAnalyzer, get_output_path
from common_utils import extract_year_from_message, extract_legislation_type, extract_document_id
import json
import re


class XMLCompletenessComprehensiveAnalyzer(BaseAnalyzer):
    """Comprehensive analyzer for XML parsing success/failure rates."""

    def __init__(self):
        super().__init__()

    def get_xml_completeness_aggregated(self, doc_type: Optional[str] = None) -> Tuple[Dict, Dict]:
        """Get XML completeness using aggregation for accurate statistics."""

        # Build base queries
        base_success_query = {
            "bool": {
                "must": [
                    {"match_phrase": {"message": "Parsed legislation"}},
                    {"match": {"level": "INFO"}},
                ]
            }
        }

        base_failure_query = {
            "bool": {
                "should": [
                    {"match_phrase": {"message": "no body found"}},
                    {"match": {"message": "likely a pdf"}},
                ],
                "minimum_should_match": 1,
                "must": [{"match": {"level": "ERROR"}}],
            }
        }

        # Add document type filter if specified
        if doc_type:
            type_filter = {"wildcard": {"message": f"*{doc_type}*"}}
            base_success_query["bool"]["must"].append(type_filter)
            base_failure_query["bool"]["must"].append(type_filter)

        # Success aggregation query
        success_agg_query = {
            "query": base_success_query,
            "size": 0,
            "aggs": {
                "by_year": {
                    "terms": {
                        "script": {
                            "source": """
                                def matcher = /\\/(\\d{4})\\//.matcher(params._source.message);
                                if (matcher.find()) {
                                    return matcher.group(1);
                                }
                                return null;
                            """
                        },
                        "size": 1000,
                    },
                    "aggs": {
                        "by_type": {
                            "terms": {
                                "script": {
                                    "source": """
                                        def types = ['ukpga', 'uksi', 'ukla', 'ukppa', 'ukcm', 'ukmo', 'ukci', 'uksro',
                                                    'asp', 'asc', 'anaw', 'aep', 'aip', 'apgb', 'aosp', 'apni',
                                                    'mwa', 'mnia', 'nia', 'nisi', 'nisr', 'nisro',
                                                    'ssi', 'wsi', 'gbla', 'eur', 'eudr', 'eudn'];
                                        for (type in types) {
                                            if (params._source.message.toLowerCase().contains('/' + type + '/')) {
                                                return type;
                                            }
                                        }
                                        return 'unknown';
                                    """
                                },
                                "size": 50,
                            },
                            "aggs": {
                                "unique_docs": {
                                    "cardinality": {
                                        "script": {
                                            "source": """
                                                def matcher = /\\/([a-z]+)\\/(\\d{4})\\/(\\d+)/.matcher(params._source.message.toLowerCase());
                                                if (matcher.find()) {
                                                    return matcher.group(1) + "/" + matcher.group(2) + "/" + matcher.group(3);
                                                }
                                                return null;
                                            """
                                        }
                                    }
                                }
                            },
                        }
                    },
                }
            },
        }

        # Failure aggregation query
        failure_agg_query = {
            "query": base_failure_query,
            "size": 0,
            "aggs": {
                "by_year": {
                    "terms": {
                        "script": {
                            "source": """
                                def text = params._source.doc_id != null ? params._source.doc_id : params._source.message;
                                def matcher = /\\/(\\d{4})\\//.matcher(text);
                                if (matcher.find()) {
                                    return matcher.group(1);
                                }
                                return null;
                            """
                        },
                        "size": 1000,
                    },
                    "aggs": {
                        "by_type": {
                            "terms": {
                                "script": {
                                    "source": """
                                        def text = params._source.doc_id != null ? params._source.doc_id : params._source.message;
                                        def types = ['ukpga', 'uksi', 'ukla', 'ukppa', 'ukcm', 'ukmo', 'ukci', 'uksro',
                                                    'asp', 'asc', 'anaw', 'aep', 'aip', 'apgb', 'aosp', 'apni',
                                                    'mwa', 'mnia', 'nia', 'nisi', 'nisr', 'nisro',
                                                    'ssi', 'wsi', 'gbla', 'eur', 'eudr', 'eudn'];
                                        for (type in types) {
                                            if (text.toLowerCase().contains('/' + type + '/')) {
                                                return type;
                                            }
                                        }
                                        return 'unknown';
                                    """
                                },
                                "size": 50,
                            },
                            "aggs": {
                                "unique_docs": {
                                    "cardinality": {
                                        "script": {
                                            "source": """
                                                def text = params._source.doc_id != null ? params._source.doc_id : params._source.message;
                                                def matcher = /\\/([a-z]+)\\/(\\d{4})\\/(\\d+)/.matcher(text.toLowerCase());
                                                if (matcher.find()) {
                                                    return matcher.group(1) + "/" + matcher.group(2) + "/" + matcher.group(3);
                                                }
                                                return null;
                                            """
                                        }
                                    }
                                }
                            },
                        }
                    },
                }
            },
        }

        try:
            success_response = self.es.search(index=self.index_name, body=success_agg_query)
            failure_response = self.es.search(index=self.index_name, body=failure_agg_query)

            # Process success data
            success_data = {}
            for year_bucket in (
                success_response.get("aggregations", {}).get("by_year", {}).get("buckets", [])
            ):
                year = year_bucket.get("key")
                if year and year.isdigit():
                    year_int = int(year)
                    success_data[year_int] = {}

                    for type_bucket in year_bucket.get("by_type", {}).get("buckets", []):
                        leg_type = type_bucket.get("key")
                        count = type_bucket.get("unique_docs", {}).get("value", 0)
                        if leg_type != "unknown":
                            success_data[year_int][leg_type] = int(count)

            # Process failure data
            failure_data = {}
            for year_bucket in (
                failure_response.get("aggregations", {}).get("by_year", {}).get("buckets", [])
            ):
                year = year_bucket.get("key")
                if year and year.isdigit():
                    year_int = int(year)
                    failure_data[year_int] = {}

                    for type_bucket in year_bucket.get("by_type", {}).get("buckets", []):
                        leg_type = type_bucket.get("key")
                        count = type_bucket.get("unique_docs", {}).get("value", 0)
                        if leg_type != "unknown":
                            failure_data[year_int][leg_type] = int(count)

            return success_data, failure_data

        except Exception as e:
            print(f"Error getting aggregated stats: {e}")
            return {}, {}

    def analyze_by_type(self, leg_type: str) -> Dict:
        """Analyze XML completeness for a specific legislation type."""
        success_data, failure_data = self.get_xml_completeness_aggregated(doc_type=leg_type)

        results = {
            "type": leg_type,
            "analysis_timestamp": datetime.now().isoformat(),
            "summary": {"total_xml": 0, "total_pdf": 0, "overall_digitization_rate": 0},
            "by_year": {},
            "by_decade": {},
            "insights": [],
        }

        # Calculate statistics by year
        all_years = sorted(set(success_data.keys()) | set(failure_data.keys()))

        for year in all_years:
            xml_count = sum(success_data.get(year, {}).values())
            pdf_count = sum(failure_data.get(year, {}).values())
            total = xml_count + pdf_count

            if total > 0:
                rate = (xml_count / total) * 100
                results["by_year"][year] = {
                    "xml_count": xml_count,
                    "pdf_count": pdf_count,
                    "total": total,
                    "digitization_rate": round(rate, 1),
                }

                # Add to totals
                results["summary"]["total_xml"] += xml_count
                results["summary"]["total_pdf"] += pdf_count

                # Decade aggregation
                decade = (year // 10) * 10
                if decade not in results["by_decade"]:
                    results["by_decade"][decade] = {"xml": 0, "pdf": 0}
                results["by_decade"][decade]["xml"] += xml_count
                results["by_decade"][decade]["pdf"] += pdf_count

        # Calculate overall rate
        total_all = results["summary"]["total_xml"] + results["summary"]["total_pdf"]
        if total_all > 0:
            results["summary"]["overall_digitization_rate"] = round(
                (results["summary"]["total_xml"] / total_all) * 100, 1
            )

        # Generate insights
        if all_years:
            # First year with data
            first_year = min(all_years)
            results["insights"].append(f"First {leg_type} documents appear in: {first_year}")

            # Find years with high digitization
            high_digital_years = []
            for year, data in results["by_year"].items():
                if data["digitization_rate"] > 90:
                    high_digital_years.append(year)

            if high_digital_years:
                results["insights"].append(
                    f"Years with >90% digitization: {len(high_digital_years)} "
                    f"({min(high_digital_years)}-{max(high_digital_years)})"
                )

            # Modern vs historical
            modern_years = [y for y in all_years if y >= 2000]
            historical_years = [y for y in all_years if y < 2000]

            if modern_years:
                modern_xml = sum(results["by_year"][y]["xml_count"] for y in modern_years)
                modern_pdf = sum(results["by_year"][y]["pdf_count"] for y in modern_years)
                modern_total = modern_xml + modern_pdf
                if modern_total > 0:
                    modern_rate = (modern_xml / modern_total) * 100
                    results["insights"].append(f"Modern era (2000+): {modern_rate:.1f}% digitized")

            if historical_years:
                hist_xml = sum(results["by_year"][y]["xml_count"] for y in historical_years)
                hist_pdf = sum(results["by_year"][y]["pdf_count"] for y in historical_years)
                hist_total = hist_xml + hist_pdf
                if hist_total > 0:
                    hist_rate = (hist_xml / hist_total) * 100
                    results["insights"].append(f"Historical (pre-2000): {hist_rate:.1f}% digitized")

        return results

    def generate_heatmap_data(self) -> Dict[str, Dict[int, float]]:
        """Generate heatmap data for type × year digitization rates."""
        success_data, failure_data = self.get_xml_completeness_aggregated()

        heatmap = defaultdict(dict)

        # Get all types and years
        all_types = set()
        all_years = set()

        for year_data in success_data.values():
            all_types.update(year_data.keys())
        for year_data in failure_data.values():
            all_types.update(year_data.keys())

        all_years.update(success_data.keys())
        all_years.update(failure_data.keys())

        # Calculate rates for each type/year combination
        for leg_type in sorted(all_types):
            for year in sorted(all_years):
                xml_count = success_data.get(year, {}).get(leg_type, 0)
                pdf_count = failure_data.get(year, {}).get(leg_type, 0)
                total = xml_count + pdf_count

                if total > 0:
                    rate = (xml_count / total) * 100
                    # Only include in heatmap if there's significant data
                    if total >= 10 or rate == 0:  # Include complete failures
                        heatmap[leg_type][year] = round(rate, 1)

        return dict(heatmap)

    def print_report(self, specific_type: Optional[str] = None):
        """Print comprehensive XML completeness report."""
        print("=" * 80)
        print("COMPREHENSIVE XML COMPLETENESS ANALYSIS")
        print("=" * 80)

        if specific_type:
            # Analyze specific type
            results = self.analyze_by_type(specific_type)

            print(f"\nAnalysis for {specific_type.upper()}")
            print(
                f"Total documents: {results['summary']['total_xml'] + results['summary']['total_pdf']:,}"
            )
            print(f"XML available: {results['summary']['total_xml']:,}")
            print(f"PDF only: {results['summary']['total_pdf']:,}")
            print(
                f"Overall digitization rate: {results['summary']['overall_digitization_rate']:.1f}%"
            )

            # Year by year breakdown
            print("\n" + "-" * 60)
            print("YEAR-BY-YEAR BREAKDOWN")
            print("-" * 60)
            print(f"{'Year':<6} {'XML':<10} {'PDF':<10} {'Total':<10} {'Rate %':<10}")
            print("-" * 60)

            for year in sorted(results["by_year"].keys()):
                data = results["by_year"][year]
                print(
                    f"{year:<6} {data['xml_count']:<10} {data['pdf_count']:<10} "
                    f"{data['total']:<10} {data['digitization_rate']:<10.1f}"
                )

            # Insights
            if results["insights"]:
                print("\n" + "-" * 60)
                print("INSIGHTS")
                print("-" * 60)
                for insight in results["insights"]:
                    print(f"• {insight}")

            # Save results
            output_file = get_output_path(f"xml_completeness_{specific_type}.json")
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nDetailed results saved to: {output_file}")

        else:
            # General analysis
            success_data, failure_data = self.get_xml_completeness_aggregated()

            # Calculate totals by year
            by_year = {}
            all_years = sorted(set(success_data.keys()) | set(failure_data.keys()))

            for year in all_years:
                xml_total = sum(success_data.get(year, {}).values())
                pdf_total = sum(failure_data.get(year, {}).values())
                total = xml_total + pdf_total

                if total > 0:
                    by_year[year] = {
                        "total": total,
                        "xml_success": xml_total,
                        "pdf_fallback": pdf_total,
                        "other_errors": 0,
                    }

            # Calculate totals by type
            by_type = defaultdict(lambda: {"total": 0, "xml_success": 0, "pdf_fallback": 0})

            for year_data in success_data.values():
                for leg_type, count in year_data.items():
                    by_type[leg_type]["xml_success"] += count
                    by_type[leg_type]["total"] += count

            for year_data in failure_data.values():
                for leg_type, count in year_data.items():
                    by_type[leg_type]["pdf_fallback"] += count
                    by_type[leg_type]["total"] += count

            # Print summary
            total_xml = sum(d["xml_success"] for d in by_year.values())
            total_pdf = sum(d["pdf_fallback"] for d in by_year.values())
            total_all = total_xml + total_pdf

            print(f"\nTotal documents analyzed: {total_all:,}")
            print(f"XML available: {total_xml:,} ({100 * total_xml / total_all:.1f}%)")
            print(f"PDF only: {total_pdf:,} ({100 * total_pdf / total_all:.1f}%)")

            # By type summary
            print("\n" + "-" * 80)
            print("XML COMPLETENESS BY DOCUMENT TYPE")
            print("-" * 80)
            print(f"{'Type':<10} {'Total':<12} {'XML':<12} {'PDF':<12} {'XML %':<10}")
            print("-" * 80)

            for leg_type in sorted(by_type.keys(), key=lambda x: by_type[x]["total"], reverse=True)[
                :20
            ]:
                data = by_type[leg_type]
                if data["total"] > 0:
                    xml_pct = 100 * data["xml_success"] / data["total"]
                    print(
                        f"{leg_type:<10} {data['total']:<12,} {data['xml_success']:<12,} "
                        f"{data['pdf_fallback']:<12,} {xml_pct:<10.1f}"
                    )

            # Generate heatmap
            heatmap = self.generate_heatmap_data()

            # Save comprehensive results
            results = {
                "summary": {
                    "total_logs": total_all,
                    "analysis_timestamp": datetime.now().isoformat(),
                    "data_source": "all-time aggregated data",
                },
                "by_year": by_year,
                "by_type": dict(by_type),
                "heatmap": heatmap,
            }

            output_file = get_output_path("xml_completeness_report.json")
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)

            print("\n" + "=" * 80)
            print(f"Detailed results saved to: {output_file}")


if __name__ == "__main__":
    import sys

    analyzer = XMLCompletenessComprehensiveAnalyzer()
    if analyzer.test_connection():
        # Check for specific type argument
        if len(sys.argv) > 1 and sys.argv[1] != "--all":
            specific_type = sys.argv[1]
            analyzer.print_report(specific_type=specific_type)
        else:
            analyzer.print_report()

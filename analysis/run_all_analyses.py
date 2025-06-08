"""Run all analysis scripts and generate comprehensive reports."""

import subprocess
import sys
from datetime import datetime
import os


def run_script(script_name: str, args: list = None) -> bool:
    """Run a Python script and return success status."""
    print(f"\n{'='*60}")
    print(f"Running {script_name}...")
    print(f"{'='*60}")
    
    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR running {script_name}:")
        print(e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    """Run all analysis scripts in sequence."""
    print(f"Starting comprehensive analysis at {datetime.now()}")
    
    # Don't create analysis directory if we're already in it
    if os.path.basename(os.getcwd()) != 'analysis':
        os.makedirs("analysis", exist_ok=True)
    
    # List of scripts to run in order
    scripts = [
        ("pipeline_monitoring.py", ["24"]),  # Last 24 hours
        ("error_type_analyzer.py", []),
        ("xml_completeness_analyzer.py", []), 
        ("processing_performance_analyzer.py", []),
        ("explanatory_notes_analyzer.py", []),
        ("extract_failed_xml_urls.py", []),
        ("uksi_comprehensive_analysis.py", ["--all-time"])
    ]
    
    results = {}
    
    for script_info in scripts:
        if isinstance(script_info, tuple):
            script, args = script_info
        else:
            script, args = script_info, []
        results[script] = run_script(script, args)
    
    # Summary
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"Completed at {datetime.now()}")
    print("\nResults:")
    for script, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"  {script:<40} {status}")
    
    # List generated files
    print("\nGenerated files:")
    output_files = [
        "error_type_report.json",
        "xml_completeness_report.json",
        "performance_report.json",
        "explanatory_notes_report.json",
        "failed_xml_urls.json",
        "validation_error_documents.json",
        "pdf_fallback_urls.json",
        "successful_xml_urls_sample.json",
        "xml_error_analysis.json",
        "uksi_comprehensive_analysis.json"
    ]
    
    for file in output_files:
        # Handle both running from root and from analysis directory
        if os.path.basename(os.getcwd()) == 'analysis':
            path = file
        else:
            path = f"analysis/{file}"
            
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024  # KB
            print(f"  {file:<40} {size:>8.1f} KB")
        else:
            print(f"  {file:<40} NOT FOUND")


if __name__ == "__main__":
    main()
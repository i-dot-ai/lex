# Lex Pipeline Analysis Tools

This directory contains analysis scripts for monitoring and analyzing the Lex pipeline's performance, errors, and data quality.

## Quick Start - Run All Analyses

```bash
# Run all analyses (includes UKSI analyses)
python run_all_analyses.py
```

## Core Scripts

### Base Infrastructure
- **`base_analyzer.py`** - Base class providing Elasticsearch connection and common query methods

### Pipeline Monitoring
- **`pipeline_monitoring.py`** - Comprehensive pipeline status, progress tracking, and logging quality analysis
  - Monitors pipeline completions and active runs
  - Checks structured logging implementation
  - Tracks throughput and batch processing metrics
  - Usage: `python pipeline_monitoring.py [hours]` (default: 24 hours)

### Error Analysis
- **`error_type_analyzer.py`** - Categorizes and analyzes all error types including non-PDF errors
  - Tracks PDF fallbacks, HTTP errors, parsing errors, validation errors
  - Provides error distribution by type and document type
  - Includes CommentaryCitation and other validation error analysis
  
- **`extract_failed_xml_urls.py`** - Extracts URLs for failed documents and validation errors
  - Generates lists of documents needing re-processing
  - Includes validation error document extraction
  - Outputs: failed XML URLs, validation errors, PDF fallbacks, success samples

### Data Quality Analysis
- **`xml_completeness_analyzer.py`** - Analyzes XML parsing success rates and PDF fallback patterns
  - Shows XML availability by year and legislation type using all-time aggregated data
  - Identifies patterns in digitization
  - Provides accurate statistics through Elasticsearch aggregations

- **`explanatory_notes_analyzer.py`** - Analyzes explanatory notes coverage
  - Shows availability by year and legislation type
  - Identifies gaps in coverage

### Performance Analysis
- **`processing_performance_analyzer.py`** - Analyzes pipeline throughput and performance metrics
  - Tracks processing speed over time
  - Monitors batch sizes and upload patterns
  - Identifies performance bottlenecks

### UKSI-Specific Analysis
- **`uksi_comprehensive_analysis.py`** - Detailed analysis of UK Statutory Instruments digitization
  - Shows accurate digitization rates when run with `--all-time` flag
  - Provides year-by-year breakdown
  - Usage: `python uksi_comprehensive_analysis.py [--all-time]`

### Orchestration
- **`run_all_analyses.py`** - Runs all analysis scripts in sequence including UKSI analyses
  - Usage: `python run_all_analyses.py`
  - Generates comprehensive report suite for all document types

## Output Files

All scripts generate JSON reports in the `analysis/` directory:

- `error_type_report.json` - Error categorization and statistics
- `xml_completeness_report.json` - XML availability analysis
- `performance_report.json` - Processing performance metrics
- `explanatory_notes_report.json` - Explanatory notes coverage
- `failed_xml_urls.json` - URLs of documents with XML parsing errors
- `validation_error_documents.json` - Documents with validation errors
- `pdf_fallback_urls.json` - Documents only available as PDFs
- `successful_xml_urls_sample.json` - Sample of successfully parsed documents
- `xml_error_analysis.json` - Detailed error pattern analysis
- `uksi_comprehensive_analysis.json` - Detailed UKSI digitization statistics

## Running Individual Scripts

```bash
# Monitor pipeline status (default: last 24 hours)
python pipeline_monitoring.py
python pipeline_monitoring.py 48  # Last 48 hours

# Analyze error types
python error_type_analyzer.py

# Extract failed document URLs
python extract_failed_xml_urls.py

# Analyze XML completeness
python xml_completeness_analyzer.py

# Analyze processing performance
python processing_performance_analyzer.py

# Analyze explanatory notes coverage
python explanatory_notes_analyzer.py
```

## Requirements

- Access to Elasticsearch instance with pipeline logs
- Python packages: elasticsearch, python-dotenv
- Environment variables configured for Elasticsearch connection
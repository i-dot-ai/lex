# Lex Pipeline Analysis Tools

This directory contains Python scripts for analyzing the logs from the Lex pipeline to understand XML completeness, error patterns, and processing performance.

## Overview

The pipeline logs various events during document processing, including:
- Successful XML parsing
- PDF fallbacks (when XML is incomplete)
- Error conditions
- Processing metrics

These analysis tools help identify:
- Which years have better XML digitization
- Which document types are most likely to be PDFs
- Common error patterns
- Processing performance bottlenecks

## Scripts

### 1. `xml_completeness_analyzer.py`
Analyzes XML parsing success rates vs PDF fallbacks:
- Success rates by year (1963-present)
- Success rates by legislation type
- Heatmap of completeness (type × year)

### 2. `error_type_analyzer.py`
Categorizes and analyzes errors:
- Error distribution by category
- Top error patterns
- Error rates by document type
- Error frequency over time

### 3. `processing_performance_analyzer.py`
Analyzes processing speed and efficiency:
- Document throughput (docs/hour)
- Batch size patterns
- Memory usage indicators
- Processing volume by document type

### 4. `explanatory_notes_analyzer.py`
Analyzes explanatory notes coverage:
- Coverage rates by year
- Coverage rates by legislation type
- Coverage trends over time

### 5. `run_all_analyses.py`
Master script that runs all analyses sequentially.

## Usage

### Prerequisites
1. Ensure Elasticsearch is running at `localhost:9200`
2. Ensure the pipeline has been running and generating logs to the `logs-pipeline` index
3. Install required dependencies (if not already installed):
   ```bash
   uv sync
   ```

### Running Individual Analyses

```bash
# From the lex directory
uv run python analysis/xml_completeness_analyzer.py
uv run python analysis/error_type_analyzer.py
uv run python analysis/processing_performance_analyzer.py
uv run python analysis/explanatory_notes_analyzer.py
```

### Running All Analyses

```bash
# From the lex directory
uv run python analysis/run_all_analyses.py
```

## Output

Each script generates:
1. **Console output**: Human-readable summary with key statistics
2. **JSON report**: Detailed data saved to `analysis/*_report.json`

### Report Files
- `xml_completeness_report.json`: XML parsing success rates
- `error_type_report.json`: Error categorization and patterns
- `performance_report.json`: Processing throughput metrics
- `explanatory_notes_report.json`: Explanatory notes coverage

## Key Findings (Typical)

Based on the analysis design, you can expect to find:

1. **XML Completeness**:
   - Older legislation (1960s-1990s) often has lower XML availability
   - Modern legislation (2000s+) typically has better XML coverage
   - Secondary legislation (SIs) may have different patterns than primary

2. **Explanatory Notes**:
   - Very limited before 1990s
   - Improving coverage from 2000s onwards
   - Best coverage for primary legislation (Acts)

3. **Error Patterns**:
   - PDF fallbacks are the most common "error"
   - HTTP errors from rate limiting
   - Parsing errors from malformed XML

4. **Performance**:
   - Batch processing helps manage memory
   - Throughput varies by document complexity
   - Peak processing times correlate with batch uploads

## Customization

To add new analyses:
1. Create a new analyzer class inheriting from `BaseAnalyzer`
2. Implement analysis methods
3. Add a `print_report()` method
4. Add to `run_all_analyses.py`

## Troubleshooting

If connection fails:
- Check Elasticsearch is running: `curl localhost:9200`
- Check authentication settings in `.env`
- Verify the `logs-pipeline` index exists

If no data appears:
- Ensure the pipeline has been running
- Check log level is set appropriately
- Verify logs are being sent to Elasticsearch
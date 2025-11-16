# Ingestion Process Documentation

## Overview

The Lex pipeline ingests UK legislative documents from The National Archives website (legislation.gov.uk) and stores them in Qdrant vector database with hybrid embeddings. The system handles multiple document types with a consistent architecture: **Scraper → Parser → Pipeline → Qdrant**.

## Document Types

The system processes four main document types:

1. **Legislation** - Primary and secondary legislation (Acts, SIs, etc.)
2. **Legislation Sections** - Individual provisions extracted from legislation
3. **Case Law** - Court judgments and decisions
4. **Explanatory Notes** - Explanatory memoranda for legislation
5. **Amendments** - Legislative changes and modifications

## Architecture

### Pipeline Flow

```
1. Scraper (fetch URLs) → 2. Load Content (download XML) → 3. Parser (extract data) → 4. Upload (store in Qdrant with hybrid vectors)
```

### Key Components

#### 1. Scrapers (`src/lex/{type}/scraper.py`)
- Generate URLs by iterating through years and document types
- Download XML content from legislation.gov.uk
- Handle pagination for search results
- Implement checkpointing for resilient processing

#### 2. Parsers (`src/lex/{type}/parser.py`)
- Transform XML/HTML into Pydantic models
- Extract structured data (title, text, metadata)
- Handle different XML schemas and formats
- Validate data integrity

#### 3. Pipelines (`src/lex/{type}/pipeline.py`)
- Orchestrate the scraping and parsing process
- Handle errors and PDF fallbacks
- Generate embeddings and upload to Qdrant
- Implement structured logging

#### 4. Models (`src/lex/{type}/models.py`)
- Define Pydantic data models
- Ensure consistent field types
- Provide computed properties
- Handle data validation

## Running Ingestion

### Sample Data (Quick Testing)
```bash
# Ingest sample of all document types
make ingest-all-sample

# Ingest specific type with limit
make ingest-legislation-sample    # 50 documents
make ingest-caselaw-sample       # 50 documents
```

### Full Data (Production)
```bash
# Ingest all document types
make ingest-all-full

# Ingest specific types
make ingest-legislation-full      # 1963-current, all types
make ingest-caselaw-full         # 2001-current
make ingest-legislation-section-full
```

### Command Line Options
```bash
# Direct command with options
docker compose exec pipeline uv run src/lex/main.py \
  -m legislation \              # Model type
  --years 2020-2023 \          # Year range
  --types uksi ukpga \         # Document types
  --limit 100 \                # Max documents
  --batch-size 50 \            # Qdrant batch size
  --non-interactive \          # No prompts
  --no-checkpoint \            # Disable checkpointing
  --clear-checkpoint           # Start fresh
```

## Document Type Details

### Legislation Types (28 types)

The system supports 28 different legislation types, organized by jurisdiction:

**UK-wide:**
- `ukpga` - UK Public General Acts
- `uksi` - UK Statutory Instruments
- `ukla` - UK Local Acts
- `ukppa` - UK Private and Personal Acts

**Scotland:**
- `asp` - Acts of the Scottish Parliament
- `ssi` - Scottish Statutory Instruments
- `aosp` - Acts of the Old Scottish Parliament

**Wales:**
- `asc`/`anaw` - Acts of Senedd Cymru/National Assembly
- `wsi` - Wales Statutory Instruments
- `mwa` - Measures of the Welsh Assembly

**Northern Ireland:**
- `nia` - Acts of the Northern Ireland Assembly
- `nisr` - Northern Ireland Statutory Rules
- `nisi` - Northern Ireland Orders in Council

**European (pre-Brexit):**
- `eur` - EU Regulations
- `eudr` - EU Directives
- `eudn` - EU Decisions

### URL Patterns

Documents follow predictable URL patterns:
```
https://www.legislation.gov.uk/{type}/{year}/{number}/data.xml
```

Examples:
- `https://www.legislation.gov.uk/ukpga/2023/52/data.xml`
- `https://www.legislation.gov.uk/uksi/2023/1234/data.xml`

## Error Handling

### PDF Fallbacks
Many older documents (especially pre-1987) only exist as PDFs:
- Parser detects "no body found" in XML
- Logs as `processing_status: "pdf_fallback"`
- Continues processing without crashing

### Server Errors
The scraper gracefully handles HTTP 5xx errors:
- Logs warning and skips affected year/type
- Continues processing other documents
- Prevents pipeline crashes

### Rate Limiting
Built-in rate limit handling:
- Exponential backoff with retry
- Circuit breaker pattern
- Checkpoint saves before exit

## Batch Processing

Documents are processed in configurable batches:
- Default batch size: 25 documents (10 for caselaw due to size)
- Batches uploaded to Qdrant using batch upsert with UUID5 idempotency
- Memory efficient for large datasets
- Progress logged every N batches

## Performance Considerations

### Typical Processing Rates
- **Legislation**: ~5-10 documents/second
- **Case Law**: ~2-5 documents/second (larger documents)
- **Sections**: ~20-50 sections/second

### Memory Usage
- Documents processed as generators (not lists)
- Batching prevents memory overflow
- Typical usage: 500MB-1GB for pipeline

### Network Optimization
- HTTP responses cached (14-day TTL)
- Connection pooling via requests session
- Parallel processing not implemented (API friendly)

## Monitoring Progress

### Check Pipeline Status
```bash
# View recent logs
docker compose logs -f pipeline

# Check Qdrant collection counts
curl localhost:6333/collections

# Check specific collection
curl localhost:6333/collections/legislation

# View Qdrant dashboard
open http://localhost:6333/dashboard
```

### Key Metrics
- Documents processed per hour
- Error rates by type
- PDF fallback percentages
- Processing duration by document type
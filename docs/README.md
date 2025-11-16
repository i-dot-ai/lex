# Lex Documentation

Documentation for the Lex UK legislative search system.

## Core Documentation

### [data-models.md](data-models.md)
Pydantic models for all document types (Legislation, CaseLaw, ExplanatoryNote, Amendment). Defines field types, validation rules, and computed properties.

**When to read**: Understanding data structures, adding new document types, or debugging validation issues.

### [legislation-gov-uk-api.md](legislation-gov-uk-api.md)
Documentation of The National Archives API behavior we discovered through empirical testing.

**Why it exists**: Documents external API we don't control. Captures URL patterns, redirect behavior, XML schema variations, and historical data availability.

### [pdf-dataset.md](pdf-dataset.md)
Analysis of PDF-only legislation dataset (1797-2025). Coverage statistics, era breakdowns, and digitization findings.

**Why it exists**: Empirical data about what PDFs exist and where coverage gaps are. Used for OCR pipeline planning.

### [qdrant-hosting.md](qdrant-hosting.md)
Cost analysis for Qdrant Cloud deployment with production dataset (~4M points).

**Why it exists**: Business case for cloud vs self-hosted, quantization trade-offs, storage calculations.

### [ingestion-process.md](ingestion-process.md)
Overview of data ingestion pipeline architecture: Scraper → Parser → Qdrant.

**When to read**: Understanding how data flows through the system, debugging ingestion issues.

### [dataset-statistics.md](dataset-statistics.md)
Current dataset statistics from production Qdrant instance (actual counts, not estimates).

**Why it exists**: Single source of truth for dataset size, coverage by era, and data quality metrics.

## Auto-Generated Documentation

**Do not duplicate these in markdown**:
- **API Endpoints**: http://localhost:8000/docs (OpenAPI/Swagger UI)
- **Qdrant Schema**: Code in `src/lex/*/qdrant_schema.py` is source of truth
- **Router Logic**: Code in `src/backend/*/router.py` is source of truth

## Contributing to Docs

**Good documentation**:
- Documents external systems (legislation.gov.uk API behavior)
- Captures empirical data (dataset statistics, cost analysis)
- Explains WHY decisions were made (trade-offs, architecture choices)
- Provides domain knowledge context (UK legal system quirks)

**Bad documentation**:
- Duplicates code or auto-generated docs
- Becomes stale immediately (API endpoint lists)
- Dev logs or temporal narratives ("we tried X, then Y...")
- Code dumps with explanatory prose

# Lex Documentation

Documentation for the Lex UK legislative search system.

**Start here**: [system-architecture.md](system-architecture.md) — high-level overview of how all components fit together.

## Core Documentation

### [system-architecture.md](system-architecture.md)
System overview: components, data flow, collections, API surface, and infrastructure. The map that ties everything else together.

**When to read**: First. Before anything else.

### [data-models.md](data-models.md)
Pydantic models for all document types (Legislation, CaseLaw, ExplanatoryNote, Amendment). Defines field types, validation rules, and computed properties.

**When to read**: Understanding data structures, adding new document types, or debugging validation issues.

### [legislation-gov-uk-api.md](legislation-gov-uk-api.md)
Documentation of The National Archives API behaviour we discovered through empirical testing.

**Why it exists**: Documents external API we don't control. Captures URL patterns, redirect behaviour, XML schema variations, and historical data availability.

### [pdf-dataset.md](pdf-dataset.md)
Analysis of PDF-only legislation dataset (1797-2025). Coverage statistics, era breakdowns, and digitisation findings.

**Why it exists**: Empirical data about what PDFs exist and where coverage gaps are. Used for OCR pipeline planning.

### [qdrant-hosting.md](qdrant-hosting.md)
Cost analysis for Qdrant Cloud deployment with production dataset (~4M points).

**Why it exists**: Business case for cloud vs self-hosted, quantisation trade-offs, storage calculations.

### [ingestion-process.md](ingestion-process.md)
Pipeline internals: scraper patterns, parser logic, embedding strategy, and amendments-led mode.

**When to read**: Understanding how documents flow through the pipeline, debugging ingestion issues.

### [dataset-statistics.md](dataset-statistics.md)
Current dataset statistics from production Qdrant instance (actual counts, not estimates).

**Why it exists**: Single source of truth for dataset size, coverage by era, and data quality metrics.

### [handover-plan.md](handover-plan.md)
Prioritised list of handover work items with completion status. Tracks what's been done and what remains.

**When to read**: Understanding what maintenance work has been completed and what's outstanding.

## Auto-Generated Documentation

**Do not duplicate these in markdown**:
- **API Endpoints**: http://localhost:8000/docs (OpenAPI/Swagger UI)
- **Qdrant Schema**: Code in `src/lex/*/qdrant_schema.py` is source of truth
- **Router Logic**: Code in `src/backend/*/router.py` is source of truth

## Contributing to Docs

**Good documentation**:
- Documents external systems (legislation.gov.uk API behaviour)
- Captures empirical data (dataset statistics, cost analysis)
- Explains WHY decisions were made (trade-offs, architecture choices)
- Provides domain knowledge context (UK legal system quirks)

**Bad documentation**:
- Duplicates code or auto-generated docs
- Becomes stale immediately (API endpoint lists)
- Dev logs or temporal narratives ("we tried X, then Y...")
- Code dumps with explanatory prose

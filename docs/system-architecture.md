# System Architecture

Lex is a semantic search API for UK legislation and case law. It ingests documents from government sources, embeds them with hybrid vectors (dense + sparse), stores them in Qdrant, and serves them via a FastAPI REST API and MCP server for AI agents.

---

## Overview

```
┌───────────────────────────────────────────────────────────────┐
│  External Sources                                             │
│  legislation.gov.uk  ·  caselaw.nationalarchives.gov.uk       │
└──────────────┬──────────────────────────┬─────────────────────┘
               │                          │
               ▼                          ▼
┌───────────────────────────────────────────────────────────────┐
│  Ingest Pipeline  (Azure Container Apps Jobs)                 │
│                                                               │
│  Scraper → Parser → Embeddings → Qdrant Upload                │
│                                                               │
│  Daily (amendments-led) · Weekly (5yr) · Monthly (full)       │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  Qdrant Cloud  (UK South)                                     │
│                                                               │
│  8 collections · 8.4M+ documents · INT8 quantisation          │
│  Dense 1024D (Azure OpenAI) + Sparse BM25 (FastEmbed)         │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  Backend API  (Azure Container App)                           │
│                                                               │
│  FastAPI · MCP Server (FastMCP) · Redis rate limiting          │
│  OpenTelemetry → Azure Monitor · PostHog analytics            │
└──────┬───────────┬──────────────┬─────────────────────────────┘
       │           │              │
       ▼           ▼              ▼
    REST API   MCP Clients    Bulk Downloads
```

---

## Components

| Component | Purpose | Key paths |
|-----------|---------|-----------|
| **Backend API** | FastAPI app serving search endpoints and homepage | `src/backend/api/app.py`, `src/backend/*/router.py` |
| **MCP server** | Exposes search tools to AI agents via Model Context Protocol | `src/backend/mcp_server/server.py` (mounted at `/mcp`) |
| **Ingest pipeline** | Scrapes, parses, embeds, and uploads documents to Qdrant | `src/lex/ingest/orchestrator.py`, `src/lex/*/pipeline.py` |
| **Ingest orchestrator** | Coordinates pipeline stages and amendments-led mode | `src/lex/ingest/orchestrator.py`, `src/lex/ingest/amendments_led.py` |
| **Embeddings** | Dense (Azure OpenAI) + sparse (BM25) vector generation | `src/lex/core/embeddings.py` |
| **Qdrant client** | Lazy-initialised client with retry logic for transient errors | `src/lex/core/qdrant_client.py` |
| **Rate limiting** | Per-IP limits via Redis with in-memory fallback | `src/backend/core/middleware.py`, `src/backend/core/cache.py` |
| **Monitoring** | OpenTelemetry traces + custom counters and histograms | `src/backend/core/telemetry.py`, `src/backend/monitoring.py` |
| **Bulk export** | Weekly Parquet export to Azure Blob Storage | `scripts/bulk_export_parquet.py` |
| **Infrastructure** | Bicep template for all Azure resources | `infrastructure/azure/main.bicep` |

---

## Collections

| Collection | Contents | ~Size | Embeds from |
|------------|----------|-------|-------------|
| `caselaw_section` | Paragraph-level sections of judgments | 4.7M | text |
| `legislation_section` | Individual provisions within legislation | 2.1M | text |
| `amendment` | Legislative amendments and modifications | 892K | changed/affecting legislation, effect type |
| `embedding_cache` | Cached embeddings for pipeline performance | 239K | — |
| `legislation` | Acts, SIs, and other instruments (top-level) | 220K | title, description, type, year |
| `explanatory_note` | Explanatory memoranda for legislation | 89K | text |
| `caselaw` | Court judgments and decisions | 70K | text |
| `caselaw_summary` | AI-generated case summaries | 61K | text |

All collections (except `embedding_cache`) use 1024-dimensional dense vectors (Azure OpenAI `text-embedding-3-large`) and sparse BM25 vectors, with INT8 scalar quantisation. Schemas are defined in `src/lex/*/qdrant_schema.py`.

---

## Data lifecycle

Documents begin at government sources. Scrapers iterate through years and document types, fetching XML from legislation.gov.uk or caselaw.nationalarchives.gov.uk. Parsers extract structured fields into Pydantic models — title, text, metadata, cross-references. Each document type follows the same pattern: `Scraper → Parser → Pipeline → Upload`.

Before upload, each document is embedded twice: a 1024-dimensional dense vector from Azure OpenAI captures semantic meaning, while a sparse BM25 vector captures exact term frequencies. An embedding cache (itself a Qdrant collection) avoids redundant API calls for repeated text. Documents are uploaded in batches with UUID5-based idempotency, so re-running a pipeline is safe.

At query time, the backend performs hybrid search — querying both dense and sparse indexes, then fusing results. Legislation uses Distribution-Based Score Fusion (DBSF) which favours semantic matches; case law uses Reciprocal Rank Fusion (RRF) which is rank-based and needs no tuning. Payload indexes on fields like `year`, `type`, and `court` enable efficient filtering. See [search-architecture.md](search-architecture.md) for details.

Three ingest schedules keep data fresh: daily amendments-led (targets only legislation known to have changed), weekly extended lookback (5 years), and monthly full rescan (all historical data). A separate weekly job exports all collections to Parquet files in Azure Blob Storage for bulk download.

---

## API surface

**Legislation**: `POST /legislation/search`, `/legislation/section/search`, `/legislation/lookup`, `/legislation/section/lookup`

**Case law**: `POST /caselaw/search`, `/caselaw/section/search`, `/caselaw/reference/search`, `/caselaw/summary/search`

**Amendments**: `POST /amendment/search`, `/amendment/section/search`

**Explanatory notes**: `POST /explanatory_note/section/search`, `/explanatory_note/legislation/lookup`

**System**: `GET /healthcheck`, `GET /api/stats`

**MCP**: All search endpoints are also exposed as MCP tools at `/mcp` for AI agent integration.

Full OpenAPI spec is auto-generated at `/docs`.

---

## Infrastructure

| Resource | Name | Purpose |
|----------|------|---------|
| Container App | `lex-api` | FastAPI + MCP server (1-10 replicas, auto-scaling) |
| Container App Jobs (x4) | `lex-*-job` | Scheduled ingest and export ([see runbook](operations-runbook.md)) |
| Container Registry | ACR | Docker image storage |
| Redis Cache | `lex-cache` | Rate limiting and search result caching |
| Storage Account | `lexdownloads` | Bulk Parquet export downloads |
| Log Analytics | — | Centralised logging (30-day retention) |
| Application Insights | — | OpenTelemetry trace collection |
| Qdrant Cloud | — | Vector database (external, UK South region) |

Deployment via `infrastructure/azure/deploy.sh`. See [deployment.md](deployment.md) for setup.

---

## Further reading

| Document | When to read |
|----------|-------------|
| [operations-runbook.md](operations-runbook.md) | Running the system day-to-day: health checks, jobs, debugging, emergencies |
| [ingestion-process.md](ingestion-process.md) | How the ingest pipeline works in detail: scrapers, parsers, scheduling |
| [search-architecture.md](search-architecture.md) | Why hybrid search, how fusion works, performance characteristics |
| [deployment.md](deployment.md) | Setting up a new instance: Docker Compose or Azure |
| [data-models.md](data-models.md) | Pydantic model field definitions for all document types |
| [dataset-statistics.md](dataset-statistics.md) | Current production dataset sizes and coverage |
| [troubleshooting.md](troubleshooting.md) | Common issues and fixes for local development |
| [qdrant-hosting.md](qdrant-hosting.md) | Cost analysis: Qdrant Cloud vs self-hosted |
| [legislation-gov-uk-api.md](legislation-gov-uk-api.md) | External API behaviour discovered through testing |
| [uk-legal-system.md](uk-legal-system.md) | Domain context: how UK legislation and case law work |

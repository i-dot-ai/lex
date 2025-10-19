# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lex is a legislative service that processes and indexes UK legal documents (legislation, caselaw, explanatory notes, amendments) for search and retrieval via FastAPI and MCP server.

## Current System Status (October 2025)

### Database Architecture
- **Vector Database**: Qdrant (port 6333) - Primary search database
- **Ingestion Pipeline**: Elasticsearch (port 9200) - Used for data ingestion only
- **Migration Status**: Elasticsearch → Qdrant migration **COMPLETE** (3.5M documents)

### Qdrant Collections (Production Ready)
- `legislation`: 125,102 Acts with hybrid vectors (dense + sparse)
- `legislation_section`: 904,512 sections with hybrid vectors
- `caselaw`: 30,512 cases with hybrid vectors
- `caselaw_section`: 2,403,490 case sections with hybrid vectors
- `explanatory_note`: 82,344 notes with hybrid vectors
- `amendment`: Amendment records (metadata only)

### API Status
- Backend API: **RUNNING** on port 8000
- API Docs: http://localhost:8000/docs
- Search: Qdrant hybrid search (RRF fusion of dense + sparse vectors)
- All endpoints operational and tested

## Development Commands

```bash
# Environment setup
make install              # Install dependencies with uv
make docker-up           # Start Qdrant, Elasticsearch, and other services
make docker-down         # Stop all services

# Data ingestion - Sample (limited data for testing)
make ingest-all-sample              # Ingest sample data for all document types
make ingest-legislation-sample      # Ingest sample legislation only (ukpga, 2020-current year, limit 50)
make ingest-caselaw-sample          # Ingest sample caselaw only (limit 50)

# Data ingestion - Full (complete data)
make ingest-all-full                # Ingest ALL data for all document types
make ingest-legislation-full        # Ingest ALL legislation (all types, 1963-current year)
make ingest-caselaw-full            # Ingest ALL caselaw (2001-current year)

# Data ingestion - Historical (pre-1963)
make ingest-legislation-historical       # Ingest historical legislation (1267-1962)
make ingest-legislation-section-historical  # Ingest historical sections
make ingest-legislation-complete         # Ingest complete dataset (1267-current year)

# Development
make run                 # Run API locally (uv run src/backend/main.py)
make test               # Run tests (uv run pytest)

# API documentation available at http://localhost:8000/docs
```

## Documentation

### Technical References
- **`docs/LEGISLATION_GOV_UK_DOCS.md`** - Complete documentation of The National Archives API, XML structure, URL patterns, data availability, and historical coverage (1267-present)
- **`app/AI_SDK_V5_GUIDE.md`** - AI SDK v5 + GPT-5 implementation guide for Deep Research feature

## Architecture

The codebase follows a consistent pattern across document types:

### Core Pipeline (`src/lex/`)
Each document type (legislation, caselaw, explanatory_note, amendment) has:
- `scraper.py` - Downloads from The National Archives
- `parser.py` - Transforms XML/HTML to Pydantic models
- `models.py` - Pydantic data models
- `pipeline.py` - Orchestrates scraping → parsing → Elasticsearch upload
- `mappings.py` - Elasticsearch index configuration (for ingestion)
- `qdrant_schema.py` - Qdrant collection schema (hybrid vectors)

### Backend API (`src/backend/`)
Each document type has:
- `router.py` - FastAPI POST endpoints
- `models.py` - Request/response schemas
- `search.py` - Qdrant hybrid search logic (RRF fusion)

### Core Utilities (`src/lex/core/`)
- `embeddings.py` - Parallel embedding generation (Azure OpenAI + FastEmbed BM25)
- `qdrant_client.py` - Qdrant client singleton
- `clients.py` - Elasticsearch client (for ingestion pipeline)

## Key Design Patterns

1. **All API endpoints are POST** - Supports complex query structures in request bodies
2. **Single CLI entry point** - `src/lex/main.py` handles all data processing with model-specific flags
3. **Hybrid search** - Qdrant RRF fusion combining:
   - Dense vectors (1024D from Azure OpenAI text-embedding-3-large)
   - Sparse vectors (BM25 from FastEmbed)
4. **HTTP caching** - Scrapers cache responses to minimize external API load
5. **Batch processing** - Documents processed in configurable batches for memory efficiency
6. **Parallel embedding generation** - 50 concurrent workers for Azure OpenAI API calls

## Important Notes

### Search Architecture
- **Elasticsearch**: Used ONLY for data ingestion pipeline (stores raw text with semantic_text)
- **Qdrant**: Used for ALL search queries (hybrid vector search with RRF fusion)
- **Migration**: Data flows: Scraper → ES → Qdrant migration → API searches Qdrant

### Default Limit Behavior
- By default, the pipeline processes ALL available documents (no limit)
- Use the `--limit` flag to restrict the number of documents processed
- Sample commands use explicit limits (e.g., 50) for quick testing
- Full commands process everything available for the specified years

### Year Ranges & Data Availability

**Modern Legislation (Complete Coverage):**
- **Years**: 1963-present (calendar year numbering)
- **Coverage**: 100% of all enacted legislation
- **URL Pattern**: `/ukpga/2020/12` (year/number format)

**Historical Legislation (Partial Coverage):**
- **Years**: 1267-1962 (regnal year numbering pre-1963)
- **Coverage**: ~85K significant Acts digitized in XML
- **URL Pattern**: `/ukpga/Geo3/41/90` (monarch/regnal-year/number format)
- **Discovery Method**: Atom feeds at `/primary+secondary/{year}/data.feed`
- **Note**: Pre-1800 acts are sparse (constitutional/major statutes only)

**Caselaw:**
- **Years**: 2001-present
- **Coverage**: TNA data availability starts 2001
- **Note**: UKSC (UK Supreme Court) only exists from 2009 onwards

**Historical Data Distribution:**
```
Period          Years       Documents  Coverage
Medieval        1267-1600   ~500       Major statutes only
Stuart Era      1600-1700   ~800       Constitutional acts
Georgian        1700-1800   ~10K       Significant acts
Victorian       1800-1900   ~25K       Good coverage
Modern Pre-1963 1900-1962   ~50K       Very good coverage
Complete        1963-Pres   ~150K      100% complete
```

See `docs/LEGISLATION_GOV_UK_DOCS.md` for comprehensive details on URL patterns, regnal years, and data availability.

## Common Development Tasks

### Adding a new document type
1. Create module in `src/lex/new_type/` with scraper, parser, models, pipeline, mappings, qdrant_schema
2. Add corresponding module in `src/backend/new_type/` with router, models, search
3. Register router in `src/backend/main.py`
4. Add CLI option in `src/lex/main.py`
5. Add collection to `scripts/init_qdrant_collections.py`

### Testing specific functionality
```bash
# Run specific test file
uv run pytest tests/lex/test_legislation.py

# Run with coverage
uv run pytest --cov=src

# Test API endpoints manually
curl -X POST http://localhost:8000/legislation/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

### Working with Qdrant
- Direct access: http://localhost:6333
- Qdrant dashboard: http://localhost:6333/dashboard
- Collections follow pattern: `{document_type}` (e.g., `legislation`, `legislation_section`)
- Each collection has named vectors: `dense` (1024D) and `sparse` (BM25)

### Working with Elasticsearch (Ingestion Only)
- Direct access: http://localhost:9200
- Kibana UI: http://localhost:5601
- Indices follow pattern: `lex-dev-{document_type}` (e.g., `lex-dev-legislation`)
- **Note**: Elasticsearch is used ONLY for ingestion, not for search queries

### GPT-5 Model Family (Deep Research)
- **Models**: gpt-5, gpt-5-mini, gpt-5-nano (we use gpt-5-mini for cost/performance)
- **API Differences**: GPT-5 does NOT support `temperature`, `top_p`, or `logprobs`
- **Instead use**:
  - `reasoning: { effort: "minimal" | "low" | "medium" | "high" }` - Controls reasoning depth
  - `text: { verbosity: "low" | "medium" | "high" }` - Controls output length
- **Responses API**: Preferred over Chat Completions (supports reasoning passthrough between turns)
- **Docs**: https://platform.openai.com/docs/guides/latest-model

### AI SDK v5 + GPT-5 Implementation Guide
**Complete reference**: See `app/AI_SDK_V5_GUIDE.md` for comprehensive documentation on:
- GPT-5 reasoning traces configuration
- Multi-step agents with `stopWhen`
- Tool definition best practices
- Production-ready patterns
- Troubleshooting common issues

**Quick reference**:
- Use `azure.responses('gpt-5-mini')` for reasoning support
- Configure reasoning in `providerOptions.openai` with underscores (not camelCase)
- Enable `sendReasoning: true` in `toUIMessageStreamResponse()`
- Use `stopWhen: stepCountIs(N)` instead of deprecated `maxSteps`

## Legislation Type Codes

The system supports 28 different legislation types (defined in `src/lex/legislation/models.py`):

### Primary Legislation
- **ukpga** - UK Public General Acts
- **asp** - Acts of the Scottish Parliament
- **asc** - Acts of Senedd Cymru
- **anaw** - Acts of the National Assembly for Wales
- **ukcm** - Church Measures
- **nia** - Acts of the Northern Ireland Assembly
- **ukla** - UK Local Acts
- **ukppa** - UK Private and Personal Acts
- **apni** - Acts of the Northern Ireland Parliament
- **gbla** - Local Acts of the Parliament of Great Britain
- **aosp** - Acts of the Old Scottish Parliament
- **aep** - Acts of the English Parliament
- **apgb** - Acts of the Parliament of Great Britain
- **mwa** - Measures of the Welsh Assembly
- **aip** - Acts of the Old Irish Parliament
- **mnia** - Measures of the Northern Ireland Assembly

### Secondary Legislation
- **uksi** - UK Statutory Instruments
- **wsi** - Wales Statutory Instruments
- **ssi** - Scottish Statutory Instruments
- **nisr** - Northern Ireland Statutory Rules
- **nisro** - Northern Ireland Statutory Rules and Orders
- **nisi** - Northern Ireland Orders in Council
- **uksro** - UK Statutory Rules and Orders
- **ukmo** - UK Ministerial Orders
- **ukci** - Church Instruments

### European Legislation
- **eudn** - Decisions originating from the EU
- **eudr** - Directives originating from the EU
- **eur** - Regulations originating from the EU

## Migration Notes (Elasticsearch → Qdrant)

### Migration Scripts
- `scripts/init_qdrant_collections.py` - Initialize all Qdrant collections with schemas
- `scripts/migrate_es_to_qdrant.py` - Migrate data from Elasticsearch to Qdrant
  - Extracts existing embeddings from ES semantic_text fields
  - Generates new embeddings for legislation collection (title + type + description)
  - Uses parallel processing (50 workers) for Azure OpenAI API calls
  - Supports checkpointing and resume functionality

### Performance Metrics
- Sequential baseline: 2.24 docs/s
- Parallel processing: 30-86 docs/s (average ~50 docs/s)
- Speedup: 13-38x faster
- Time savings: 15 hours → ~1.5 hours for full migration

## Lessons Learned

### Common Issues & Solutions
- **Default limits**: The pipeline had a default 10K document limit that stopped processing early. Always check for hidden limits in data processing code.
- **Logging limitations**: The ElasticsearchLogHandler only indexed `props` attribute, not standard Python `extra` fields. When debugging logging, check the handler implementation.
- **PDF fallbacks**: Some pre-1800 UK legislation only exists as PDFs, not XML. Check for PDF URLs if XML returns 404.
- **Year patterns**: Modern legislation uses calendar years (1963+), historical uses regnal years (pre-1963). Different document types have different historical availability.
- **Historical URL patterns**: Pre-1963 Acts use regnal year format (`/ukpga/Geo3/41/90`) instead of calendar year format. Use Atom feeds (`/primary+secondary/{year}/data.feed`) for discovery.
- **Environment loading with nohup**: When running scripts with `nohup` or in background processes, use explicit path: `load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)`
- **Rate limiting**: Azure OpenAI has 7200 RPM limit. Use parallel processing (50 workers ≈ 83 req/s) with exponential backoff retry logic for 429 errors.
- **Embedding extraction**: Extract existing embeddings from ES semantic_text fields instead of regenerating to save API calls and time.
- **SQLite cache concurrency**: Use `FanoutCache` instead of `Cache` for better write concurrency. Single SQLite files cause "database disk image is malformed" errors under concurrent load. FanoutCache shards across 8 files with 60s lock timeout.
- **File append modes**: Use 'a' not 'w' mode for resume capability in long-running processes. Opening in 'w' mode truncates existing results.
- **HTTP retry settings**: legislation.gov.uk needs aggressive retry settings: 30 attempts, 600s max delay, 30s timeout. Default 15 attempts/180s delay causes frequent failures.

### Qdrant/Elasticsearch Migrations - CRITICAL LESSONS

**NEVER TRUST CHECKPOINT FILES OR LOGS - ALWAYS VERIFY ACTUAL COUNTS:**
- Checkpoint files can become stale or incorrect after failed runs
- Progress bars show docs *processed*, not docs *added* (due to idempotency)
- **ALWAYS** check actual Qdrant count via API: `curl http://localhost:6333/collections/{name} | jq .result.points_count`
- **ALWAYS** compare to ES count: `curl http://localhost:9200/{index}/_count`

**UUID5 IDEMPOTENCY IS RELIABLE - TRUST IT:**
- Using `uuid.uuid5(NAMESPACE, doc_id)` provides perfect idempotency
- Qdrant's `upsert()` safely ignores duplicate UUIDs - existing points are not duplicated
- Migration can be safely re-run multiple times - duplicates will be skipped
- Don't panic if progress bar shows "processing 100K docs" but count only increases by 899
- This is EXPECTED behavior - most docs already exist and are correctly skipped

**ELASTICSEARCH SCROLL ORDER IS ARBITRARY:**
- ES scroll API returns documents in random order
- Missing documents can be scattered anywhere in the dataset
- **MUST** process ALL documents in ES to ensure you find the missing ones
- Cannot rely on "first N documents" to fill gaps
- If Qdrant has 903,613 and ES has 904,512, you must scroll through ALL 904,512 to find the 899 missing

**BATCH SIZE AND TIMEOUTS FOR LARGE DOCUMENTS:**
- Standard batch size: 25 works for most collections
- **Caselaw exception**: Requires batch size 10 (documents can be 260K chars + embeddings)
- Qdrant timeout: 360s required (increased from 45s → 120s → 360s)
- Large documents (>100K chars) can timeout even with retries at lower timeouts
- Retry detection must catch `ResponseHandlingException`, not just timeout strings
- Balance: smaller batches = more HTTP overhead, larger batches = timeout risk

**QDRANT QUERY API - CORRECT USAGE:**
- Use `FusionQuery(fusion=Fusion.RRF)` for fusion queries, NOT `Query(fusion=...)`
- `prefetch` is a direct parameter of `query_points()`, NOT nested inside query object
- Incorrect: `query=Query(fusion=..., prefetch=[...])`
- Correct: `query=FusionQuery(fusion=...), prefetch=[...]`
- `Query` is a type alias (typing.Union), not an instantiable class - will fail with TypeError

**CHECKPOINT COMPLEXITY IS NOT WORTH IT:**
- Checkpoints add complexity and failure modes
- Better approach: rely on UUID idempotency and just re-process everything
- Qdrant's upsert is fast enough that duplicates don't slow things down significantly
- Simpler code = fewer bugs

**EMBEDDING EXTRACTION vs GENERATION:**
- For collections with ES semantic_text fields: EXTRACT embeddings (don't regenerate)
- Check ES mapping: if `type: semantic_text` exists, embeddings are at `doc["text"]["inference"]["chunks"][0]["embeddings"]`
- For legislation collection: ES has NO embeddings (just metadata), MUST generate from title+description
- Regenerating embeddings unnecessarily costs money and time (1.5 hours for 125K docs)

**MIGRATION VERIFICATION CHECKLIST:**
1. Check ES source count: `curl localhost:9200/{index}/_count`
2. Check Qdrant target count: `curl localhost:6333/collections/{name} | jq .result.points_count`
3. If counts don't match, DON'T assume idempotency is broken - run full migration
4. Monitor actual Qdrant count during migration, not progress bar output
5. Let migration complete fully - partial runs won't find all missing docs

**COMMON MISTAKES TO AVOID:**
- ❌ Assuming progress bar "docs processed" = "docs added"
- ❌ Panicking when Qdrant count doesn't increase proportionally to docs processed
- ❌ Stopping migration early thinking "it's adding duplicates"
- ❌ Trusting checkpoint files without verifying actual counts
- ❌ Regenerating embeddings that already exist in ES
- ❌ Using large batch sizes (>50) with hybrid vectors

### Code Patterns
- **Consistent error handling**: Use structured logging with `extra` fields for better observability
- **Document type abstraction**: Each type (legislation, caselaw, etc.) follows the same scraper→parser→pipeline pattern
- **Batch processing**: Essential for memory management with large document sets
- **Parallel embeddings**: Use ThreadPoolExecutor with 50 workers for Azure OpenAI API calls
- **Hybrid search**: Combine dense (semantic) and sparse (BM25) vectors with RRF fusion for best results

## Environment Variables

Key variables (see docker-compose.yaml for full list):
- `AZURE_OPENAI_API_KEY` - Required for embeddings
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` - Deployment name (text-embedding-3-large)
- `QDRANT_URL` - Qdrant connection URL (default: http://localhost:6333)
- `PIPELINE_BATCH_SIZE` - Documents per batch (default: 100)
- `HTTP_CACHE_EXPIRY` - Cache duration in days (default: 14)

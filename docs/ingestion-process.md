# Ingestion Process

Pipeline internals for scraping, parsing, embedding, and uploading UK legal documents. For the high-level system overview, see [system-architecture.md](system-architecture.md). For scheduling and operational procedures, see [operations-runbook.md](operations-runbook.md).

---

## Pipeline Architecture

Every document type follows the same four-stage pattern:

```
Scraper (fetch URLs) → Parser (extract data) → Embeddings (dense + sparse) → Upload (Qdrant)
```

The system processes five document types: legislation, legislation sections, case law, explanatory notes, and amendments. Each has its own scraper, parser, and pipeline module under `src/lex/{type}/`.

---

## Scrapers (`src/lex/{type}/scraper.py`)

Scrapers generate document URLs by iterating through years and legislation types, then download XML content from legislation.gov.uk or caselaw.nationalarchives.gov.uk.

- **Pagination**: Atom feeds return 20 entries per page; scrapers follow `<leg:morePages>` until exhausted
- **Checkpointing**: Progress is saved periodically so interrupted runs can resume
- **Rate limiting**: Exponential backoff with circuit breaker prevents hammering external APIs
- **Error recovery**: HTTP 5xx errors are logged and skipped; the pipeline continues with remaining documents

URL patterns follow legislation.gov.uk conventions — see [legislation-gov-uk-api.md](legislation-gov-uk-api.md) for details.

## Parsers (`src/lex/{type}/parser.py`)

Parsers transform XML/HTML into Pydantic models (defined in [data-models.md](data-models.md)).

- **XML schemas**: Crown Legislation Markup Language (CLML) for legislation, XHTML for case law
- **Section extraction**: Walks the hierarchical XML structure (Body → Part → P1group → P1 → P1para) to extract individual provisions
- **PDF fallback**: Pre-1987 documents often lack XML body text. The parser detects empty bodies, logs `processing_status: "pdf_fallback"`, and continues without crashing
- **URI normalisation**: All URIs are normalised to canonical format (`http://www.legislation.gov.uk/id/{type}/{year}/{number}`) at parse time

## Embeddings (`src/lex/core/embeddings.py`)

Each document gets two vectors:

- **Dense** (1024D): Azure OpenAI `text-embedding-3-large` — captures semantic meaning
- **Sparse** (BM25): FastEmbed — captures exact term frequencies for citation matching

An embedding cache (`src/lex/core/embedding_cache.py`) stores results in a dedicated Qdrant collection. Lookups use UUID5(SHA-256(text)) for O(1) retrieval, giving a 35x speedup on repeated text.

For why hybrid vectors and how fusion works, see [search-architecture.md](search-architecture.md).

## Upload (`src/lex/{type}/pipeline.py`)

Documents are uploaded to Qdrant in configurable batches (default: 25, 10 for case law).

- **Idempotency**: Point IDs are UUID5-derived from document identifiers, so re-running a pipeline is safe
- **Batch upsert**: Chunks uploads to stay within Qdrant's 32MB payload limit
- **Memory efficiency**: Documents flow through as generators, not lists — typical usage is 500MB-1GB

---

## Amendments-Led Mode

The daily ingest uses amendments as a "change manifest" rather than blindly rescraping by year. This is the most important mode to understand.

**How it works** (`src/lex/ingest/amendments_led.py`):

1. Query the amendments collection for `affecting_year` in the target range
2. Extract unique `changed_legislation` IDs from those amendments
3. Check which IDs are missing or stale in Qdrant
4. Rescrape only those specific legislation items
5. Also ingest new case law and amendments for the year range

The weekly job extends the lookback to 5 years (`--years-back 5`). The monthly job bypasses this entirely and runs a full historical rescan.

---

## Performance

| Metric | Typical value |
|--------|--------------|
| Legislation throughput | 5-10 docs/second |
| Case law throughput | 2-5 docs/second |
| Section throughput | 20-50 sections/second |
| Pipeline memory | 500MB-1GB |
| HTTP cache TTL | 14 days |

Network requests use connection pooling via requests sessions. Processing is single-threaded (API-friendly).

---

## Code References

| Component | Path |
|-----------|------|
| Orchestrator | `src/lex/ingest/orchestrator.py` |
| Amendments-led mode | `src/lex/ingest/amendments_led.py` |
| Embeddings | `src/lex/core/embeddings.py` |
| Embedding cache | `src/lex/core/embedding_cache.py` |
| Legislation pipeline | `src/lex/legislation/pipeline.py` |
| Case law pipeline | `src/lex/caselaw/pipeline.py` |
| Models | `src/lex/{type}/models.py` — see [data-models.md](data-models.md) |

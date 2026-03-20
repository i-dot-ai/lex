# Operations Runbook

Day-to-day operational reference for running Lex in production. For initial setup and deployment, see [deployment.md](deployment.md). For local development issues, see [troubleshooting.md](troubleshooting.md).

---

## Key URLs

| Resource | URL |
|----------|-----|
| API | `https://lex.lab.i.ai.gov.uk` |
| MCP endpoint | `https://lex.lab.i.ai.gov.uk/mcp` |
| Health check | `https://lex.lab.i.ai.gov.uk/healthcheck` |
| API docs (OpenAPI) | `https://lex.lab.i.ai.gov.uk/docs` |
| Downloads manifest | `https://lexdownloads.blob.core.windows.net/downloads/latest/manifest.json` |
| Azure resource group | `rg-lex` |

All secrets are stored as Azure Container Apps secret refs. Local dev credentials live in `.env` (not committed).

---

## Daily health checks

### 1. API health

```bash
curl -s https://lex.lab.i.ai.gov.uk/healthcheck | jq
```

Expected response (200 OK):

```json
{
  "status": "healthy",
  "database": "qdrant",
  "collections": 8,
  "collection_details": {
    "caselaw_section": { "points": 4723735, "status": "green" },
    "legislation_section": { "points": 2098225, "status": "green" },
    "amendment": { "points": 892210, "status": "green" },
    "embedding_cache": { "points": 238600, "status": "green" },
    "legislation": { "points": 219685, "status": "green" },
    "explanatory_note": { "points": 88956, "status": "green" },
    "caselaw": { "points": 69970, "status": "green" },
    "caselaw_summary": { "points": 61107, "status": "green" }
  }
}
```

If status is `unhealthy` (503), check Qdrant Cloud connectivity.

### 2. Container App logs

```bash
az containerapp logs show --name lex-api --resource-group rg-lex --follow
```

### 3. App Insights

Check for error spikes in Application Insights via the Azure portal (linked from `rg-lex` resource group).

### 4. Export manifest freshness

```bash
curl -s https://lexdownloads.blob.core.windows.net/downloads/latest/manifest.json | jq '.generated_at, .collections | to_entries[] | {name: .key, records: .value.total_records}'
```

Manifest should be <10 days old with non-zero record counts for all 4 exported collections.

---

## Scheduled jobs

All jobs run as Azure Container Apps Jobs in `rg-lex`. Resource prefix is `lex-prod`.

| Job name | Schedule | Command | Timeout | Retries | Purpose |
|----------|----------|---------|---------|---------|---------|
| `lex-prod-ingest-job` | Daily 02:00 UTC | `lex.ingest --mode amendments-led` | 8 hours | 1 | Ingest recent amendments and linked legislation |
| `lex-prod-weekly-ingest-job` | Saturday 02:00 UTC | `lex.ingest --mode amendments-led --years-back 5` | 24 hours | 1 | Extended ingest with 5-year lookback |
| `lex-prod-monthly-ingest-job` | 1st of month 01:00 UTC | `lex.ingest --mode full` | 7 days | 1 | Full historical re-ingest |
| `lex-prod-export-job` | Sunday 03:00 UTC | `bulk_export_parquet.py` | 6 hours | 2 | Parquet export to blob storage |

All jobs use 2.0 CPU / 4Gi memory.

### Check job status

```bash
# List recent executions
az containerapp job execution list \
  --name lex-prod-export-job \
  --resource-group rg-lex \
  -o table

# View logs for a specific execution
az containerapp job logs show \
  --name lex-prod-export-job \
  --resource-group rg-lex \
  --execution <execution-name>
```

### Manually trigger a job

```bash
az containerapp job start \
  --name lex-prod-export-job \
  --resource-group rg-lex
```

### Job failure behaviour

- **Export job**: exits non-zero on total failure, Azure retries up to 2 times. Manifest is only updated when at least one collection exports successfully. Single-collection runs (`--collection`) skip manifest update.
- **Ingest jobs**: exit non-zero on failure, Azure retries once. See [ingestion-process.md](ingestion-process.md) for pipeline details.

---

## Monitoring the export

The weekly export writes Snappy-compressed Parquet files to Azure Blob Storage.

### Blob storage structure

```
downloads/
  latest/
    manifest.json
    legislation_YYYY.parquet
    legislation_section_YYYY.parquet
    amendment_YYYY.parquet
    explanatory_note_YYYY.parquet
  archive/
    2026-03-16/
      ...same files...
```

### Verifying a successful export

1. Check manifest record counts are non-zero for all collections
2. Check `generated_at` timestamp is from the most recent Sunday
3. If manifest shows zeros or is stale, check export job logs and re-trigger

### Export safeguards

- Manifest is **not updated** if all collections fail (prevents overwriting good data with zeros)
- Manifest is **not updated** for single-collection runs (`--collection` flag)
- Old archives are **not cleaned up** unless current export succeeded
- All Qdrant scroll and blob upload operations have exponential backoff retry

---

## Data migrations

### URI normalisation

The codebase has inconsistent URI formats across collections (https vs http, missing `/id/` segment). The `maintenance/fix_uri_formats.py` script normalises these to canonical format: `http://www.legislation.gov.uk/id/{type}/{year}/{number}`.

**Current status** (as of 2026-03-20): amendments ~70% done; legislation and legislation_section not started.

```bash
# Dry run — report non-canonical URIs per collection
USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py

# Apply fixes to a specific collection
USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py --apply --collection amendments

# Apply all
USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py --apply
```

**After migration is complete**: remove the `MatchAny` dual http/https fallback in `src/backend/amendment/search.py` (lines 25, 57). This is tech debt from the incomplete migration.

### Payload indexes

Run after schema changes or adding new collections:

```bash
uv run python scripts/create_payload_indexes.py
```

Creates 29 payload indexes across all 7 collections for query filter performance.

---

## Scripts reference

Scripts are organised into `scripts/` (actively used), `scripts/maintenance/` (one-off repairs), and `scripts/pdf/` (PDF digitisation pipeline). Run with `uv run python scripts/<path>`.

All destructive scripts default to **dry-run** mode. Pass `--apply` to make changes.

### Scheduled / operational

| Script | Purpose | When to run | Env needed | Key flags |
|--------|---------|-------------|------------|-----------|
| `bulk_export_parquet.py` | Export collections to Parquet in blob storage | Scheduled: Sundays 03:00 UTC | `AZURE_STORAGE_CONNECTION_STRING`, Qdrant creds | `--apply`, `--collection`, `--no-cleanup` |
| `create_payload_indexes.py` | Create Qdrant payload indexes (29 total) | After schema changes or new collections | `.env` with Qdrant creds | — |
| `regenerate_all_summaries.py` | Regenerate caselaw AI summaries from scratch | When summary generation logic changes | Qdrant + Azure OpenAI creds | `--apply`, `--limit`, `--workers`, `--batch-size`, `--no-reset` |

> **Warning**: `regenerate_all_summaries.py --apply` wipes the `caselaw_summary` collection before rebuilding unless `--no-reset` is passed.

**Example invocations:**

```bash
# Preview export without uploading
uv run python scripts/bulk_export_parquet.py

# Actually export to blob storage
uv run python scripts/bulk_export_parquet.py --apply

# Export single collection
uv run python scripts/bulk_export_parquet.py --apply --collection legislation

# Apply payload indexes after schema change
uv run python scripts/create_payload_indexes.py

# Test summary regeneration on 100 cases
USE_CLOUD_QDRANT=true uv run python scripts/regenerate_all_summaries.py --limit 100

# Full summary rebuild
USE_CLOUD_QDRANT=true uv run python scripts/regenerate_all_summaries.py --apply
```

### Debugging / analysis

| Script | Purpose | When to run | Env needed | Key flags |
|--------|---------|-------------|------------|-----------|
| `bulk_search_qdrant.py` | Hybrid semantic search with CSV/Excel/JSON export | On-demand research and validation | Azure OpenAI + Qdrant creds | `--query`, `--collection`, `--limit`, `--year-from`, `--year-to`, `--types`, `--formats` |
| `profile_search_endpoints.py` | Benchmark search endpoint response times | After search changes, performance regression testing | Local API running on :8000 | — |

**Example invocations:**

```bash
# Search legislation sections
uv run python scripts/bulk_search_qdrant.py --query "environmental reporting" --limit 50 --year-from 2010

# Benchmark all search endpoints
uv run python scripts/profile_search_endpoints.py
```

### Maintenance (one-off repairs)

| Script | Purpose | When to run | Env needed | Key flags |
|--------|---------|-------------|------------|-----------|
| `maintenance/fix_uri_formats.py` | Normalise URIs to canonical `http://www.legislation.gov.uk/id/...` | When URI inconsistencies detected | `USE_CLOUD_QDRANT=true`, Qdrant creds | `--apply`, `--collection`, `--batch-size` |
| `maintenance/fix_nested_text_schema.py` | Unwrap nested text fields from Elasticsearch migration | After Elasticsearch data import | `USE_CLOUD_QDRANT=true`, Qdrant creds | `--apply`, `--collection`, `--batch-size` |
| `maintenance/enable_quantization.py` | Enable INT8 scalar quantisation (75% memory saving) | After major collection ingestion | Qdrant creds | — |

**Example invocations:**

```bash
# Preview URI fixes
USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py

# Apply URI fixes to amendments
USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py --apply --collection amendments

# Enable quantisation on all collections (background, 10-30 min)
USE_CLOUD_QDRANT=true uv run python scripts/maintenance/enable_quantization.py
```

### PDF digitisation pipeline

| Script | Purpose | When to run | Env needed | Key flags |
|--------|---------|-------------|------------|-----------|
| `pdf/discover_pdf_legislation.py` | Discover PDF-only historical legislation from Atom feeds | Initial discovery of documents needing OCR | Network access only | `--start-year`, `--end-year`, `--output` |
| `pdf/process_pdfs.py` | OCR process historical PDFs via Azure OpenAI vision | Batch processing discovered PDFs | Azure OpenAI creds | `--csv`, `--url`, `--type`, `--id`, `--max-concurrent` |
| `pdf/check_pdf_progress.py` | Analyse PDF batch processing results and costs | After or during PDF batch processing | None | positional: JSONL results path |

**Example invocations:**

```bash
# Discover historical PDFs (1267-1962)
uv run python scripts/pdf/discover_pdf_legislation.py

# Process PDFs from CSV
uv run python scripts/pdf/process_pdfs.py --csv data/pdf_only_legislation.csv --max-concurrent 5

# Check batch progress
uv run python scripts/pdf/check_pdf_progress.py data/results.jsonl
```

---

## Debugging production issues

### API returning no results

1. Check `/healthcheck` — are collections populated?
2. Check Qdrant Cloud dashboard for cluster health
3. Verify payload indexes exist (run `create_payload_indexes.py` if missing)

### Slow queries

1. Check Qdrant Cloud dashboard for CPU/memory pressure
2. Verify payload indexes are created (they enable filtered queries)
3. Check `caselaw/search.py` scroll calls — `with_payload=True` fetches full payloads (known performance concern)

### Job failures

1. Check exit code — non-zero means failure
2. View execution logs: `az containerapp job logs show ...`
3. Common cause: Qdrant Cloud timeouts on large scroll operations
4. Retry logic handles transient errors automatically; persistent failures indicate cluster issues

### Rate limiting

- Redis-backed: 60 requests/min, 1000 requests/hr per client IP
- Client IP extracted from the **rightmost** `X-Forwarded-For` entry (appended by Azure Container Apps; leftmost is client-controlled)
- Headers: `X-RateLimit-Remaining-Minute`, `X-RateLimit-Remaining-Hour`
- Monitoring events fire at 80% threshold
- Falls back to in-memory tracking if Redis is down
- Redis has public network access enabled (Container Apps connects over public internet; disabling requires VNet/Private Endpoint)
- `/healthcheck` and `/health` endpoints are exempt
- Configurable via `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_PER_HOUR` env vars

### Qdrant timeouts

- `query_points` and `scroll` have automatic retry with exponential backoff (3 attempts, 1s/2s/4s)
- Retries on: "timed out", "timeout", "connection", "disconnected"
- Built into the client at `src/lex/core/qdrant_client.py` — covers all backend search endpoints
- If persistent: check Qdrant Cloud cluster health and resource utilisation

---

## Scaling

| Component | Current config | How to scale |
|-----------|---------------|--------------|
| Container App | 1-10 replicas, scales at 50 concurrent requests | Increase `maxReplicas` in `infrastructure/azure/main.bicep` |
| Qdrant Cloud | Managed (UK South) | Contact Qdrant support |
| Redis Cache | Azure Cache for Redis | Scale via Azure portal |
| Rate limits | 60/min, 1000/hr | Change via env vars or Bicep parameters |

---

## Emergency procedures

### API is down

```bash
# Check Container App status
az containerapp show --name lex-api --resource-group rg-lex -o table

# List revisions
az containerapp revision list --name lex-api --resource-group rg-lex -o table

# Restart active revision
az containerapp revision restart \
  --name lex-api \
  --resource-group rg-lex \
  --revision <revision-name>
```

### Qdrant Cloud unreachable

1. Check [Qdrant Cloud status page](https://status.qdrant.io)
2. Verify `USE_CLOUD_QDRANT=true` and credentials are set in Container App secrets
3. Check Container App can reach Qdrant (network/firewall)

### Bad data in production

Qdrant Cloud manages automatic snapshots. Contact Qdrant support for point-in-time recovery.

### Export manifest corrupted

Previous successful exports are preserved in `archive/{date}/`. To recover:

1. Re-trigger the export job: `az containerapp job start --name lex-prod-export-job --resource-group rg-lex`
2. The script will regenerate `latest/manifest.json` from fresh data
3. Old archives remain untouched (cleanup only runs on successful exports)

### Env vars wiped after job update

Using `az containerapp job update --yaml` can silently wipe environment variables if they're not included in the YAML. Always verify env vars after any job config change:

```bash
az containerapp job show \
  --name lex-prod-export-job \
  --resource-group rg-lex \
  -o yaml | grep -A 50 "env:"
```

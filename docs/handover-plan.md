# Handover Plan

Prioritised list of work to make Lex robust and maintainable for the team after handover. Each item will get its own implementation plan.

## Done

### ~~1. Operations runbook~~ — DONE
See [`docs/operations-runbook.md`](operations-runbook.md). Covers daily health checks, job monitoring, data migrations, debugging, scaling, emergency procedures, and scripts reference.

### ~~2. Complete URI migration~~ — PARTIALLY DONE
Parser now normalises URIs at ingest time (`src/lex/amendment/parser.py`). Dual http/https `MatchAny` fallback removed from `src/backend/amendment/search.py`. Still need to run `fix_uri_formats.py --apply` on remaining collections to fix historical data.

**Dry run results (2026-03-20):**
| Collection | Total records | Affected | Fields |
|---|---|---|---|
| amendment | 892,210 | 616,210 | `changed_url`, `affecting_url` |
| legislation | 219,685 | 219,684 | `id` (94K), `uri` (all) |
| legislation_section | 2,098,225 | 2,098,225 | `id`, `uri`, `legislation_id` (all) |
| explanatory_note | 88,956 | 0 | Already clean |
| **Total** | | **2,934,119** | |

### ~~3. Export job failure alerting~~ — DONE
Azure Monitor alert rule and manifest staleness check added. See commit `b3d3058`.

### ~~4. Environment variable reference~~ — DONE
`.env.example` expanded into full reference with descriptions, defaults, and secret flags. See commit `8498651`.

### ~~5. CI: add test execution~~ — DONE
Pytest added to GitHub Actions workflow. 29 unit tests run on every PR. Integration tests marked and skipped in CI. Lazy Qdrant client init fixes import chain. Ruff pinned to 0.14.5 with `RUFF_OUTPUT_FORMAT` override to avoid action compatibility issue. See commits `5833da2`, `862c043`.

### ~~8. Resolve Dependabot alerts~~ — DONE
`uv lock --upgrade` resolved 29 of 30 Python alerts (including 1 critical authlib, 11 high). Two remain:
- **diskcache** (medium) — no patch available; only caches controlled HTTP responses, low risk
- **pillow** (high) — blocked by fastembed `<12.0` cap; PSD image vuln, not exploitable here

Remaining Dependabot alerts are npm/frontend. See commit `0a0002b`.

### ~~9. Scripts reference~~ — DONE
Covered in the operations runbook (`docs/operations-runbook.md`, Scripts Reference section).

### ~~6. System architecture doc~~ — DONE
See [`docs/system-architecture.md`](system-architecture.md). High-level system map with ASCII diagram, components table, collections reference, data lifecycle, API surface, infrastructure, and links to all deep dives. Documentation suite also received a consistency pass: cross-linking, British spelling, tone alignment, and content deduplication across all docs.

### ~~7. Azure cost budget alerts~~ — DONE
Monthly budget `lex-monthly-budget` created on `rg-lex` via Azure Cost Management. £600/month with alerts at 80% (£480) and 100% (£600) to `lex@cabinetoffice.gov.uk`. Runs April 2026 – April 2027. Current spend ~£430/month, dominated by Qdrant Cloud SaaS (~£300/month, 73-79%).

## Nice-to-have (future team)

- Sentry or similar for error aggregation
- Search quality/relevance metrics
- Qdrant collection consistency health check (detect orphaned sections)
- Replace broad `except Exception` with specific types in `cache.py`, `telemetry.py`
- MCP server documentation (tools available, debugging connections)
- Testing strategy doc (how to mock Qdrant, write new endpoint tests)

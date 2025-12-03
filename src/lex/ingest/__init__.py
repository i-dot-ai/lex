"""Unified ingestion pipeline for Lex.

This module provides a single entry point for all data ingestion:
    python -m lex.ingest --mode daily --limit 10

Design principles:
    - Qdrant IS the state - no JSONL tracking files
    - One pipeline per source - unified pipelines yield core + sections
    - Two-stage DAG - scrape first, then AI enrichment
    - Idempotent - deterministic UUIDs, safe to re-run
"""

from lex.ingest.orchestrator import (
    ingest_amendments,
    ingest_caselaw_summaries,
    ingest_explanatory_notes,
    run_daily_ingest,
    run_full_ingest,
)
from lex.ingest.state import filter_new_items, get_existing_ids

__all__ = [
    "run_daily_ingest",
    "run_full_ingest",
    "ingest_amendments",
    "ingest_caselaw_summaries",
    "ingest_explanatory_notes",
    "get_existing_ids",
    "filter_new_items",
]

# Dataset Statistics

Empirical statistics from the production Qdrant Cloud instance. For the system overview, see [system-architecture.md](system-architecture.md).

**Last Updated**: March 2026
**Source**: Production healthcheck (`https://lex.lab.i.ai.gov.uk/healthcheck`)

## Collection Sizes

| Collection | Points | Description |
|------------|--------|-------------|
| `caselaw_section` | 4,723,735 | Paragraphs within court judgments |
| `legislation_section` | 2,098,225 | Individual provisions within Acts and SIs |
| `amendment` | 892,210 | Legislative changes and modifications |
| `embedding_cache` | 238,600 | Cached embeddings for performance |
| `legislation` | 219,685 | Acts and Statutory Instruments (document-level) |
| `explanatory_note` | 88,956 | Explanatory memoranda sections |
| `caselaw` | 69,970 | Court judgments (document-level) |
| `caselaw_summary` | 61,107 | AI-generated case summaries |
| **Total** | **~8.4M** | **Total vectors in production** |

## Coverage by Document Type

### Legislation
- **Total Acts/SIs**: 219,685 documents
- **Total Provisions**: 2,098,225 sections
- **Coverage**: 1963-present (complete), 1267-1962 (partial)
- **Average sections per document**: 9.6

### Case Law
- **Total Cases**: 69,970 judgments
- **Total Paragraphs**: 4,723,735 sections
- **Total Summaries**: 61,107 AI-generated summaries
- **Coverage**: 2001-present
- **Average paragraphs per case**: 67.5

### Explanatory Notes
- **Total Sections**: 88,956
- **Coverage**: Modern legislation with published explanatory notes

### Amendments
- **Total Records**: 892,210
- **Coverage**: Cross-references between affecting and changed legislation

## Storage Metrics

**With Scalar Quantisation (INT8)**:
- Dense vectors: ~8 GB (quantised from ~32 GB)
- Sparse vectors: ~5 GB
- Payload data: ~20 GB
- **Total**: ~33 GB

**Cloud Configuration**:
- Provider: Qdrant Cloud (Azure UK South)
- Quantisation: INT8 scalar, `always_ram=True`
- Monthly cost: see [qdrant-hosting.md](qdrant-hosting.md)

## Data Quality

### Legislation Year Metadata
- **Year coverage**: 99.47% of 2,098,225 sections have `legislation_year` populated
- **Remaining nulls**: ~11,100 sections — genuinely unrecoverable OCR artefacts (bare local act numbers, missing references)
- **Recovery work**: `scripts/maintenance/fix_null_years.py` recovered ~202K of 213K null-year sections across five tiers — see [year-recovery.md](year-recovery.md)

### Legislation Coverage Gaps
- **Pre-1963**: ~85K Acts from 1267-1962, year metadata 99.47% complete
- **PDF-only documents**: 93,883 PDFs identified (1837-2025) — see [pdf-dataset.md](pdf-dataset.md)

### Case Law Constraints
- **Historical limit**: TNA data only from 2001 onwards
- **UKSC**: Only exists from 2009 onwards (court established 2009)

### Amendment Status
- Collection status: yellow (optimising)
- URI normalisation partially complete — see [operations-runbook.md](operations-runbook.md)

## Data Sources

All data sourced from:
- **Legislation**: legislation.gov.uk (The National Archives)
- **Case Law**: caselaw.nationalarchives.gov.uk (TNA)
- **Explanatory Notes**: Embedded within legislation.gov.uk

## Related Documentation

- [pdf-dataset.md](pdf-dataset.md) — Detailed PDF coverage analysis
- [data-models.md](data-models.md) — Pydantic model definitions
- [ingestion-process.md](ingestion-process.md) — How data is collected
- [qdrant-hosting.md](qdrant-hosting.md) — Storage and hosting costs

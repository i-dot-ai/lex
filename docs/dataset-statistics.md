# Dataset Statistics

Empirical statistics from production Qdrant Cloud instance.

**Last Updated**: November 2025
**Source**: Azure-hosted Qdrant cluster

## Collection Sizes

| Collection | Points | Description |
|------------|--------|-------------|
| `legislation_section` | 997,461 | Individual provisions within Acts and SIs |
| `caselaw_section` | 2,403,490 | Paragraphs within court judgments |
| `embedding_cache` | 333,000+ | Cached embeddings for performance |
| `legislation` | 125,255 | Acts and Statutory Instruments (document-level) |
| `explanatory_note` | 82,344 | Explanatory memoranda sections |
| `caselaw` | 30,512 | Court judgments (document-level) |
| `amendment` | 32 | Legislative changes and modifications |
| **Total** | **~4,000,000** | **Total vectors in production** |

## Coverage by Document Type

### Legislation
- **Total Acts/SIs**: 125,255 documents
- **Total Provisions**: 997,461 sections
- **Coverage**: 1963-present (complete), 1267-1962 (partial)
- **Average sections per document**: 7.97

### Case Law
- **Total Cases**: 30,512 judgments
- **Total Paragraphs**: 2,403,490 sections
- **Coverage**: 2001-present
- **Average paragraphs per case**: 78.7

### Explanatory Notes
- **Total Sections**: 82,344
- **Coverage**: Modern legislation with published explanatory notes

### Amendments
- **Total Records**: 32
- **Status**: Early development (limited ingestion)

## Storage Metrics

**With Scalar Quantization (INT8)**:
- Dense vectors: ~4 GB (quantized from 16 GB)
- Sparse vectors: ~3.2 GB
- Payload data: ~12 GB
- **Total**: ~19 GB

**Cloud Configuration**:
- Provider: Qdrant Cloud (Azure UK South)
- RAM: 4 GiB
- Disk: 32 GB
- Monthly cost: ~$60 (see `qdrant-hosting.md`)

## Data Quality

### Legislation Coverage Gaps
- **Pre-1963**: Partial coverage (~85K Acts from 1267-1962)
- **PDF-only documents**: 93,883 PDFs identified (1837-2025)
- **Sections missing**: Some documents have metadata but incomplete section ingestion

### Case Law Constraints
- **Historical limit**: TNA data only exists from 2001 onwards
- **UKSC**: Only exists from 2009 onwards (court established 2009)

## Data Sources

All data sourced from:
- **Legislation**: legislation.gov.uk (The National Archives)
- **Case Law**: caselaw.nationalarchives.gov.uk (TNA)
- **Explanatory Notes**: Embedded within legislation.gov.uk

## Related Documentation

- **PDF Dataset**: `pdf-dataset.md` - Detailed PDF coverage analysis
- **Data Models**: `data-models.md` - Pydantic model definitions
- **Ingestion Process**: `ingestion-process.md` - How data is collected
- **Cost Analysis**: `qdrant-hosting.md` - Storage and hosting costs

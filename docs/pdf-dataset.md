# PDF Digitisation for Historical UK Legislation

Historical UK legislation (1267-1962) exists only as scanned PDFs without structured XML. This system uses Azure OpenAI GPT-5-mini with vision to extract structured data from these PDFs and upload to Qdrant with full provenance tracking.

**Corpus**: 10,267 PDF-only documents identified from legislation.gov.uk

---

## Dataset Statistics

**Total PDFs on legislation.gov.uk**: 93,883

| Period | Years | PDFs | Notes |
|--------|-------|------|-------|
| Pre-1797 | 1267-1796 | ~500 | Full XML already exists; no OCR needed |
| Late Georgian | 1797-1837 | 6,853 | Scanned PDFs without XML body text |
| Victorian–Edwardian | 1837-1952 | 19,200 | Systematic scanned PDFs |
| Modern | 1963-2025 | 73,290 | XML + PDF both available |

**Key finding**: Systematic static scanned PDFs only exist from 1797 onwards. Pre-1797 legislation was either fully digitised as XML or left as metadata-only records.

### Type Distribution

| Type | Count | Share |
|------|-------|-------|
| UK Statutory Instruments (uksi) | 48,502 | 51.7% |
| UK Local Acts (ukla) | 14,161 | 15.1% |
| NI Statutory Rules (nisr) | 9,112 | 9.7% |
| NI Statutory Rules/Orders (nisro) | 8,790 | 9.4% |
| UK Public General Acts (ukpga) | 7,555 | 8.0% |

Primary legislation accounts for 23.7%, secondary for 76.3%.

---

## Architecture

```
PDF URLs (10,267) → Azure Blob Storage → GPT-5-mini Vision → Structured JSONL →
    XML Metadata Fetch → Merge → Qdrant Upload (with provenance)
```

| Component | Path | Purpose |
|-----------|------|---------|
| PDF Discovery | `data/pdf_only_legislation_complete.csv` | 10,267 PDF-only documents |
| PDF Processor | `src/lex/processing/historical_pdf/processor.py` | GPT-5-mini extraction (v1.1 prompt) |
| Batch Processing | `scripts/pdf/process_pdfs.py` | Parallel processing with resume |
| Progress Checker | `scripts/pdf/check_pdf_progress.py` | Statistics and cost estimates |
| Blob Setup | `scripts/setup_azure_storage.py` | Azure Blob Storage upload |
| Models | `src/lex/processing/historical_pdf/models.py` | Pydantic extraction result models |

---

## Provenance Tracking

Every PDF-extracted document includes five provenance fields:

```python
provenance_source: "llm_ocr"          # vs "xml" for authoritative content
provenance_model: "gpt-5-mini"        # AI model used
provenance_prompt_version: "v1.1"     # Prompt version for reproducibility
provenance_timestamp: datetime        # Extraction time (UTC)
provenance_response_id: "resp_..."    # Azure OpenAI response ID
```

These fields are added to the standard `Legislation` and `LegislationSection` models (see [data-models.md](data-models.md)).

### Filtering by Provenance

```python
# Query only authoritative XML content
{"query": "data protection", "provenance_source": ["xml"]}

# Query only AI-extracted historical content
{"query": "railway companies", "year_from": 1800, "year_to": 1900, "provenance_source": ["llm_ocr"]}
```

---

## XML + PDF Merge Strategy

The uploader fetches authoritative XML metadata from legislation.gov.uk and merges it with PDF-extracted content:

| Field | Source | Fallback |
|-------|--------|----------|
| `id`, `uri`, `title`, `publisher`, `category`, `type`, `year`, `number`, `status` | XML metadata | Direct |
| `description` | XML `dc:description` | PDF preamble (truncated to 500 chars) |
| `enactment_date` | XML `ukm:EnactmentDate` | PDF `date_enacted` |
| `number_of_provisions` | PDF section count | sections + schedules |
| `extent` | N/A | `[]` (not available for PDF-only docs) |
| `provenance_*` | PDF extraction | 5 provenance fields |

---

## Usage

```bash
# 1. Discover PDF URLs
uv run python data/extract_all_pdfs.sh

# 2. Upload PDFs to Azure Blob Storage
uv run python scripts/setup_azure_storage.py

# 3. Batch process with GPT-5-mini
uv run python scripts/pdf/process_pdfs.py \
  --csv data/pdf_only_legislation_complete.csv \
  --max-concurrent 5 \
  --output data/historical_legislation_results.jsonl

# 4. Check progress
uv run python scripts/pdf/check_pdf_progress.py data/historical_legislation_results.jsonl
```


---

## Known Limitations

1. **Geographic extent**: Not available in XML or PDF for historical docs — defaults to `[]`
2. **XML descriptions**: Rarely present for PDF-only legislation — falls back to PDF preamble
3. **Complex layouts**: Tables and mathematical notation may extract poorly
4. **OCR quality**: Pre-1800s documents may have poor scans
5. **Nested sub-sections**: May be missed in deeply structured documents

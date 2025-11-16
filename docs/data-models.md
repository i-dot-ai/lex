# Data Models Guide

## Overview

Lex uses Pydantic models to ensure data consistency and validation across the pipeline. Each document type has its own model with specific fields, validation rules, and computed properties. All models are stored in Qdrant vector database with hybrid vector embeddings (dense + sparse).

## Base Models

### LexModel
The base class for all Lex documents, providing common fields and functionality.

```python
class LexModel(BaseModel):
    id: str                    # Unique identifier (required)
    created_at: datetime       # When document was created
    updated_at: datetime       # Last modification time
```

## Legislation Models

### Legislation
Primary model for legislative documents (Acts, SIs, etc.).

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | str | Unique identifier | `"http://www.legislation.gov.uk/id/ukpga/2023/52"` |
| `title` | str | Document title | `"Online Safety Act 2023"` |
| `type` | LegislationType | Document type enum | `LegislationType.UKPGA` |
| `year` | int | Year of enactment | `2023` |
| `number` | int | Document number | `52` |
| `enacted` | date | Enactment date | `"2023-10-26"` |
| `modified` | datetime | Last modification | `"2023-10-26T00:00:00"` |
| `version` | int | Version number | `1` |
| `status` | str | Current status | `"enacted"` |
| `html_snippet` | str | HTML preview | `"<p>An Act to...</p>"` |
| `html` | str | Full HTML content | Complete document HTML |
| `number_of_provisions` | int | Section count | `215` |
| `territorial_extent` | List[str] | Geographic coverage | `["England", "Wales", "Scotland"]` |

#### Computed Fields
- `citation` - Full citation (e.g., "2023 c. 52")
- `url` - Link to legislation.gov.uk

### LegislationType Enum
```python
class LegislationType(str, Enum):
    # UK-wide
    UKPGA = "ukpga"    # UK Public General Acts
    UKSI = "uksi"      # UK Statutory Instruments
    UKLA = "ukla"      # UK Local Acts
    UKPPA = "ukppa"    # UK Private and Personal Acts
    
    # Scotland
    ASP = "asp"        # Acts of the Scottish Parliament
    SSI = "ssi"        # Scottish Statutory Instruments
    
    # Wales
    ASC = "asc"        # Acts of Senedd Cymru
    ANAW = "anaw"      # Acts of National Assembly for Wales
    WSI = "wsi"        # Wales Statutory Instruments
    
    # Northern Ireland
    NIA = "nia"        # NI Assembly Acts
    NISR = "nisr"      # NI Statutory Rules
    NISI = "nisi"      # NI Orders in Council
    
    # European (pre-Brexit)
    EUR = "eur"        # EU Regulations
    EUDR = "eudr"      # EU Directives
    EUDN = "eudn"      # EU Decisions
    
    # ... (28 types total)
```

### LegislationSection
Individual provisions within legislation.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | str | Section identifier | `"ukpga/2023/52/section/1"` |
| `uri` | str | Full URI | `"http://www.legislation.gov.uk/id/ukpga/2023/52/section/1"` |
| `legislation_id` | str | Parent document ID | `"http://www.legislation.gov.uk/id/ukpga/2023/52"` |
| `title` | str | Section title | `"Meaning of 'online safety'"` |
| `text` | str | Section content | Full text of the provision |
| `extent` | List[GeographicalExtent] | Geographic application | See GeographicalExtent |
| `provision_type` | ProvisionType | Type of provision | `ProvisionType.SECTION` |

#### Computed Fields
- `section_number` - Extracted section number

### GeographicalExtent
Territorial application details.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `territory` | str | Geographic area | `"England"` |
| `start_date` | date | When extent begins | `"2023-10-26"` |
| `end_date` | Optional[date] | When extent ends | `None` |
| `notes` | str | Additional notes | `"Applies to reserved matters only"` |

## Case Law Models

### CaseLaw
Court judgments and decisions.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | str | Unique identifier | `"ewca/civ/2023/1234"` |
| `title` | str | Case title | `"Smith v Jones"` |
| `neutral_citation` | str | Neutral citation | `"[2023] EWCA Civ 1234"` |
| `court` | Court | Court enum | `Court.EWCA` |
| `division` | Optional[str] | Court division | `"Civil Division"` |
| `year` | int | Judgment year | `2023` |
| `number` | int | Case number | `1234` |
| `date` | date | Judgment date | `"2023-11-15"` |
| `judges` | List[str] | Presiding judges | `["Lord Justice Smith", "Lady Justice Jones"]` |
| `parties` | List[str] | Case parties | `["John Smith", "Jane Jones"]` |
| `catchwords` | List[str] | Key topics | `["Contract", "Breach", "Damages"]` |
| `headnote` | str | Case summary | Brief summary |
| `html` | str | Full judgment HTML | Complete judgment text |

### Court Enum
```python
class Court(str, Enum):
    # Supreme Court
    UKSC = "uksc"      # UK Supreme Court
    UKPC = "ukpc"      # Privy Council
    
    # Court of Appeal
    EWCA_CIV = "ewca-civ"   # Civil Division
    EWCA_CRIM = "ewca-crim" # Criminal Division
    
    # High Court
    EWHC_ADMIN = "ewhc-admin"  # Administrative Court
    EWHC_CH = "ewhc-ch"        # Chancery Division
    EWHC_QB = "ewhc-qb"        # Queen's Bench
    EWHC_FAM = "ewhc-fam"      # Family Division
    
    # ... (many more courts)
```

### CaseLawSection
Paragraphs within judgments.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | str | Section identifier | `"ewca/civ/2023/1234/para/45"` |
| `caselaw_id` | str | Parent case ID | `"ewca/civ/2023/1234"` |
| `paragraph_number` | int | Paragraph number | `45` |
| `text` | str | Paragraph content | Full paragraph text |
| `is_quote` | bool | Whether it's a quote | `false` |
| `judge` | Optional[str] | Speaking judge | `"Lord Justice Smith"` |

## Amendment Models

### Amendment
Legislative changes and modifications.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | str | Unique identifier | Generated UUID |
| `changed_legislation` | str | Document being changed | `"ukpga/2006/41"` |
| `changed_provision` | Optional[str] | Specific provision | `"section/45"` |
| `affecting_legislation` | str | Document making change | `"uksi/2023/1234"` |
| `affecting_provision` | Optional[str] | Provision making change | `"regulation/2"` |
| `type` | AmendmentType | Type of change | `AmendmentType.SUBSTITUTION` |
| `date` | date | When change takes effect | `"2024-01-01"` |
| `extent` | List[str] | Geographic application | `["England", "Wales"]` |
| `note` | Optional[str] | Explanatory note | `"Words substituted"` |

### AmendmentType Enum
```python
class AmendmentType(str, Enum):
    SUBSTITUTION = "substitution"   # Text replaced
    INSERTION = "insertion"         # Text added
    REPEAL = "repeal"              # Section removed
    REVOCATION = "revocation"      # SI revoked
    AMENDMENT = "amendment"        # General change
    MODIFICATION = "modification"  # Modified application
```

## Explanatory Note Models

### ExplanatoryNote
Explanatory memoranda for legislation.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | str | Unique identifier | `"ukpga/2023/52/en"` |
| `legislation_id` | str | Related legislation | `"ukpga/2023/52"` |
| `title` | str | Note title | `"Explanatory Notes to Online Safety Act 2023"` |
| `html` | str | Full HTML content | Complete explanatory text |
| `sections` | List[ExplanatoryNoteSection] | Individual sections | See below |

### ExplanatoryNoteSection
Sections within explanatory notes.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | str | Section identifier | `"ukpga/2023/52/en/section/1"` |
| `explanatory_note_id` | str | Parent note ID | `"ukpga/2023/52/en"` |
| `section_ref` | str | Related legislation section | `"section/1"` |
| `title` | str | Section title | `"Overview of section 1"` |
| `text` | str | Explanatory text | Detailed explanation |

## Validation Rules

### Common Validations
1. **IDs must be unique** - Enforced by Qdrant UUID5 generation
2. **Required fields** - Cannot be None or empty
3. **Date formats** - ISO 8601 format required
4. **Enums** - Must match defined values
5. **URLs** - Must be valid HTTP(S) URLs

### Type-Specific Validations

#### Legislation
- `year` must be between 1066 and current year
- `number` must be positive integer
- `type` must be valid LegislationType enum

#### Case Law
- `neutral_citation` must match citation pattern
- `court` must be valid Court enum
- `date` cannot be in future

#### Amendments
- `changed_legislation` must be valid document ID
- `affecting_legislation` must be valid document ID
- `date` represents when change takes effect

## Qdrant Schema

Each model is stored in Qdrant with:
- **Hybrid vectors**: Dense (1024D Azure OpenAI) + Sparse (BM25 FastEmbed)
- **Payload**: Full Pydantic model as JSON
- **UUID5 point IDs**: Deterministic IDs from document identifiers
- **Named vectors**: `dense` and `sparse` for RRF fusion search

Example Qdrant collection configuration for Legislation:
```python
{
    "vectors": {
        "dense": {
            "size": 1024,  # Azure OpenAI text-embedding-3-large
            "distance": "Cosine"
        },
        "sparse": {
            "modifier": "Idf"  # BM25 from FastEmbed
        }
    },
    "hnsw_config": {
        "m": 16,
        "ef_construct": 100
    }
}
```

Point structure:
```python
{
    "id": uuid.uuid5(NAMESPACE, document_id),  # Deterministic UUID
    "vector": {
        "dense": [0.123, ...],  # 1024D float array
        "sparse": {"indices": [...], "values": [...]}  # BM25 vector
    },
    "payload": {
        "id": "ukpga/2023/52",
        "title": "Online Safety Act 2023",
        "type": "ukpga",
        "year": 2023,
        "html": "<p>...</p>",
        # ... all other Pydantic fields
    }
}
```

## Best Practices

### 1. Use Enums for Fixed Values
```python
# Good
type: LegislationType = LegislationType.UKPGA

# Bad
type: str = "ukpga"
```

### 2. Validate Early
```python
# Models validate on instantiation
try:
    legislation = Legislation(**data)
except ValidationError as e:
    logger.error(f"Invalid data: {e}")
```

### 3. Use Computed Properties
```python
@computed_field
@property
def citation(self) -> str:
    return f"{self.year} c. {self.number}"
```

### 4. Handle Optional Fields
```python
# Check optional fields before use
if legislation.enacted:
    days_since = (date.today() - legislation.enacted).days
```

### 5. Consistent ID Format
- Legislation: `{type}/{year}/{number}`
- Case Law: `{court}/{year}/{number}`
- Sections: `{parent_id}/section/{number}`

## Extending Models

To add a new document type:

1. Create model in `src/lex/{type}/models.py`
2. Inherit from `LexModel`
3. Define fields with types and validation
4. Add computed properties as needed
5. Create corresponding Qdrant collection schema
6. Update documentation

Example:
```python
class NewDocumentType(LexModel):
    """Model for new document type."""
    
    # Required fields
    title: str
    type: NewDocumentEnum
    content: str
    
    # Optional fields
    metadata: Optional[Dict[str, Any]] = None
    
    # Computed property
    @computed_field
    @property
    def summary(self) -> str:
        return self.content[:200] + "..."
```

## Common Issues

### 1. Validation Errors
```python
# Missing required field
ValidationError: field required (type=value_error.missing)

# Wrong type
ValidationError: value is not a valid integer (type=type_error.integer)
```

### 2. Enum Mismatches
```python
# Use .value for string representation
doc_type = LegislationType.UKPGA.value  # "ukpga"
```

### 3. Date Parsing
```python
# Dates must be ISO format
date: "2023-11-15"  # Good
date: "15/11/2023"  # Bad
```

### 4. Large Text Fields
- Consider truncating for previews
- Use separate fields for full content
- Be mindful of Qdrant payload size limits (10MB default)
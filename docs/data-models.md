# Data Models

Pydantic models for all document types in the Lex pipeline. Each model defines the fields stored in Qdrant and validated at ingest time.

For domain context on legislation types and court hierarchy, see [uk-legal-system.md](uk-legal-system.md). For how these models flow through the pipeline, see [ingestion-process.md](ingestion-process.md).

---

## Legislation

Top-level legislative documents (Acts, SIs, etc.).

**Source**: `src/lex/legislation/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Canonical URI (`http://www.legislation.gov.uk/id/ukpga/2023/52`) |
| `uri` | str | Document URI |
| `title` | str | Document title |
| `type` | LegislationType | One of 28 legislation type codes — see [uk-legal-system.md](uk-legal-system.md) |
| `year` | int | Year of enactment/making |
| `number` | int | Document number within that year |
| `enacted` | date | Enactment/making date |
| `modified` | datetime | Last modification timestamp |
| `version` | int | Version number |
| `status` | str | Current status (e.g. "enacted", "revised") |
| `html_snippet` | str | HTML preview |
| `html` | str | Full HTML content |
| `number_of_provisions` | int | Section count |
| `territorial_extent` | list[str] | Geographic coverage (England, Wales, Scotland, N.I.) |

**Computed**: `citation` (e.g. "2023 c. 52"), `url` (link to legislation.gov.uk)

## LegislationSection

Individual provisions within legislation.

**Source**: `src/lex/legislation/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Section identifier |
| `uri` | str | Full URI |
| `legislation_id` | str | Parent document ID |
| `title` | str | Section title |
| `text` | str | Section content |
| `extent` | list[GeographicalExtent] | Territorial application |
| `provision_type` | ProvisionType | Type of provision (section, schedule, etc.) |

**Computed**: `section_number`

---

## Case Law

Court judgments and decisions.

**Source**: `src/lex/caselaw/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Identifier (e.g. `ewca/civ/2023/1234`) |
| `title` | str | Case title (e.g. "Smith v Jones") |
| `neutral_citation` | str | Neutral citation (e.g. `[2023] EWCA Civ 1234`) |
| `court` | Court | Court enum — see [uk-legal-system.md](uk-legal-system.md) |
| `division` | str? | Court division |
| `year` | int | Judgment year |
| `number` | int | Case number |
| `date` | date | Judgment date |
| `judges` | list[str] | Presiding judges |
| `parties` | list[str] | Case parties |
| `catchwords` | list[str] | Key topics |
| `headnote` | str | Case summary |
| `html` | str | Full judgment HTML |

## CaseLawSection

Paragraphs within judgments.

**Source**: `src/lex/caselaw/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Section identifier |
| `caselaw_id` | str | Parent case ID |
| `paragraph_number` | int | Paragraph number |
| `text` | str | Paragraph content |
| `is_quote` | bool | Whether it's a quotation |
| `judge` | str? | Speaking judge |

---

## Amendment

Legislative changes and modifications.

**Source**: `src/lex/amendment/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Generated UUID |
| `changed_legislation` | str | Document being changed |
| `changed_provision` | str? | Specific provision changed |
| `affecting_legislation` | str | Document making the change |
| `affecting_provision` | str? | Provision making the change |
| `type` | AmendmentType | substitution, insertion, repeal, revocation, amendment, modification |
| `date` | date | When change takes effect |
| `extent` | list[str] | Geographic application |
| `note` | str? | Explanatory note |

---

## Explanatory Note

Explanatory memoranda for legislation.

**Source**: `src/lex/explanatory_note/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Identifier (e.g. `ukpga/2023/52/en`) |
| `legislation_id` | str | Related legislation |
| `title` | str | Note title |
| `html` | str | Full HTML content |
| `sections` | list[ExplanatoryNoteSection] | Individual sections |

### ExplanatoryNoteSection

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Section identifier |
| `explanatory_note_id` | str | Parent note ID |
| `section_ref` | str | Related legislation section |
| `title` | str | Section title |
| `text` | str | Explanatory text |

---

## Validation Rules

All models inherit from `LexModel` (defined in `src/lex/core/models.py`) which provides `id`, `created_at`, and `updated_at`.

**Common rules**:
- IDs must be unique (enforced by UUID5 generation at upload)
- Required fields cannot be None or empty
- Dates must be ISO 8601 format
- Enums must match defined values

**Type-specific**:
- Legislation `year` must be between 1066 and current year
- Case law `neutral_citation` must match citation pattern
- Case law `date` cannot be in future
- Amendment `changed_legislation` and `affecting_legislation` must be valid document IDs

---

## Qdrant Storage

Each model is stored in Qdrant with hybrid vectors: dense (1024D Azure OpenAI) + sparse (BM25 FastEmbed). Point IDs are deterministic UUID5s derived from document identifiers, making re-ingestion idempotent.

Collection schemas are defined in `src/lex/*/qdrant_schema.py` — these are the source of truth. See [search-architecture.md](search-architecture.md) for how hybrid search works.

## ID Format Conventions

- Legislation: `http://www.legislation.gov.uk/id/{type}/{year}/{number}`
- Case law: `{court}/{year}/{number}`
- Sections: `{parent_id}/section/{number}`

# UK Legal System Primer

Essential UK legal concepts for understanding the Lex codebase.

## Regnal Years

### What They Are

Regnal years date legislation by monarch's reign, not calendar years. A monarch's first regnal year begins on accession and runs for 12 months.

**Example**: George III acceded October 25, 1760
- Regnal year 1: Oct 25, 1760 - Oct 24, 1761
- Regnal year 41: Oct 25, 1800 - Oct 24, 1801

### The 1963 Transition

**Acts of Parliament Numbering and Citation Act 1962** ended the regnal year system:
- **Before 1963**: Acts cited as "41 Geo. 3, c. 90" (George III, year 41, chapter 90)
- **From Jan 1, 1963**: Acts cited as "Northern Ireland Act 1998, c. 47" (calendar year)

### In Lex URLs

**Modern (1963+)**: `/ukpga/2020/12` (type/year/number)

**Historical (pre-1963)**: `/ukpga/Geo3/41/90` (type/monarch/regnal-year/number)

**Common monarch codes**:
- `Edw1` - Edward I (1272-1307)
- `Hen8` - Henry VIII (1509-1547)
- `Geo3` - George III (1760-1820)
- `Vict` - Victoria (1837-1901)
- `Eliz2` - Elizabeth II (1952-2022)

## Court Hierarchy

### Structure

**1. Supreme Court (UKSC)** - Established 2009, replaced House of Lords
- Final appeal court for all UK civil cases
- Format: `[2009] UKSC 1`
- Only exists from 2009 onwards

**2. Court of Appeal (EWCA)**
- Civil Division: `EWCA Civ` - appeals from High Court
- Criminal Division: `EWCA Crim` - appeals from Crown Court

**3. High Court (EWHC)** - Specialist divisions:
- `QB/KB` - Queen's/King's Bench (general civil)
- `Ch` - Chancery (property, trusts)
- `Fam` - Family Division
- `Admin` - Administrative Court (judicial review)
- `Comm` - Commercial Court

**4. Tribunals**
- `UKUT` - Upper Tribunal (administrative appeals)
- `UKFTT` - First-tier Tribunal

### Citation Format
```
[year] COURT number (Division)
[2020] EWHC 123 (Admin)
```

## Legislation Types (28 Total)

### Primary Legislation

**Modern UK-wide**:
- `ukpga` (1801+) - UK Public General Acts
- `ukla` (1797+) - UK Local Acts
- `ukppa` (1539+) - UK Private and Personal Acts

**Devolved parliaments**:
- `asp` (1999+) - Acts of Scottish Parliament
- `nia` (2000+) - Acts of Northern Ireland Assembly
- `asc` (2020+) - Acts of Senedd Cymru (Wales)
- `anaw` (2012-2020) - Acts of National Assembly for Wales

**Historical**:
- `aep` (1267-1707) - Acts of English Parliament
- `aosp` (1424-1707) - Acts of Old Scottish Parliament
- `apgb` (1707-1800) - Acts of Parliament of Great Britain

### Secondary Legislation

**Modern statutory instruments**:
- `uksi` (1948+) - UK Statutory Instruments
- `ssi` (1999+) - Scottish Statutory Instruments
- `wsi` (2012+) - Wales Statutory Instruments
- `nisr` (2000+) - Northern Ireland Statutory Rules

**Historical**:
- `uksro` (1894-1947) - UK Statutory Rules and Orders
- `nisi` (1974+) - NI Orders in Council

### European Legislation (1973-2020)

- `eur` - EU Regulations (directly applicable)
- `eudr` - EU Directives (required UK implementation)
- `eudn` - EU Decisions

### Why So Many Types?

**Devolution**: Scotland Act 1998, NI Act 1998, Wales Acts created devolved parliaments with legislative powers in health, education, transport (reserved matters stay at Westminster).

**Constitutional history**: UK formed through unions:
- 1707: England + Scotland → Great Britain
- 1801: Great Britain + Ireland → United Kingdom
- 1921: Ireland partition creates Northern Ireland

## Enacted vs Made

### Enacted (Primary Legislation - Acts)

**Process**: Bill → Parliament readings → Royal Assent → **Enacted**

Acts receive Royal Assent and become "enacted."

### Made (Secondary Legislation - SIs)

**Process**: Minister drafts SI → Laid before Parliament → Minister signs → **Made**

SIs are "made" when minister signs them.

**Terminology**:
- "Laid" = presented to Parliament
- "Made" = signed by minister
- "Coming into force" = date SI takes effect (may differ)

## Historical Context

### Why 1963 Matters

The 1962 Act changed citation from regnal years to calendar years. This affects:
- URL patterns (`/ukpga/Geo3/41/90` vs `/ukpga/1963/1`)
- Scraping strategy (must handle both formats)
- Year extraction logic

### Pre-1800 Data is Sparse

| Period | Years | Documents | Coverage |
|--------|-------|-----------|----------|
| Medieval | 1267-1600 | ~500 | Major statutes only |
| Stuart | 1600-1700 | ~800 | Constitutional acts |
| Georgian | 1700-1800 | ~10K | Significant acts |
| Victorian | 1800-1900 | ~25K | Good coverage |
| Modern Pre-1963 | 1900-1962 | ~50K | Very good |
| Complete | 1963+ | ~150K | 100% complete |

**Why sparse**: TNA prioritized in-force and constitutional legislation. Most medieval Acts were repealed and never digitized.

### Case Law Starts 2001

- TNA's Find Case Law digitized from 2001 onwards
- UKSC only exists from 2009 (before: House of Lords)
- Earlier cases in commercial databases (Westlaw, LexisNexis)

## Key Takeaways for Developers

1. **1963 is the critical dividing line** - regnal years before, calendar years after
2. **Court hierarchy matters** - UKSC > EWCA > EWHC for authority
3. **28 types from constitutional history** - unions, devolution, local/private Acts
4. **"Enacted" = Acts, "Made" = SIs** - different processes
5. **Pre-1800 sparse by design** - TNA prioritized in-force legislation
6. **2009 matters for caselaw** - UKSC didn't exist before
7. **Devolution started 1999** - ASP, SSI, NIA, NISR only from then

## Code References

- `src/lex/legislation/models.py` - LegislationType enum, year ranges
- `src/lex/caselaw/models.py` - Court hierarchy, divisions
- `docs/legislation-gov-uk-api.md` - URL patterns, regnal years

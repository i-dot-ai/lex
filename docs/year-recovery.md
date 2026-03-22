# Year Recovery: From Regnal Years to Calendar Dates

How we recovered year metadata for 200,000+ historical legislation sections, and the 800-year dating system that made it necessary.

## The Problem

When Lex ingested legislation from legislation.gov.uk, pre-1963 Acts arrived with URIs like:

```
/id/ukpga/Vict/44-45/12
/id/ukla/Geo3/39-40/67
/id/ukpga/Edw7/9/29
```

These aren't broken URLs. They encode a dating system that predates the Gregorian calendar's adoption in Britain: **regnal years** — the year of a monarch's reign. The standard parser (`_parse_year_from_legislation_id()` in `models.py`) handled canonical formats, but 213,356 sections arrived with nonstandard, OCR-damaged, or freetext citations that it couldn't parse. Their `legislation_year` was null, making them invisible to year-filtered searches.

## Regnal Years: A Brief History

Before 1963, every Act of Parliament was dated by the regnal year of the reigning monarch — the number of years since their accession. This wasn't bureaucratic whimsy. For most of English legal history, the sovereign *was* the legislature. Parliament met at the monarch's pleasure, and sessions were counted from the start of each reign.

### How It Works

The **Acts of Parliament Numbering and Citation Act 1962** (which took effect from 1 January 1963) finally switched to calendar years. Everything before that uses regnal years:

```
5 & 6 Vict. c. 45
```

This means: **Chapter 45 of the session spanning the 5th and 6th years of Queen Victoria's reign**. Victoria acceded on 20 June 1837, so:

```
year = 1837 + 5 - 1 = 1841
```

The `- 1` is because the first regnal year is year 1, not year 0 (there is no "year zero" in regnal counting, just as there is none in the CE calendar).

Sessions frequently spanned two regnal years because Parliament's sessions didn't align with accession dates. A session beginning in November of the 5th year and ending in July of the 6th year would be cited as "5 & 6 Vict."

### The Monarch Table

Lex maintains a complete monarch lookup table covering 31 sovereigns from Henry III (1216) to Elizabeth II (2022):

| Abbreviation | Monarch | Reign | Notable |
|---|---|---|---|
| `Hen3` | Henry III | 1216-1272 | Earliest legislation in the dataset |
| `Edw1` | Edward I | 1272-1307 | Statute of Westminster, foundation of common law |
| `Edw3` | Edward III | 1327-1377 | 50-year reign, extensive legislation |
| `Hen8` | Henry VIII | 1509-1547 | Reformation statutes |
| `Eliz1` | Elizabeth I | 1558-1603 | Poor Laws, vagrancy Acts |
| `Cha1` | Charles I | 1625-1649 | Ends with execution, no legislation 1649-1660 |
| `Cha2` | Charles II | 1660-1685 | Restoration — reign backdated to 1649 by legal fiction |
| `WillandMar` | William & Mary | 1689-1694 | Joint sovereignty after Glorious Revolution |
| `Will3` | William III | 1694-1702 | Sole reign after Mary's death |
| `Vict` | Victoria | 1837-1901 | 64-year reign, largest volume of legislation |
| `Geo5` | George V | 1910-1936 | WWI and interwar legislation |
| `Edw8` | Edward VIII | 1936-1936 | Abdicated — only 1 session year |
| `Geo6` | George VI | 1936-1952 | Shares 1936 start year with Edward VIII |
| `Eliz2` | Elizabeth II | 1952-2022 | Last monarch to have regnal-year legislation (pre-1963 Acts) |

### Historical Curiosities

**The Interregnum gap (1649-1660)**: Charles I was executed in 1649. The Commonwealth and Protectorate governed without a monarch. When Charles II was restored in 1660, Parliament backdated his reign to 1649 — legally pretending the republic never happened. Acts from this period are cited under Charles II's regnal years despite being passed during Cromwell's rule.

**Edward VIII's single session**: Edward VIII reigned for less than a year (January-December 1936) before abdicating. Only one parliamentary session falls under his regnal year. Legislation from this transition is cited as "1 Edw. 8 & 1 Geo. 6" — a combined citation spanning both monarchs' first (and, for Edward, only) year.

**William and Mary's joint sovereignty**: After the Glorious Revolution of 1688, William III and Mary II reigned jointly — the only true co-sovereignty in English history. When Mary died in 1694, William continued alone. This creates two overlapping citation systems: `WillandMar` (1689-1694) and `Will3` (1694-1702).

**Philip and Mary**: Mary I's marriage to Philip II of Spain created a brief period of dual citation (`PhilandMarSess`, 1554-1558), though Philip's authority was severely limited by Parliament.

## The OCR Problem

Lex's pre-1963 legislation was digitised from scanned Parliamentary records using LLM-based OCR. The OCR had to read centuries-old printed text — blackletter type, water damage, faded ink, margin notes — and produce structured URIs. It did remarkably well for most records, but ~10% of sections arrived with nonstandard or damaged citations.

### What Went Wrong

The OCR produced a taxonomy of errors:

**Nonstandard separators** — using slashes, underscores, or dots where the canonical format uses hyphens:
```
/Vict/44/45/12        (slashes instead of /Vict/44-45/12)
/Vict_44_45/c12       (underscores)
/30Vict.c.8           (dots, concatenated)
```

**Concatenated session-monarch** — running the session number into the monarch abbreviation:
```
/52-53Vict/cxcvii     (most common nonstandard format)
/10Edw7/102
```

**Freetext citations** — the OCR reproduced the citation as printed rather than normalising:
```
52 & 53 Vict. c. clviii
14 Geo. 6. c. xliii
S.R. & O. 1948 No. 845
```

**Latinised monarch names** — older documents used Latin forms:
```
/13-14-Victoriae/45   (Victoriae = Victoria)
/19victoriae/13
/7-edw-vii/82         (vii = VII = 7)
```

**UNCLEAR markers** — when the OCR couldn't confidently read the text:
```
[UNCLEAR: possible_reference 'ukpga/20 Geo. 5/Ch. 1']
[UNCLEAR: reference not provided on scanned pages]
[UNCLEAR: Liverpool_Sanitary_Amendment_Act_1854_Cap.xv]
```

**Combined reign references** — transition periods between monarchs:
```
/Edw8and1Geo6/1/100   (Edward VIII & 1st year of George VI)
26 Geo. 5. & 1 Edw. 8. c. xxix
```

**Acts of English Parliament** — pre-Union legislation with its own abbreviation scheme:
```
/aep/Ja2/1/15         (James II, session 1, chapter 15)
```

**Local act numbers** — bare sequential numbers with no date information at all:
```
Local.-207.
[Local.-42]
```

## The Recovery

Recovery proceeded in four tiers over a single session, progressively loosening the parsing rules:

### Tier 1: Deterministic Regex (172,251 recovered)

Six strategies applied in order of specificity:

1. **Explicit year** — extract `(1889)` or `S.I. 1948` or `/1845/` from URI
2. **Regnal with separators** — handle slashes, underscores, concatenation, freetext citations
3. **Combined reign** — parse `Edw8and1Geo6` transition patterns
4. **Freetext monarch** — scan for any monarch name followed by session numbers
5. **Broad year** — find any 4-digit year `\b\d{4}\b` anywhere in the URI
6. **Number-before-monarch** — handle `33 Vict.` where session precedes monarch (reverse of canonical order)

Each strategy builds a monarch alias map (`MONARCH_ALIASES`) that maps 50+ variants to the 31 canonical keys. Every computed year is validated against the monarch's actual reign dates — if the calculation puts a year outside the reign, it's rejected.

### Tier 2: LLM Fallback (~4,900 recovered)

Records that defeated all regex strategies were sent to Azure OpenAI's `gpt-5-nano` in batches of 25 URIs. The system prompt included the full monarch table and calculation formula. The model handled:

- `[UNCLEAR:]` references with enough context to infer the legislation
- Roman numeral chapter numbers that obscured the citation structure
- Ambiguous or damaged citations where context was needed

Only high and medium confidence results were applied. Low confidence results (~11,400) were discarded.

### Tier 3: Enhanced Regex (22,924 recovered)

Analysis of Tier 2's failures revealed two patterns the regex had missed:

- **Freetext years without word boundaries** — `1949 No. 2170` where the year isn't a clean URI segment
- **Session-before-monarch** — `33 Vict.` where traditional citation order puts the number first

Two new strategies caught these without any LLM calls.

### Tier 4: Alias Expansion and Embedded Years (~2,000 projected)

The final pass targets:

- **Latinised monarch names** — adding `Victoriae` → `Vict` to the alias map
- **Act names with embedded years** — `Liverpool_Sanitary_Amendment_Act_1854_Cap.xv` where the year is part of an underscored name
- **Acts of English Parliament abbreviations** — `Ja2` → `Jas1` (James I)

## Results

| Tier | Method | Recovered | Cumulative |
|------|--------|-----------|------------|
| 1 | Regex (6 strategies) | 172,251 | 172,251 |
| 2 | LLM (gpt-5-nano) | ~4,900 | ~177,100 |
| 3 | Enhanced regex | 22,924 | ~200,000 |
| 4 | Alias expansion + embedded years | 1,723 | ~201,800 |
| 5 | Monarch table fix + slug parsing | 430 | ~202,200 |

**Starting null-year sections**: 213,356
**Final null-year sections**: 11,139
**Recovery rate**: 94.8%
**Coverage**: 99.47% of 2,098,225 sections have year metadata

## What Remains

The ~11,100 unrecoverable records fall into clear categories:

- **No reference at all** (35%) — `[UNCLEAR: reference not provided on scanned pages]`. The original document genuinely didn't contain a citation that the OCR could read.
- **Generic UNCLEAR** (25%) — `[UNCLEAR: legislation reference]`. The OCR flagged something but couldn't extract anything useful.
- **Local act numbers only** (20%) — `Local.-207.` or `[UNCLEAR: Local.-42]`. These are sequential numbers assigned to local Acts with no date or monarch information. Recovery would require cross-referencing against a complete local Acts register.
- **Damaged beyond parsing** (20%) — Various edge cases where the citation is too fragmented to extract any temporal signal.

These records remain searchable by text content — only year-filtered queries miss them.

## Implementation

- **Script**: `scripts/maintenance/fix_null_years.py`
- **Monarch table**: `src/lex/legislation/models.py` (`_REGNAL_YEAR_RANGES`, line 486)
- **Baseline parser**: `src/lex/legislation/models.py` (`_parse_year_from_legislation_id()`, line 521)
- **Coverage stats**: `docs/dataset-statistics.md`

## Further Reading

- [Acts of Parliament Numbering and Citation Act 1962](https://www.legislation.gov.uk/ukpga/1962/34) — the Act that finally switched to calendar years
- [Regnal years on legislation.gov.uk](https://www.legislation.gov.uk/understanding-legislation#regnal-years) — official explanation
- [Chronological Table of the Statutes](https://www.legislation.gov.uk/changes/chron-tables) — complete chronological listing of all Acts

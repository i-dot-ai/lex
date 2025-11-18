# Legislation.gov.uk Technical Documentation

Comprehensive documentation of The National Archives legislation API, XML structure, URL patterns, and data availability.

**Last Updated:** 2025-10-13
**API Base:** https://www.legislation.gov.uk
**Official Developer Docs:** https://www.legislation.gov.uk/developer

---

## Table of Contents

1. [Overview](#overview)
2. [URL Patterns & Structure](#url-patterns--structure)
3. [Data Formats](#data-formats)
4. [XML Structure (CLML)](#xml-structure-clml)
5. [Historical Data Coverage](#historical-data-coverage)
6. [Legislation Types](#legislation-types)
7. [Regnal Years](#regnal-years)
8. [Pagination & Feeds](#pagination--feeds)
9. [API Best Practices](#api-best-practices)

---

## Overview

The National Archives (TNA) provides free, structured access to all UK legislation through legislation.gov.uk. The service uses RESTful APIs with content negotiation and provides data in multiple formats (XML, RDF, Atom, CSV, HTML).

### Key Characteristics

- **Complete Coverage:** 1267 to present (750+ years)
- **XML Format:** Crown Legislation Markup Language (CLML)
- **API Style:** RESTful with content negotiation
- **Licensing:** Open Government Licence v3.0
- **Versioning:** Point-in-time versions available (format: YYYY-MM-DD)
- **Caching:** Recommended 14 days for HTTP caching

### Data Completeness

| Period | Coverage | Notes |
|--------|----------|-------|
| 1988-Present | Complete | All legislation digitized |
| 1801-1987 | Partial | Significant Acts digitized (~85K) |
| 1267-1800 | Sparse | Historical/constitutional Acts (~2K) |
| Pre-1267 | None | No digitized legislation |

---

## URL Patterns & Structure

### 1. Basic Document URI

```
http://www.legislation.gov.uk/{type}/{year}/{number}
```

**Examples:**
```
http://www.legislation.gov.uk/ukpga/2018/12        # Data Protection Act 2018
http://www.legislation.gov.uk/uksi/2020/1234       # Statutory Instrument
http://www.legislation.gov.uk/asp/2023/1           # Scottish Parliament Act
```

### 2. Historical (Pre-1963) Regnal Year URI

For Acts passed before the Acts of Parliament Numbering and Citation Act 1962, legislation uses regnal year format:

```
http://www.legislation.gov.uk/{type}/{monarch}/{regnal-year}/{number}
```

**Monarch Format:** `{Name}{Regnal-Number}` (e.g., `Geo3`, `Vict`, `Edw1`)

**Standard Examples:**
```
http://www.legislation.gov.uk/ukpga/Geo3/41/90     # Crown Debts Act 1801 (George III, 41st year)
http://www.legislation.gov.uk/ukpga/Vict/1/1       # Crown Suits Act 1838 (Victoria, 1st year)
http://www.legislation.gov.uk/aep/Edw1/3/5         # Statute of Westminster 1275 (Edward I, 3rd year)
http://www.legislation.gov.uk/apgb/Will3/10/26     # Bank of England Act 1698 (William III, 10th year)
```

**Special Collection Format (Medieval Legislation):**

For very old legislation that was originally published as collections of chapters, the URI includes a "cc" (chapter collection) identifier:

```
http://www.legislation.gov.uk/{type}/{monarch}cc{collection}/{regnal-year}/{number}
```

**Examples:**
```
http://www.legislation.gov.uk/aep/Edw1cc1929/25/9  # Magna Carta (1297) - chapters 1, 9, 29
http://www.legislation.gov.uk/aep/Edw1cc16/25/6    # Confirmation of the Charters (1297) - chapters 1-6
http://www.legislation.gov.uk/aep/Hen3c23/52/23    # Provisions of Oxford (1267) - chapter 23
http://www.legislation.gov.uk/aep/Edw3Stat5/25/4   # Statute of Labourers (1351) - Statute 5
```

**Collection Identifiers Explained:**
- `cc1929` = Chapters 1, 9, 29 (the remaining un-repealed chapters)
- `cc16` = Chapters 1-6
- `c23` = Chapter 23
- `Stat5` = The 5th statute from that regnal year

**Regnal Year Ambiguity:**
When a calendar year spans multiple regnal years, the API returns HTTP 300 (Multiple Choices) with links to each version.

### 3. Section/Provision URI

```
http://www.legislation.gov.uk/{type}/{year}/{number}/section/{section-number}
```

**Examples:**
```
http://www.legislation.gov.uk/ukpga/2018/12/section/5              # DPA 2018, section 5
http://www.legislation.gov.uk/ukpga/2018/12/section/5/1            # subsection (1)
http://www.legislation.gov.uk/ukpga/2018/12/section/5/1/a          # paragraph (a)
http://www.legislation.gov.uk/ukpga/2018/12/schedule/2             # Schedule 2
http://www.legislation.gov.uk/ukpga/2018/12/schedule/2/paragraph/3 # Schedule 2, para 3
```

### 4. Point-in-Time (Versioned) URI

```
http://www.legislation.gov.uk/{type}/{year}/{number}/{date}
```

**Date Format:** `YYYY-MM-DD`

**Examples:**
```
http://www.legislation.gov.uk/ukpga/2018/12/2020-01-01    # DPA 2018 as at 1 Jan 2020
http://www.legislation.gov.uk/ukpga/2018/12/enacted       # Original enacted version
http://www.legislation.gov.uk/ukpga/2018/12/prospective   # Future (not yet in force) version
```

**Point-in-Time Metadata:**
- Sections with `Match="false"` attribute are not valid at requested date
- `Status` attribute values: `Prospective`, `Repealed`, `Discarded`

### 5. Data Format URIs

Append `/data.{format}` to any legislation URI:

```
http://www.legislation.gov.uk/{type}/{year}/{number}/data.{format}
```

**Supported Formats:**
- `.xml` - Crown Legislation Markup Language (CLML)
- `.rdf` - RDF/XML metadata
- `.akn` - Akoma Ntoso XML format
- `.xht` - HTML snippet (fragment)
- `.htm` - Full HTML page
- `.html` - HTML5 snippet
- `.csv` - Tabular metadata (for lists)
- `.pdf` - PDF rendering
- `.feed` - Atom feed (for lists/searches)

**Examples:**
```
http://www.legislation.gov.uk/ukpga/2018/12/data.xml      # XML content
http://www.legislation.gov.uk/ukpga/2018/12/data.rdf      # RDF metadata
http://www.legislation.gov.uk/ukpga/2018/12/data.pdf      # PDF download
```

### 6. Browse & Search URIs

**Year Browse:**
```
http://www.legislation.gov.uk/{type}/{year}                    # Browse by type & year
http://www.legislation.gov.uk/ukpga/2020                       # All UKPGA from 2020
```

**Historical Year Browse (Pre-1963):**
```
http://www.legislation.gov.uk/primary+secondary/{year}         # All legislation from year
http://www.legislation.gov.uk/primary+secondary/1801           # All 1801 legislation
http://www.legislation.gov.uk/primary+secondary/1801/data.feed # Atom feed for 1801
```

**Search:**
```
http://www.legislation.gov.uk/search?type={type}&year={year}&title={query}
http://www.legislation.gov.uk/all?title=Data%20Protection
```

**ID Lookup:**
```
http://www.legislation.gov.uk/id?title={act-name}
http://www.legislation.gov.uk/id?title=Data%20Protection%20Act%202018
```

---

## Data Formats

### XML (CLML - Crown Legislation Markup Language)

Primary format for legislation content. Uses namespace `http://www.legislation.gov.uk/namespaces/legislation`.

**Schema:** http://www.legislation.gov.uk/schema/legislation.xsd
**GitHub:** https://github.com/legislation/clml-schema

**Key Features:**
- Dublin Core metadata (dc:title, dc:identifier, dc:date, etc.)
- Hierarchical structure (Body → P1group → P1 → P1para → P2 → P2para)
- XHTML for tables, MathML for formulae
- Commentaries and amendments tracked
- Extent/territorial application metadata

### Atom Feeds

List endpoints support Atom feeds via `/data.feed`:

```xml
<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:leg="http://www.legislation.gov.uk/namespaces/legislation">
  <id>http://www.legislation.gov.uk/primary+secondary/1801/data.feed</id>
  <title>Search Results</title>
  <openSearch:itemsPerPage>20</openSearch:itemsPerPage>
  <openSearch:startIndex>1</openSearch:startIndex>
  <leg:morePages>5</leg:morePages>

  <leg:facetTypes>
    <leg:facetType type="UnitedKingdomLocalAct" value="93"/>
    <leg:facetType type="UnitedKingdomPublicGeneralAct" value="4"/>
  </leg:facetTypes>

  <entry>
    <id>http://www.legislation.gov.uk/id/ukpga/Geo3/41/90</id>
    <title>Crown Debts Act 1801</title>
    <link rel="alternate" href="http://www.legislation.gov.uk/ukpga/Geo3/41/90"/>
  </entry>
</feed>
```

**Pagination:** Use `?page={N}` query parameter. Check `<leg:morePages>` for remaining pages.

### CSV Format

Tabular export of metadata:

```csv
"Title","Type","Year","Number","URI"
"Data Protection Act 2018","UnitedKingdomPublicGeneralAct","2018","12","http://www.legislation.gov.uk/id/ukpga/2018/12"
```

---

## XML Structure (CLML)

### Root Element

```xml
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             DocumentURI="http://www.legislation.gov.uk/ukpga/2018/12"
             IdURI="http://www.legislation.gov.uk/id/ukpga/2018/12"
             NumberOfProvisions="215"
             RestrictExtent="E+W+S+N.I."
             SchemaVersion="1.0">
```

**Key Attributes:**
- `DocumentURI` - Full HTTP URI to document
- `IdURI` - Canonical identifier URI
- `NumberOfProvisions` - Total section count
- `RestrictExtent` - Territorial application (E=England, W=Wales, S=Scotland, N.I.=Northern Ireland)

### Metadata Section

```xml
<ukm:Metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
              xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata">
  <dc:identifier>http://www.legislation.gov.uk/id/ukpga/2018/12</dc:identifier>
  <dc:title>Data Protection Act 2018</dc:title>
  <dc:description>An Act to make provision...</dc:description>
  <dc:date>2018-05-23</dc:date>
  <dc:type>text</dc:type>
  <dc:language>en</dc:language>
  <dc:publisher>Statute Law Database</dc:publisher>
  <dc:modified>2024-01-15</dc:modified>

  <ukm:PrimaryMetadata>
    <ukm:DocumentClassification>
      <ukm:DocumentCategory Value="primary"/>
      <ukm:DocumentMainType Value="UnitedKingdomPublicGeneralAct"/>
      <ukm:DocumentStatus Value="revised"/>
    </ukm:DocumentClassification>
    <ukm:Year Value="2018"/>
    <ukm:Number Value="12"/>
    <ukm:ISBN Value="9780105412182"/>
  </ukm:PrimaryMetadata>

  <ukm:Statistics>
    <ukm:TotalParagraphs Value="215"/>
    <ukm:BodyParagraphs Value="194"/>
    <ukm:ScheduleParagraphs Value="21"/>
  </ukm:Statistics>
</ukm:Metadata>
```

### Primary Structure

```xml
<Primary>
  <PrimaryPrelims>
    <Title>Data Protection Act 2018</Title>
    <Number>2018 c. 12</Number>
    <LongTitle>An Act to make provision for the regulation...</LongTitle>
    <DateOfEnactment><DateText>23rd May 2018</DateText></DateOfEnactment>
  </PrimaryPrelims>

  <Body>
    <!-- Content here -->
  </Body>

  <Schedules>
    <!-- Schedules here -->
  </Schedules>
</Primary>
```

### Body Structure (Hierarchical)

**UK Legislation Hierarchy:**
```
Body
└── Part (optional grouping)
    └── P1group (section grouping with title)
        └── Title (section heading)
        └── P1 (main section)
            └── Pnumber (e.g., "5")
            └── P1para (section content)
                └── Text (main text)
                └── P2 (subsection)
                    └── Pnumber (e.g., "(1)")
                    └── P2para (subsection content)
                        └── Text
                        └── P3 (sub-subsection)
                            └── Pnumber (e.g., "(a)")
                            └── P3para
                                └── Text
```

**Example:**
```xml
<Body>
  <Part id="part-1">
    <Number>Part 1</Number>
    <Title>General Processing</Title>

    <P1group>
      <Title>Lawfulness of processing</Title>
      <P1 id="section-5">
        <Pnumber>5</Pnumber>
        <P1para>
          <Text>Personal data must be processed lawfully in accordance with:</Text>
        </P1para>
        <P2 id="section-5-1">
          <Pnumber>(1)</Pnumber>
          <P2para>
            <Text>the principles set out in Article 5 of the GDPR;</Text>
          </P2para>
        </P2>
        <P2 id="section-5-2">
          <Pnumber>(2)</Pnumber>
          <P2para>
            <Text>the other provisions of the GDPR; and</Text>
          </P2para>
        </P2>
      </P1>
    </P1group>
  </Part>
</Body>
```

### Schedule Structure

```xml
<Schedules>
  <Schedule id="schedule-1">
    <Number>Schedule 1</Number>
    <Title>Data Protection Principles</Title>

    <ScheduleBody>
      <Part id="schedule-1-part-1">
        <Number>Part 1</Number>
        <Title>Principles</Title>

        <P1 id="schedule-1-paragraph-1">
          <Pnumber>1</Pnumber>
          <P1para>
            <Text>Personal data must be processed fairly and lawfully.</Text>
          </P1para>
        </P1>
      </Part>
    </ScheduleBody>
  </Schedule>
</Schedules>
```

### Commentary & Amendments

```xml
<Commentaries>
  <Commentary id="c1" Type="F">
    <Para>
      <Text>Words inserted by <Citation URI="..." Year="2020" Number="5">
        Finance Act 2020 (c. 5)</Citation>, section 42(3)</Text>
    </Para>
  </Commentary>

  <Commentary id="c2" Type="C">
    <Para>
      <Text>This section has effect subject to section 6</Text>
    </Para>
  </Commentary>
</Commentaries>
```

**Commentary Types:**
- `F` - Textual amendment (insertion, substitution, repeal)
- `C` - Commencement note
- `X` - Explanatory note
- `M` - Marginal citation
- `E` - Extent note
- `I` - Coming into force

**Referenced in text:**
```xml
<Text>Personal data<CommentaryRef Ref="c1"/> must be processed...</Text>
```

### Lists & Tables

**Unordered Lists:**
```xml
<UnorderedList>
  <ListItem>
    <Para><Text>first item</Text></Para>
  </ListItem>
  <ListItem>
    <Para><Text>second item</Text></Para>
  </ListItem>
</UnorderedList>
```

**Tables (XHTML):**
```xml
<Tabular xmlns="http://www.w3.org/1999/xhtml">
  <table>
    <thead>
      <tr><th>Column 1</th><th>Column 2</th></tr>
    </thead>
    <tbody>
      <tr><td>Data 1</td><td>Data 2</td></tr>
    </tbody>
  </table>
</Tabular>
```

### Historical Documents (Pre-1800)

**Language Attribute:**
```xml
<ukm:Metadata>
  <dc:language>enm</dc:language>  <!-- enm = Middle English -->
</ukm:Metadata>
```

**Image References (for archaic text):**
```xml
<Figure Orientation="portrait" ImageLayout="vertical">
  <Image ResourceRef="r00001" Height="auto" Width="auto"/>
</Figure>

<Resources>
  <Resource id="r00001">
    <ExternalVersion URI="http://www.legislation.gov.uk/aep/Edw1/3/5/images/aep_12750005_enm_1517436_001"/>
  </Resource>
</Resources>
```

### PDF-Only Documents

Some historical Acts only exist as PDFs. The XML will contain minimal metadata:

```xml
<Legislation>
  <ukm:Metadata>
    <dc:title>Act Name</dc:title>
    <ukm:DocumentStatus Value="base"/>
  </ukm:Metadata>

  <Primary>
    <PrimaryPrelims>
      <Title>Act Name</Title>
    </PrimaryPrelims>
    <Body>
      <!-- Empty or message indicating PDF-only -->
    </Body>
  </Primary>
</Legislation>
```

**PDF URL Pattern:**
```
http://www.legislation.gov.uk/{type}/{year}/{number}/pdfs/{type}_{year}{number}_en.pdf
http://www.legislation.gov.uk/gbla/Geo3/38/57/pdfs/gbla_17980057_en.pdf
```

---

## Historical Data Coverage

### Data Availability by Period

```
┌─────────────────────────────────────────────────────────────────────┐
│ Period       │ Years    │ Docs/Year │ Total   │ Coverage            │
├─────────────────────────────────────────────────────────────────────┤
│ Ancient      │ 1267-1600│ ~1-10     │ ~500    │ Major statutes only │
│ Stuart Era   │ 1600-1700│ ~10-50    │ ~800    │ Constitutional acts │
│ Georgian     │ 1700-1800│ ~50-150   │ ~10K    │ Significant acts    │
│ Victorian    │ 1800-1900│ ~150-400  │ ~25K    │ Good coverage       │
│ Modern Pre   │ 1900-1962│ ~400-1000 │ ~50K    │ Very good coverage  │
│ Complete     │ 1963-Pres│ ~1000-2500│ ~150K   │ 100% complete       │
└─────────────────────────────────────────────────────────────────────┘
```

### Atom Feed Statistics (From 1801 Feed)

Total documents by year (sample from feed metadata):

```
1801: 97    | 1850: 246  | 1900: 137  | 1950: 1284 | 2000: 2500
1810: 218   | 1860: 296  | 1910: 131  | 1960: 986  | 2010: 3968
1820: 91    | 1870: 289  | 1920: 131  | 1970: 1500 | 2020: 2499
1830: 145   | 1880: 280  | 1930: 336  | 1980: 2006 | 2024: 2029
1840: 141   | 1890: 225  | 1940: 241  | 1990: 2080 | 2025: 1528*
```

*2025 count as of October 2025

### Document Type Distribution (Historical)

**1801 Example (from Atom feed facets):**
- `ukpga` (UK Public General Acts): 4
- `ukla` (UK Local Acts): 93

**Pre-1700:**
- `aep` (Acts of English Parliament): Sparse
- `aosp` (Acts of Old Scottish Parliament): Very sparse
- `apgb` (Acts of Parliament of Great Britain 1707-1800): ~800

---

## Legislation Types

The UK has 28 distinct legislation types, categorized as Primary, Secondary, or European.

### Primary Legislation (16 types)

| Code | Full Name | Years Active | Notes |
|------|-----------|--------------|-------|
| **ukpga** | UK Public General Acts | 1801-present | Main UK legislation post-union |
| **asp** | Acts of the Scottish Parliament | 1999-present | Devolved Scotland |
| **asc** | Acts of Senedd Cymru | 2020-present | Welsh Parliament (renamed from anaw) |
| **anaw** | Acts of National Assembly for Wales | 2012-2020 | Now asc |
| **ukcm** | Church Measures | 1920-present | Church of England |
| **nia** | Acts of NI Assembly | 2000-present | Devolved NI (restored) |
| **ukla** | UK Local Acts | 1797-present | Local/private scope |
| **ukppa** | UK Private and Personal Acts | 1539-present | Private bills |
| **apni** | Acts of NI Parliament | 1921-1972 | Old Stormont |
| **gbla** | Local Acts of Parliament of GB | 1797-1800 | Pre-union local |
| **aosp** | Acts of Old Scottish Parliament | 1424-1707 | Pre-union Scotland |
| **aep** | Acts of English Parliament | 1267-1707 | Pre-union England |
| **apgb** | Acts of Parliament of Great Britain | 1707-1800 | Post-union, pre-Ireland |
| **mwa** | Measures of Welsh Assembly | 2008-2011 | Old Welsh powers |
| **aip** | Acts of Old Irish Parliament | 1495-1800 | Pre-union Ireland |
| **mnia** | Measures of NI Assembly | 1974 only | Brief period |

### Secondary Legislation (9 types)

| Code | Full Name | Years Active | Notes |
|------|-----------|--------------|-------|
| **uksi** | UK Statutory Instruments | 1948-present | Main secondary legislation |
| **wsi** | Wales Statutory Instruments | 2012-present | Welsh SIs |
| **ssi** | Scottish Statutory Instruments | 1999-present | Scottish SIs |
| **nisr** | Northern Ireland Statutory Rules | 2000-present | NI SIs |
| **nisro** | NI Statutory Rules and Orders | 1922-1974 | Historical NI |
| **nisi** | Northern Ireland Orders in Council | 1974-present | Direct rule orders |
| **uksro** | UK Statutory Rules and Orders | 1894-1947 | Pre-SI system |
| **ukmo** | UK Ministerial Orders | Various | Ministerial powers |
| **ukci** | Church Instruments | 1991-present | Church of England rules |

### European Legislation (3 types)

| Code | Full Name | Years Active | Notes |
|------|-----------|--------------|-------|
| **eur** | EU Regulations | 1973-2020 | Direct effect |
| **eudr** | EU Directives | 1973-2020 | Require implementation |
| **eudn** | EU Decisions | 1973-2020 | Specific addressees |

**Note:** EU legislation remains on legislation.gov.uk as "retained EU law" post-Brexit but is no longer updated.

---

## Regnal Years

Pre-1963 legislation uses regnal year numbering (year of monarch's reign).

### Format

```
{MonarchName}{RegnalNumber}/{RegnaYearStart}[-{RegnalYearEnd}]/{ActNumber}
```

### Common Monarchs in Database

| Monarch | Code | Reign | Regnal Years |
|---------|------|-------|--------------|
| Edward I | Edw1 | 1272-1307 | 1-35 |
| Edward III | Edw3 | 1327-1377 | 1-51 |
| Henry VIII | Hen8 | 1509-1547 | 1-38 |
| Elizabeth I | Eliz1 | 1558-1603 | 1-45 |
| James I | Jas1 | 1603-1625 | 1-23 |
| Charles II | Cha2 | 1660-1685 | 12-37 (starts at 12) |
| William III | Will3 | 1689-1702 | 1-14 |
| Anne | Ann | 1702-1714 | 1-13 |
| George II | Geo2 | 1727-1760 | 1-33 |
| George III | Geo3 | 1760-1820 | 1-60 |
| George IV | Geo4 | 1820-1830 | 1-11 |
| William IV | Will4 | 1830-1837 | 1-7 |
| Victoria | Vict | 1837-1901 | 1-64 |
| Edward VII | Edw7 | 1901-1910 | 1-10 |
| George V | Geo5 | 1910-1936 | 1-26 |
| Edward VIII | Edw8 | 1936 | 1 |
| George VI | Geo6 | 1936-1952 | 1-16 |
| Elizabeth II | Eliz2 | 1952-2022 | 1-71 |

### Regnal Year Spans

When an Act spans regnal years (e.g., passed in Feb 1801 = George III's 40th year ends, 41st begins), both years are referenced:

```
Geo3/40-41/120  # Act passed across two regnal years
```

### Computing Calendar Year from Regnal Year

The API provides `<ukm:AlternativeNumber Category="Regnal" Value="41_Geo_3_"/>` in metadata, but you must compute the calendar year from the reign dates:

```python
def regnal_to_calendar_year(monarch: str, regnal_year: int) -> int:
    """
    Convert regnal year to calendar year.
    Requires knowing accession date of each monarch.
    """
    # George III: Accession 25 Oct 1760
    # Regnal year 1: 25 Oct 1760 - 24 Oct 1761
    # Regnal year 41: 25 Oct 1800 - 24 Oct 1801
    # Therefore: Geo3/41 = 1801 (primarily)

    accession_dates = {
        'Geo3': (1760, 10, 25),
        'Vict': (1837, 6, 20),
        'Edw7': (1901, 1, 22),
        # ... etc
    }
    # Calculate from regnal_year + accession_date
```

**Simpler approach:** Extract year from `<ukm:Year Value="1801"/>` in metadata (TNA does the conversion).

---

## Pagination & Feeds

### Atom Feed Pagination

**Base URL:**
```
http://www.legislation.gov.uk/primary+secondary/{year}/data.feed
```

**Pagination Query Parameter:**
```
?page={N}   # 1-indexed
```

**Example:**
```
http://www.legislation.gov.uk/primary+secondary/1801/data.feed?page=1
http://www.legislation.gov.uk/primary+secondary/1801/data.feed?page=2
```

### Feed Structure for Pagination

```xml
<feed>
  <openSearch:itemsPerPage>20</openSearch:itemsPerPage>
  <openSearch:startIndex>1</openSearch:startIndex>
  <leg:morePages>5</leg:morePages>  <!-- 5 more pages after current -->

  <entry>...</entry>
  <entry>...</entry>
  <!-- 20 entries per page -->
</feed>
```

**Algorithm:**
```python
page = 1
while True:
    feed_url = f"{base}/primary+secondary/{year}/data.feed?page={page}"
    feed_xml = fetch(feed_url)

    # Process entries
    for entry in feed_xml.findall('.//atom:entry'):
        process_entry(entry)

    # Check if more pages exist
    more_pages = int(feed_xml.find('.//leg:morePages').text or '0')
    if more_pages == 0:
        break

    page += 1
```

### Rate Limiting

TNA does not publish official rate limits, but best practices:

- **Respect robots.txt:** https://www.legislation.gov.uk/robots.txt
- **Cache aggressively:** 14 days for stable content
- **User-Agent:** Identify your application
- **Throttle:** 1-2 requests/second is safe
- **Batch:** Use feeds instead of individual document requests where possible

---

## API Best Practices

### 1. Content Negotiation

The API supports content negotiation via HTTP headers:

```http
GET /ukpga/2018/12 HTTP/1.1
Accept: application/xml
```

**Supported Accept Headers:**
- `application/xml` - Returns CLML XML
- `application/rdf+xml` - Returns RDF metadata
- `application/atom+xml` - Returns Atom feed (for lists)
- `text/html` - Returns HTML rendering

**Recommendation:** Explicitly request `/data.xml` instead of relying on content negotiation for deterministic behavior.

### 2. Caching

```http
Cache-Control: max-age=1209600  # 14 days
```

**Strategy:**
- Cache XML responses for 14 days minimum
- Cache feeds for 1-7 days (more volatile)
- Use ETags if provided for conditional requests
- Store locally with SQLite or file cache

### 3. Error Handling

| Status Code | Meaning | Action |
|-------------|---------|--------|
| 200 OK | Success | Process content |
| 300 Multiple Choices | Regnal year ambiguity | Parse links, choose appropriate version |
| 404 Not Found | Document doesn't exist | May be PDF-only, check for PDF URL |
| 500 Server Error | TNA server issue | Retry with exponential backoff |
| 503 Service Unavailable | Maintenance | Retry after delay |

**PDF-Only Detection:**
```python
response = fetch(f"{base}/ukpga/{year}/{number}/data.xml")
if response.status_code == 404:
    # Check for PDF
    pdf_url = f"{base}/ukpga/{year}/{number}/pdfs/ukpga_{year}{number:04d}_en.pdf"
    pdf_response = fetch(pdf_url)
    if pdf_response.ok:
        # Document is PDF-only
```

### 4. User-Agent

Identify your application:

```http
User-Agent: LexSearch/1.0 (https://example.com; contact@example.com)
```

### 5. Bulk Access

For bulk downloads:

1. **Use Atom feeds** - More efficient than crawling year pages
2. **Process year ranges sequentially** - Avoid hammering a single year
3. **Respect off-peak hours** - UK business hours are 9am-5pm GMT/BST
4. **Consider TNA's bulk download service** - Contact them for dumps

### 6. Attribution

Per Open Government Licence v3.0:

```
Source: legislation.gov.uk
© Crown copyright
Licensed under the Open Government Licence v3.0
```

---

## Advanced Topics

### Amendments & Modifications

Legislation is updated over time. Amendments are tracked via:

1. **Commentary References:**
```xml
<Text>Personal data<CommentaryRef Ref="c1"/> must...</Text>

<Commentary id="c1" Type="F">
  <Para><Text>Words inserted by Finance Act 2020...</Text></Para>
</Commentary>
```

2. **Version History:**
- Use point-in-time URIs to see past versions
- Compare `/enacted` vs `/latest` to see all changes
- Check `<dc:modified>` in metadata for last update date

### Cross-References

Internal and external references are encoded:

```xml
<Citation URI="http://www.legislation.gov.uk/id/ukpga/2018/12"
         Year="2018"
         Class="UnitedKingdomPublicGeneralAct"
         Number="12">
  Data Protection Act 2018
</Citation>
```

**External citations:**
```xml
<CitationSubRef id="c00003"
                URI="http://www.legislation.gov.uk/id/ukpga/1998/29/section/5"
                CitationRef="c00002"
                SectionRef="section-5">
  section 5
</CitationSubRef>
```

### Extent (Territorial Application)

Legislation may apply to different territories:

```xml
<Legislation RestrictExtent="E+W+S+N.I.">  <!-- Applies UK-wide -->
<Legislation RestrictExtent="E+W">          <!-- England and Wales only -->
<Legislation RestrictExtent="S">            <!-- Scotland only -->
```

**Extent Codes:**
- `E` - England
- `W` - Wales
- `S` - Scotland
- `N.I.` - Northern Ireland
- `UK` - Entire United Kingdom

Some sections within an Act may have different extents:

```xml
<P1 RestrictExtent="E+W">  <!-- England & Wales only section -->
```

---

## Troubleshooting

### Issue: 404 for Historical Act

**Cause:** Document may be PDF-only or use different URI pattern.

**Solution:**
1. Try regnal year format: `/ukpga/Geo3/41/90` instead of `/ukpga/1801/90`
2. Check year browse page: `/primary+secondary/1801`
3. Look for PDF: `/ukpga/Geo3/41/90/pdfs/ukpga_18010090_en.pdf`

### Issue: XML Parse Error

**Cause:** CLML uses multiple namespaces and XHTML tables.

**Solution:**
```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(xml_content, 'xml')  # Use 'xml' parser, not 'html'
# Register namespaces
NS = {
    'leg': 'http://www.legislation.gov.uk/namespaces/legislation',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'ukm': 'http://www.legislation.gov.uk/namespaces/metadata'
}
```

### Issue: Empty Body in XML

**Cause:** Document may have been repealed entirely or is PDF-only.

**Solution:**
Check `<ukm:DocumentStatus>` and look for commentary explaining repeal.

---

## References

- **Official Developer Docs:** https://www.legislation.gov.uk/developer
- **URIs Guide:** https://www.legislation.gov.uk/developer/uris
- **Formats Guide:** https://www.legislation.gov.uk/developer/formats
- **XML Format:** https://www.legislation.gov.uk/developer/formats/xml
- **Atom Feeds:** https://www.legislation.gov.uk/developer/formats/atom
- **CLML Schema:** http://www.legislation.gov.uk/schema/legislation.xsd
- **GitHub Repository:** https://github.com/legislation/clml-schema
- **Data Completeness:** https://cdn.nationalarchives.gov.uk/documents/cas-82049-legislation-date.pdf

---

**End of Documentation**
